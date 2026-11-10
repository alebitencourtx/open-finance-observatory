"""Bounded Arrow batches, content-addressed transform cache, explicit rate units."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from . import TRANSFORM_VERSION
from .domain import CREDIT, SCHEMAS, UFS, family_label, segment
from .storage import Lake, digest, encoded, read_json, write_json

POST_INDEXERS = {"POS_FIXADO_TR_TBF", "POS_FIXADO_TJLP", "POS_FIXADO_LIBOR", "POS_FIXADO_TLP",
                 "OUTRAS_TAXAS_POS_FIXADAS", "FLUTUANTES_CDI", "FLUTUANTES_SELIC", "OUTRAS_TAXAS_FLUTUANTES",
                 "INDICES_PRECOS_IGPM", "INDICES_PRECOS_IPCA", "INDICES_PRECOS_IPCC", "OUTROS_INDICES_PRECO",
                 "CREDITO_RURAL_TCR_POS", "CREDITO_RURAL_TRFC_POS"}


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        # API contracts use a decimal point. Never guess locale or unit by magnitude.
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def obj(value):
    return value if isinstance(value, dict) else {}


def items(value):
    return value if isinstance(value, list) else []


def walk(node, path="$"):
    if isinstance(node, dict):
        yield path, node
        for key, value in node.items():
            yield from walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from walk(value, f"{path}[{index}]")


class BatchWriter:
    def __init__(self, root: Path, batch_size: int = 4096):
        root.mkdir(parents=True, exist_ok=True)
        self.buffers = {name: [] for name in SCHEMAS}
        self.writers = {name: pq.ParquetWriter(root / f"{name}.parquet", schema, compression="zstd")
                        for name, schema in SCHEMAS.items()}
        self.counts = dict.fromkeys(SCHEMAS, 0)
        self.batch_size = batch_size

    def add(self, table, row):
        self.buffers[table].append(row)
        self.counts[table] += 1
        if len(self.buffers[table]) >= self.batch_size:
            self.flush(table)

    def flush(self, table):
        if self.buffers[table]:
            self.writers[table].write_table(pa.Table.from_pylist(self.buffers[table], schema=SCHEMAS[table]))
            self.buffers[table].clear()

    def close(self):
        try:
            for table in SCHEMAS:
                self.flush(table)
        finally:
            for writer in self.writers.values():
                writer.close()


def row_id(base, value):
    return digest(encoded([base["group_id"], base["cnpj"], base["family"], value]))[:32]


def product_name(record, family):
    return str(record.get("name") or record.get("code") or record.get("type") or
               " · ".join(str(x) for x in (record.get("investmentType") or record.get("anbimaCategory"),
                                          record.get("issuerInstitutionName")) if x) or
               ("Adiantamento a depositante" if "unarranged" in family else "Produto sem nome publicado"))


def money(value):
    if isinstance(value, dict):
        return number(value.get("value", value.get("amount")))
    return number(value)


def emit_product(writer, base, record, brand, json_path, identity_context=None):
    name = product_name(record, base["family"])
    product_id = row_id(base, [identity_context, record])
    writer.add("products", {**base, "entity_id": product_id, "name": name,
                            "product_type": str(record.get("type") or record.get("modality") or
                                                record.get("investmentType") or ""), "brand": str(brand)})
    for path, node in walk(record, json_path):
        if "prices" in node and (node.get("name") or node.get("code")):
            currency = obj(node.get("minimum")).get("currency") or obj(node.get("maximum")).get("currency") or "BRL"
            minimum, maximum = money(node.get("minimum")), money(node.get("maximum"))
            reason = "missing_value" if minimum is None or maximum is None else "negative_value" if min(minimum, maximum) < 0 else "inverted_range" if maximum < minimum else ""
            if obj(node.get("minimum")).get("currency", currency) != obj(node.get("maximum")).get("currency", currency):
                reason = "currency_mismatch"
            if currency not in ("BRL", "USD", "EUR"):
                reason = "unknown_currency"
            writer.add("fees", {**base, "entity_id": row_id(base, [product_id, path.removeprefix(json_path), node]),
                                "product_id": product_id, "name": name,
                                "service": str(node.get("name") or ""), "code": str(node.get("code") or ""),
                                "currency": str(currency), "minimum": money(node.get("minimum")),
                                "maximum": maximum, "valid": not reason, "reason": reason, "json_path": path})
        if not ({"referentialRateIndexer", "minimumRate", "maximumRate", "preFixedRate", "postFixedRate"} & node.keys()):
            continue
        # Containers do not themselves represent a rate observation.
        if not any(k in node for k in ("minimumRate", "maximumRate", "preFixedRate", "postFixedRate", "applications")):
            continue
        indexer = str(node.get("referentialRateIndexer") or node.get("indexer") or "UNKNOWN")
        low_raw, high_raw = node.get("minimumRate"), node.get("maximumRate")
        low, high = number(low_raw), number(high_raw)
        effective_minimum = round(low * 100, 6) if low is not None else None
        effective_maximum = round(high * 100, 6) if high is not None else None
        # applications.indexer.rate is a band median, not a minimum. Do not impute a minimum from it.
        if low is None and "preFixedRate" in node:
            low_raw = high_raw = node["preFixedRate"]
            low = high = number(low_raw)
            indexer = "PRE_FIXADO"
        unit = "pct_month" if indexer == "PRE_FIXADO" and base["family_label"] in CREDIT else "unknown"
        if indexer in POST_INDEXERS and base["family_label"] in CREDIT:
            # Official LoanInterestRate.rate is the indexer factor; min/max are the effective range.
            # See api-opendata-loans v1.1.0, LoanInterestRate and ApplicationRate.
            low_raw = high_raw = node.get("rate")
            low = high = number(low_raw)
            unit = "pct_indexer"
            path += ".rate"
        minimum = round(low * 100, 6) if low is not None else None
        maximum = round(high * 100, 6) if high is not None else None
        reason = ""
        if unit == "unknown":
            reason = "unit_not_comparable"
        elif minimum is None or minimum <= 0:
            reason = "missing_or_zero"
        elif (maximum is not None and maximum < minimum) or (effective_minimum is not None and effective_maximum is not None and effective_maximum < effective_minimum):
            reason = "inverted_range"
        elif (unit == "pct_month" and minimum > 50) or (unit == "pct_indexer" and minimum > 300):
            reason = "outside_analytical_range"
        writer.add("rates", {**base, "entity_id": row_id(base, [product_id, path.removeprefix(json_path), node]), "product_id": product_id,
                             "name": name, "indexer": indexer, "unit": unit, "minimum": minimum, "maximum": maximum,
                             "raw_minimum": None if low_raw is None else str(low_raw),
                             "raw_maximum": None if high_raw is None else str(high_raw),
                             "effective_minimum": effective_minimum, "effective_maximum": effective_maximum,
                             "valid": not reason, "reason": reason, "json_path": path})


CHANNEL_NAMES = {"branches": "Agências", "banking-agents": "Correspondentes",
                 "shared-automated-teller-machines": "ATMs", "electronic-channels": "Digitais",
                 "phone-channels": "Telefônicos"}


def emit_channel(writer, base, record, subtype, agent=None):
    identification = obj((agent or record).get("identification"))
    address = obj(record.get("postalAddress"))
    uf = str(address.get("countrySubDivision") or "").upper()
    row = {"channel_type": CHANNEL_NAMES.get(subtype, subtype),
           "name": str(identification.get("name") or identification.get("corporationName") or
                       identification.get("ownerName") or identification.get("type") or ""),
           "code": str(identification.get("code") or identification.get("cnpjNumber") or ""),
           "uf": uf if uf in UFS else "", "city": str(address.get("townName") or ""),
           "address": str(address.get("address") or ""), "postal_code": str(address.get("postCode") or "")}
    # Keep digital channels distinct by URL; physical sites by identifier and address.
    identity = [row, identification.get("urls"), identification.get("phones")]
    writer.add("channels", {**base, **row, "entity_id": row_id(base, identity)})


def reject(writer, base, record, path, reason):
    writer.add("quarantine", {**base, "json_path": path, "reason": reason,
                              "raw_json": json.dumps(record, ensure_ascii=False)})


def emit_record(writer, base, record, path):
    if not isinstance(record, dict) or not record:
        writer.add("quarantine", {**base, "json_path": path, "reason": "record_not_object",
                                  "raw_json": json.dumps(record, ensure_ascii=False)})
        return
    family = base["family"]
    if family == "channels_banking-agents" and not isinstance(record.get("bankingAgents"), list):
        reject(writer, base, record, path, "bankingAgents_not_array")
        return
    if "society" in record and (not isinstance(record["society"], dict) or not isinstance(record["society"].get("products"), list)):
        reject(writer, base, record, path, "society_products_not_array")
        return
    for field in ("interestRates", "bankingAgents"):
        if field in record and not isinstance(record[field], list):
            reject(writer, base, record, path + "." + field, field + "_not_array")
            return
    if family.startswith("channels_"):
        subtype = family.split("_", 1)[1]
        if subtype == "banking-agents":
            for agent in items(record.get("bankingAgents")):
                if isinstance(agent, dict):
                    if not isinstance(agent.get("locations"), list):
                        reject(writer, base, agent, path + ".locations", "locations_not_array")
                    for index, location in enumerate(items(agent.get("locations"))):
                        if isinstance(location, dict) and location:
                            emit_channel(writer, base, location, subtype, agent)
                        else:
                            reject(writer, base, location, f"{path}.locations[{index}]", "invalid_location")
                else:
                    reject(writer, base, agent, path + ".bankingAgents", "invalid_agent")
        else:
            emit_channel(writer, base, record, subtype)
    elif family.startswith("opendata-exchange"):
        vet = obj(record.get("vetAmount"))
        writer.add("exchange", {**base, "entity_id": row_id(base, record),
                                "currency": str(record.get("foreignCurrency") or record.get("currency") or ""),
                                "category": str(record.get("transactionCategory") or ""),
                                "audience": str(record.get("targetAudience") or ""),
                                "value": number(record.get("value")),
                                "updated_at": str(record.get("valueUpdateDateTime") or ""),
                                "transaction_type": str(record.get("transactionType") or ""),
                                "delivery": str(record.get("deliveryForeignCurrency") or ""),
                                "range_category": str(record.get("rangeTransactionCategory") or ""),
                                "vet_minimum": number(vet.get("minimum")), "vet_maximum": number(vet.get("maximum")),
                                "vet_prices": json.dumps(vet.get("prices", []), ensure_ascii=False)})
    elif family.startswith("opendata-"):
        society_products = obj(record.get("society")).get("products")
        brand = obj(record.get("participant")).get("brand") or ""
        if isinstance(society_products, list):
            for index, product in enumerate(society_products):
                if isinstance(product, dict) and product:
                    # Scope even a single nested product: sibling society data cannot leak into its rates.
                    society = obj(record.get("society"))
                    emit_product(writer, base, product, brand, f"{path}.society.products[{index}]",
                                 [society.get("cnpjNumber"), society.get("name")])
                else:
                    reject(writer, base, product, f"{path}.society.products[{index}]", "invalid_product")
        else:
            emit_product(writer, base, record, brand, path)


def normalize_capture(lake: Lake, capture: dict) -> tuple[Path, dict, bool]:
    stable = {k: capture.get(k) for k in ("endpoint_id", "objects", "format")}
    stable["identity"] = {k: capture["meta"].get(k) for k in ("group", "company", "cnpj", "family", "url")}
    cache_key = digest(encoded([TRANSFORM_VERSION, stable]))
    root = lake.root / "silver" / f"v{TRANSFORM_VERSION}" / cache_key
    complete_marker = root / "complete.json"
    if complete_marker.exists():
        stats = read_json(complete_marker)
        hashes = read_json(root / "checksums.json")
        for name, sha in hashes.items():
            if digest((root / name).read_bytes()) != sha:
                raise ValueError("Cache silver corrompido: " + name)
        endpoint = pq.read_table(root / "endpoints.parquet").to_pylist()[0]
        meta = capture["meta"]
        endpoint.update(captured_at=meta["captured_at"], status=int(meta.get("status") or 0),
                        complete=meta.get("status") == 200 and not meta.get("error") and not meta.get("truncated"),
                        error=str(meta.get("error") or ""), tls_verified=not bool(meta.get("tls_insecure")),
                        bytes=capture.get("bytes", 0), latency_ms=meta.get("latency_ms"))
        if capture.get("page_log"):
            endpoint["source_sha"] = capture["page_log"][-1]["sha"]
        pq.write_table(pa.Table.from_pylist([endpoint], schema=SCHEMAS["endpoints"]), root / "endpoints.parquet", compression="zstd")
        write_json(root / "checksums.json", {f.name: digest(f.read_bytes()) for f in root.glob("*.parquet")})
        return root, stats, True
    meta = capture["meta"]
    base = {"group_id": str(meta["group"]), "company": str(meta["company"]), "cnpj": str(meta["cnpj"]),
            "family": str(meta["family"]), "family_label": family_label(meta["family"]),
            "segment": segment(meta["family"]), "endpoint_id": capture["endpoint_id"], "source_sha": ""}
    writer = BatchWriter(root)
    n_records, pages, latencies = 0, 0, []
    try:
        for sha in capture["objects"]:
            base["source_sha"] = sha
            envelope = json.loads(lake.get(sha))
            data = envelope.get("data")
            if not isinstance(data, list):
                writer.add("quarantine", {**base, "json_path": "$.data", "reason": "data_not_array",
                                          "raw_json": json.dumps(data, ensure_ascii=False)})
                continue
            for index, record in enumerate(data):
                emit_record(writer, base, record, f"$.data[{index}]")
            n_records += len(data)
            page_log = envelope.get("pages", []) if capture["format"] == "legacy-envelope" else []
            latencies.extend(float(p.get("elapsed_ms") or 0) for p in page_log)
            pages += len(page_log) if page_log else 1
        status = int(meta.get("status") or 0)
        endpoint_sha = capture.get("page_log", [{}])[-1].get("sha", base["source_sha"]) if capture.get("page_log") else base["source_sha"]
        writer.add("endpoints", {**base, "source_sha": endpoint_sha, "url": meta["url"], "captured_at": meta["captured_at"],
                                 "status": status, "records": n_records, "pages": pages,
                                 "complete": status == 200 and not meta.get("truncated") and not meta.get("error"),
                                 "tls_verified": not bool(meta.get("tls_insecure")), "error": str(meta.get("error") or ""),
                                 "bytes": capture.get("bytes", 0),
                                 "latency_ms": sorted(latencies)[len(latencies)//2] if latencies else meta.get("latency_ms")})
    finally:
        writer.close()
    write_json(root / "checksums.json", {f.name: digest(f.read_bytes()) for f in root.glob("*.parquet")})
    write_json(complete_marker, writer.counts)
    return root, writer.counts, False
