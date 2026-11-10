"""Deterministic builds, quality gates, versioned marts and an offline executive artifact."""
from __future__ import annotations

import json
import shutil
import time
import tempfile
import html
from pathlib import Path

import duckdb

from . import TRANSFORM_VERSION
from .domain import FAMILY_ORDER, SCHEMAS
from .normalize import normalize_capture
from .storage import Lake, atomic_write, digest, encoded, read_json, utcnow, write_json

HERE = Path(__file__).parent


def rows(db, query, params=None):
    result = db.execute(query, params or [])
    names = [c[0] for c in result.description]
    return [dict(zip(names, row)) for row in result.fetchall()]


def quality_checks(db):
    checks = []
    definitions = [
        ("endpoints_present", "error", "Endpoints no instantâneo", "SELECT CASE WHEN count(*)=0 THEN 1 ELSE 0 END FROM endpoints"),
        ("unique_endpoints", "error", "Identidades de endpoint únicas", "SELECT count(*)-count(DISTINCT endpoint_id) FROM endpoints"),
        ("quarantine_empty", "error", "Contratos analíticos mínimos", "SELECT count(*) FROM quarantine"),
        ("rate_references", "error", "Taxas vinculadas às ofertas", "SELECT count(*) FROM rates r ANTI JOIN products p ON r.product_id=p.entity_id"),
        ("fee_references", "error", "Tarifas vinculadas às ofertas", "SELECT count(*) FROM fees f ANTI JOIN products p ON f.product_id=p.entity_id"),
        ("fees_consistency", "warning", "Tarifas comparáveis", "SELECT count(*) FROM fees WHERE NOT valid"),
        ("collections_complete", "warning", "Coletas completas", "SELECT count(*) FROM endpoints WHERE NOT complete"),
        ("tls_verified", "warning", "TLS verificado na origem", "SELECT count(*) FROM endpoints WHERE NOT tls_verified"),
        ("rate_consistency", "warning", "Faixas de taxas consistentes", "SELECT count(*) FROM rates WHERE reason='inverted_range'"),
        ("rate_units", "warning", "Unidades de taxas comparáveis", "SELECT count(*) FROM rates WHERE reason='unit_not_comparable'"),
    ]
    for check_id, severity, label, query in definitions:
        failures = db.execute(query).fetchone()[0]
        checks.append({"id": check_id, "label": label, "severity": severity,
                       "failures": failures, "passed": failures == 0})
    return checks


def build(lake: Lake, snapshot_id: str | None = None, output: Path | None = None, memory="1GB", threads=4) -> dict:
    started = time.perf_counter()
    snapshot = lake.snapshot(snapshot_id)
    if snapshot.get("state") != "captured":
        raise ValueError("Coleta ainda em andamento; retome-a antes de publicar")
    verify(lake, snapshot["snapshot_id"])
    code_hash = digest(b"".join(f.read_bytes() for f in sorted(HERE.rglob("*")) if f.suffix in (".py", ".sql")))
    build_id = digest(encoded([TRANSFORM_VERSION, snapshot["fingerprint"], code_hash]))[:24]
    root = lake.root / "gold" / build_id
    complete = root / "build.json"
    if complete.exists():
        result = read_json(complete)
        for name, sha in read_json(root / "checksums.json").items():
            if digest((root / name).read_bytes()) != sha:
                raise ValueError("Build corrompido: " + name)
        if output:
            render_dashboard(root, output)
        write_json(lake.root / "latest.json", {"build_id": build_id, "snapshot_id": snapshot["snapshot_id"]})
        return {**result, "reused": True}
    root.mkdir(parents=True, exist_ok=True)
    # A failed build may leave files, but never advances the published pointer.
    db_path = root / "warehouse.duckdb"
    db_path.unlink(missing_ok=True)
    normalized, cache_hits, counts = [], 0, dict.fromkeys(SCHEMAS, 0)
    for capture in snapshot["captures"]:
        path, stats, hit = normalize_capture(lake, capture)
        normalized.append(path)
        cache_hits += int(hit)
        for name, count in stats.items():
            counts[name] += count
    if not normalized:
        raise ValueError("Snapshot vazio")
    db = duckdb.connect(str(db_path))
    try:
        db.execute("SET memory_limit = ?", [memory])
        db.execute("SET threads = ?", [max(1, threads)])
        for name in SCHEMAS:
            paths = [str(p / f"{name}.parquet") for p in normalized]
            # Materialize once: repeated dashboard queries never rescan JSON or tiny fragments.
            relation = db.from_parquet(paths, union_by_name=False)
            relation.create_view("incoming", replace=True)
            if name not in ("endpoints", "quarantine"):
                db.execute(f'CREATE TABLE "{name}" AS SELECT * FROM incoming QUALIFY row_number() OVER(PARTITION BY entity_id ORDER BY endpoint_id,source_sha)=1')
            else:
                db.execute(f'CREATE TABLE "{name}" AS SELECT * FROM incoming')
        db.execute("CREATE TABLE dim_groups(group_id VARCHAR PRIMARY KEY, label VARCHAR)")
        groups = {c["meta"]["group"]: c["meta"].get("group_label", c["meta"]["group"]) for c in snapshot["captures"]}
        db.executemany("INSERT INTO dim_groups VALUES (?, ?)", sorted(groups.items()))
        db.execute("CREATE TABLE dim_families(family_label VARCHAR PRIMARY KEY)")
        db.executemany("INSERT INTO dim_families VALUES (?)", [(f,) for f in FAMILY_ORDER])
        checks = quality_checks(db)
        write_json(root / "quality.json", checks)
        if any(not c["passed"] and c["severity"] == "error" for c in checks):
            raise ValueError(f"Gate de qualidade reprovado. Evidências: {root / 'quality.json'}")
        db.execute((HERE / "sql" / "marts.sql").read_text(encoding="utf-8"))
        tables = ["group_metrics", "coverage", "rates_family", "channels_uf", "channels_type", "products_family",
                  "fees_family", "companies", "product_catalog", "endpoints", "rate_offers", "exchange"]
        table_counts = {}
        for table in tables:
            target = str(root / f"{table}.parquet").replace("'", "''")
            db.execute(f"COPY (SELECT * FROM {table}) TO '{target}' (FORMAT PARQUET, COMPRESSION ZSTD)")
            table_counts[table] = db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        payload = {table: rows(db, f"SELECT * FROM {table} ORDER BY ALL") for table in tables if table != "rate_offers"}
        payload["rate_exclusions"] = rows(db, "SELECT group_id,reason,count(*) AS count FROM rates WHERE NOT valid GROUP BY ALL ORDER BY ALL")
        payload["fee_exclusions"] = rows(db, "SELECT group_id,reason,count(*) AS count FROM fees WHERE NOT valid GROUP BY ALL ORDER BY ALL")
        payload["quality"] = checks
        payload["families"] = FAMILY_ORDER
        payload["meta"] = {"snapshot_id": snapshot["snapshot_id"], "build_id": build_id,
                           "transform_version": TRANSFORM_VERSION, "code_hash": code_hash, "generated_at": utcnow(),
                           "origin": snapshot["origin"], "captured_from": min(c["meta"]["captured_at"] for c in snapshot["captures"]),
                           "captured_to": max(c["meta"]["captured_at"] for c in snapshot["captures"]),
                           "bronze_bytes": sum(c.get("bytes", 0) for c in snapshot["captures"]),
                           "source_fingerprint": snapshot["fingerprint"], "directory_evidence": snapshot.get("directory_evidence", []),
                           "quality_state": "attention" if any(not c["passed"] for c in checks) else "passed",
                           "history_available": False}
        write_json(root / "dashboard.json", payload)
        deduplicated = {name: counts[name] - db.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
                        for name in SCHEMAS if name not in ("endpoints", "quarantine")}
        result = {"build_id": build_id, "snapshot_id": snapshot["snapshot_id"], "transform_version": TRANSFORM_VERSION,
                  "completed_at": utcnow(), "duration_seconds": round(time.perf_counter()-started, 3),
                  "input_bytes": payload["meta"]["bronze_bytes"], "endpoints": len(normalized),
                  "transform_cache_hits": cache_hits, "input_rows": counts, "deduplicated": deduplicated,
                  "tables": table_counts, "quality": checks, "reused": False}
    finally:
        db.close()
    write_json(root / "execution.json", result)
    if output:
        render_dashboard(root, output)
    write_json(root / "checksums.json", {f.name: digest(f.read_bytes()) for f in root.iterdir()
                                        if f.is_file() and f.name not in ("build.json", "checksums.json")})
    write_json(complete, result)
    write_json(lake.root / "latest.json", {"build_id": build_id, "snapshot_id": snapshot["snapshot_id"]})
    return result


def render_dashboard(build_root: Path, output: Path):
    """Stage a complete immutable release; only the entry point commits publication."""
    output.mkdir(parents=True, exist_ok=True)
    with Lake(output).lock():
        releases = output / "releases"
        releases.mkdir(exist_ok=True)
        payload = (build_root / "dashboard.json").read_bytes()
        from .documentation import generate
        with tempfile.TemporaryDirectory(prefix=".stage-", dir=releases) as temporary:
            stage = Path(temporary)
            for asset in (HERE / "web").iterdir():
                if asset.is_file():
                    shutil.copyfile(asset, stage / asset.name)
            atomic_write(stage / "data.js", b"window.OFB_DATA=" + payload + b";\n")
            atomic_write(stage / "dashboard.json", payload)
            generate(build_root, stage / "manual.html")
            release_id = digest(b"".join(f.read_bytes() for f in sorted(stage.iterdir())))[:24]
            destination = releases / release_id
            if not destination.exists():
                stage.rename(destination)
                stage.mkdir()  # TemporaryDirectory owns this path, not the committed release.
            target = "releases/" + release_id + "/index.html"
            entry = '<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Observatory</title><meta http-equiv="refresh" content="0;url=' + target + '"><a href="' + target + '">Abrir dashboard executivo</a><script>location.replace("' + target + '"+location.hash)</script></html>'
            # Stable documentation URL survives replacement of older Pages releases.
            atomic_write(output / "documentacao.html", (destination / "manual.html").read_bytes())
            atomic_write(output / "manual.html", (destination / "manual.html").read_bytes())
            atomic_write(output / "404.html", (HERE / "web" / "404.html").read_bytes())
            atomic_write(output / "dashboard.json", payload)
            atomic_write(output / "index.html", entry.encode())


def verify(lake: Lake, snapshot_id: str | None = None):
    snapshot = lake.snapshot(snapshot_id)
    shas = {sha for c in snapshot["captures"] for sha in c["objects"]}
    shas.update(p["sha"] for c in snapshot["captures"] for p in c.get("page_log", []))
    for sha in shas:
        lake.get(sha)
    return {"snapshot_id": snapshot["snapshot_id"], "objects_verified": len(shas), "integrity": "passed"}
