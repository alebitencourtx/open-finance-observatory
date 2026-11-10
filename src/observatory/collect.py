"""Bounded asynchronous HTTP collection. TLS verification is always enabled."""
from __future__ import annotations

import asyncio
import email.utils
import ipaddress
import json
import random
import ssl
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import truststore

from .domain import family_label
from .tls import bradesco_context
from .storage import Lake, digest, encoded, read_json, utcnow, write_json

DIRECTORY_URL = "https://data.directory.openbankingbrasil.org.br/participants"


def validate_url(url: str):
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("A coleta aceita somente URLs HTTPS pÃºblicas sem credenciais")
    if host in ("localhost",) or host.endswith((".local", ".internal")):
        raise ValueError("Host privado nÃ£o permitido")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if not address.is_global:
        raise ValueError("IP privado nÃ£o permitido")


def host_matches(host, domain):
    return host == domain or host.endswith("." + domain)


def discover(lake: Lake, groups_file: Path, directory_file: Path | None = None) -> dict:
    """Resolve only explicit CNPJs / exact domain suffixes; record heuristic evidence."""
    config = read_json(groups_file)
    if directory_file:
        raw = directory_file.read_bytes()
    else:
        context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        with httpx.Client(verify=context, timeout=120, follow_redirects=False, http2=True) as client:
            response = client.get(DIRECTORY_URL)
            response.raise_for_status()
            raw = response.content
    payload = json.loads(raw)
    if not isinstance(payload, list):
        raise ValueError("DiretÃ³rio deve ser uma lista de organizaÃ§Ãµes")
    sha = lake.put(raw)
    targets, evidence, seen = [], [], set()
    for organisation in payload:
        if organisation.get("Status") not in (None, "Active", "ACTIVE"):
            continue
        cnpj = str(organisation.get("RegistrationNumber") or "")
        company = organisation.get("OrganisationName") or organisation.get("LegalEntityName") or cnpj
        refs = []
        for server in organisation.get("AuthorisationServers") or []:
            for resource in server.get("ApiResources") or []:
                family = resource.get("ApiFamilyType") or ""
                if not (family.startswith(("opendata-", "channels_")) or family == "admin"):
                    continue
                if family_label(family) == "Fora do escopo":
                    continue
                for endpoint in resource.get("ApiDiscoveryEndpoints") or []:
                    url = endpoint.get("ApiEndpoint") or ""
                    if url:
                        refs.append((family, str(resource.get("ApiVersion") or ""), url))
        hosts = {urlsplit(ref[2]).hostname or "" for ref in refs}
        matches = []
        for group_id, group in config.items():
            domains = sorted({domain for host in hosts for domain in group["domains"] if host_matches(host, domain)})
            if cnpj in group["cnpjs"] or domains:
                matches.append((group_id, group, "curated_cnpj" if cnpj in group["cnpjs"] else "api_domain", domains))
        if len(matches) > 1:
            raise ValueError(f"ResoluÃ§Ã£o ambÃ­gua para {cnpj}; revise a configuraÃ§Ã£o")
        for group_id, group, method, domains in matches:
            evidence.append({"group_id": group_id, "company": company, "cnpj": cnpj, "method": method,
                             "domains": domains, "directory_sha": sha,
                             "caveat": "VÃ­nculo operacional heurÃ­stico; nÃ£o comprova controle societÃ¡rio"})
            for family, version, url in refs:
                key = [group_id, cnpj, family, url]
                endpoint_id = digest(encoded(key))
                if endpoint_id in seen:
                    continue
                seen.add(endpoint_id)
                targets.append({"endpoint_id": endpoint_id, "group": group_id, "group_label": group["label"],
                                "company": company, "cnpj": cnpj, "family": family, "version": version, "url": url})
    result = {"created_at": utcnow(), "directory_sha": sha, "directory_source": str(directory_file or DIRECTORY_URL),
              "targets": sorted(targets, key=lambda t: t["endpoint_id"]), "evidence": evidence}
    if not targets:
        raise ValueError("DiretÃ³rio sem endpoints no escopo configurado")
    write_json(lake.root / "catalog.json", result)
    return result


@dataclass(frozen=True)
class Policy:
    concurrency: int = 8
    per_host: int = 2
    interval: float = 0.25
    retries: int = 3
    timeout: float = 30
    max_pages: int = 400
    max_records: int = 100_000
    max_bytes: int = 24 * 1024 * 1024
    retry_cap: float = 30

    def __post_init__(self):
        if min(self.concurrency, self.per_host, self.max_pages, self.max_records, self.max_bytes) < 1:
            raise ValueError("Limites devem ser positivos")
        if self.retries < 0 or self.interval < 0 or self.timeout <= 0:
            raise ValueError("PolÃ­tica HTTP invÃ¡lida")


def retry_after(value: str | None, cap: float):
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            seconds = (email.utils.parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
        except (ValueError, TypeError):
            return None
    return min(cap, max(0, seconds))


def record_counts(family, data):
    """Count declared response grains explicitly; parent envelopes are not always records."""
    counts = {"envelopes": len(data)}
    if family.startswith(("opendata-insurance", "opendata-pension", "opendata-capitalization")):
        if data and all(isinstance(r, dict) and isinstance(r.get("society"), dict) and
                        isinstance(r["society"].get("products"), list) for r in data):
            counts["products"] = sum(len(r["society"]["products"]) for r in data)
    if family == "channels_banking-agents" and data:
        if all(isinstance(r, dict) and isinstance(r.get("bankingAgents"), list) for r in data):
            agents = [a for r in data for a in r["bankingAgents"]]
            counts["agents"] = len(agents)
            if all(isinstance(a, dict) and isinstance(a.get("locations"), list) for a in agents):
                counts["locations"] = sum(len(a["locations"]) for a in agents)
    return counts


class Collector:
    def __init__(self, lake: Lake, policy=Policy(), transport=None):
        self.lake, self.policy = lake, policy
        self.hosts, self.clocks, self.last = {}, {}, {}
        self.transport = transport

    async def request(self, client, url, page):
        validate_url(url)
        host = urlsplit(url).hostname
        semaphore = self.hosts.setdefault(host, asyncio.Semaphore(self.policy.per_host))
        clock = self.clocks.setdefault(host, asyncio.Lock())
        for attempt in range(self.policy.retries + 1):
            async with semaphore:
                async with clock:
                    delay = self.policy.interval - (time.monotonic() - self.last.get(host, 0))
                    if delay > 0:
                        await asyncio.sleep(delay)
                    self.last[host] = time.monotonic()
                try:
                    started = time.perf_counter()
                    async with client.stream("GET", url, params={"page": page, "page-size": 100}) as response:
                        content = bytearray()
                        async for part in response.aiter_bytes():
                            content.extend(part)
                            if len(content) > self.policy.max_bytes:
                                raise ValueError("response_size_limit")
                        result = (response.status_code, bytes(content), int((time.perf_counter()-started)*1000))
                        wait = retry_after(response.headers.get("Retry-After"), self.policy.retry_cap)
                    if response.status_code not in (408, 429, 500, 502, 503, 504) or attempt == self.policy.retries:
                        return result
                except (httpx.TransportError, httpx.TimeoutException):
                    if attempt == self.policy.retries:
                        raise
                    wait = None
            await asyncio.sleep(wait if wait is not None else min(self.policy.retry_cap, 2**attempt + random.random()))
        raise RuntimeError("retry_exhausted")

    async def capture(self, client, target):
        meta = {**target, "captured_at": utcnow(), "status": 0, "tls_insecure": False,
                "truncated": False, "error": ""}
        capture = {"policy": asdict(self.policy), "endpoint_id": target["endpoint_id"], "meta": meta, "objects": [], "format": "http-pages",
                   "bytes": 0, "page_log": []}
        seen, records, total_reported = set(), 0, 0
        counts = {}
        parsed = urlsplit(target["url"])
        # Observed Itaú v2 branches contract publishes a per-page total, not a global total.
        page_scoped = parsed.hostname == "api.itau" and parsed.path.rstrip("/") == "/open-banking/channels/v2/branches"
        meta["reported_total_scope"] = "page" if page_scoped else "result"
        try:
            if "{" in target["url"]:
                raise ValueError("templated_endpoint_requires_parameters")
            for page in range(1, self.policy.max_pages + 1):
                status, raw, latency = await self.request(client, target["url"], page)
                meta["status"], meta["latency_ms"] = status, latency
                sha = self.lake.put(raw)
                capture["page_log"].append({"page": page, "status": status, "sha": sha, "latency_ms": latency})
                capture["bytes"] += len(raw)
                if status != 200:
                    meta["error"] = f"http_{status}"
                    break
                payload = json.loads(raw)
                if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                    raise ValueError("invalid_data_contract")
                data = payload["data"]
                page_hash = digest(encoded(data))
                if data and page_hash in seen:
                    raise ValueError("pagination_repeated")
                seen.add(page_hash)
                capture["objects"].append(sha)
                records += len(data)
                for grain, count in record_counts(target["family"], data).items():
                    counts[grain] = counts.get(grain, 0) + count
                pagination = payload.get("meta", {})
                if not isinstance(pagination, dict):
                    raise ValueError("invalid_pagination_contract")
                for key in ("totalPages", "totalRecords"):
                    value = pagination.get(key)
                    if value is not None and (type(value) is not int or value < 0):
                        raise ValueError("invalid_pagination_total")
                total_pages = pagination.get("totalPages") or 0
                reported = pagination.get("totalRecords")
                if reported is not None:
                    if page_scoped and reported != len(data):
                        raise ValueError("reported_page_total_mismatch")
                    if not page_scoped and total_reported and reported != total_reported:
                        raise ValueError("pagination_total_changed")
                    total_reported = reported
                if max(counts.values(), default=0) > self.policy.max_records:
                    raise ValueError("record_limit")
                if (total_pages and page >= total_pages) or not data:
                    if (not page_scoped and reported is not None and total_reported not in counts.values()) or (not data and total_pages > page):
                        raise ValueError("reported_total_mismatch")
                    break
                if records >= self.policy.max_records:
                    raise ValueError("record_limit")
            else:
                raise ValueError("page_limit")
        except (ValueError, TypeError, httpx.HTTPError) as error:
            meta["error"] = str(error)[:500] or type(error).__name__
        meta["truncated"] = bool(meta["error"] and records)
        meta["records"], meta["total_records_reported"] = records, total_reported
        meta["record_counts"] = counts
        meta["reported_count_grains"] = [grain for grain, count in counts.items() if count == total_reported]
        return capture

    async def run(self, catalog: dict, resume: str | None = None):
        if resume:
            manifest = self.lake.snapshot(resume)
            if manifest.get("catalog_fingerprint") != digest(encoded(catalog["targets"])):
                raise ValueError("O catÃ¡logo mudou; crie uma nova coleta")
        else:
            snapshot_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + digest(encoded(time.time_ns()))[:8]
            manifest = {"schema_version": 1, "snapshot_id": snapshot_id, "created_at": utcnow(), "origin": "live_collection",
                        "catalog_fingerprint": digest(encoded(catalog["targets"])), "captures": [],
                        "directory_evidence": catalog["evidence"], "policy": asdict(self.policy), "state": "collecting"}
        completed = {c["endpoint_id"]: c for c in manifest["captures"]}
        pending = [t for t in catalog["targets"] if t["endpoint_id"] not in completed or
                   completed[t["endpoint_id"]]["meta"].get("error") or completed[t["endpoint_id"]]["meta"].get("status") != 200]
        if resume and not pending:
            if manifest["state"] != "captured":
                manifest["state"] = "captured"
                manifest["fingerprint"] = digest(encoded(manifest["captures"]))
                self.lake.save_snapshot(manifest)
            return manifest
        if resume and manifest["state"] == "captured":
            # Retrying a published/closed snapshot creates a new revision, never rewrites the old evidence.
            manifest = {**manifest, "parent_snapshot": manifest["snapshot_id"],
                        "snapshot_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + digest(encoded(time.time_ns()))[:8],
                        "created_at": utcnow(), "state": "collecting"}
        queue = asyncio.Queue()
        for target in pending:
            queue.put_nowait(target)
        context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.lake.save_snapshot(manifest, publish=False)
        limits = httpx.Limits(max_connections=self.policy.concurrency)
        mounts = None if self.transport else {
            "https://api.bradesco.com": httpx.AsyncHTTPTransport(verify=bradesco_context(), http2=True, limits=limits)
        }
        async with httpx.AsyncClient(verify=context, timeout=self.policy.timeout, transport=self.transport,
                                    mounts=mounts, limits=limits,
                                    follow_redirects=False, http2=True, headers={"User-Agent": "OpenFinanceObservatory/1.0"}) as client:
            async def worker():
                while True:
                    try:
                        target = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        return
                    capture = await self.capture(client, target)
                    completed[target["endpoint_id"]] = capture
                    manifest["captures"] = sorted(completed.values(), key=lambda c: c["endpoint_id"])
                    self.lake.save_snapshot(manifest, publish=False)
                    print(json.dumps({"event": "capture", "snapshot_id": manifest["snapshot_id"],
                                      "endpoint_id": target["endpoint_id"], "status": capture["meta"]["status"],
                                      "records": capture["meta"]["records"], "error": capture["meta"]["error"]}), flush=True)
                    queue.task_done()
            await asyncio.gather(*(worker() for _ in range(self.policy.concurrency)))
        manifest["state"] = "captured"
        manifest["fingerprint"] = digest(encoded(manifest["captures"]))
        self.lake.save_snapshot(manifest)
        return manifest
