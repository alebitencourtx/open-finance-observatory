"""Immutable content-addressed bronze and atomic snapshot publication."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encoded(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def read_json(path: Path):
    return json.loads(path.read_bytes())


def atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with tmp.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def write_json(path: Path, value) -> None:
    atomic_write(path, encoded(value))


class Lake:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @contextlib.contextmanager
    def lock(self):
        path = self.root / ".writer.lock"
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as error:
            raise RuntimeError(f"Outro escritor ativo; verifique {path} antes de remover um lock abandonado") from error
        try:
            os.write(fd, encoded({"pid": os.getpid(), "started_at": utcnow()}))
            os.close(fd)
            yield
        finally:
            path.unlink(missing_ok=True)

    def object_path(self, sha: str) -> Path:
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError("SHA-256 inválido")
        return self.root / "bronze" / "objects" / sha[:2] / f"{sha}.json"

    def put(self, raw: bytes) -> str:
        sha = digest(raw)
        path = self.object_path(sha)
        if not path.exists():
            atomic_write(path, raw)
        return sha

    def get(self, sha: str) -> bytes:
        raw = self.object_path(sha).read_bytes()
        if digest(raw) != sha:
            raise ValueError(f"Falha de integridade no objeto {sha}")
        return raw

    def snapshot(self, snapshot_id: str | None = None) -> dict:
        if snapshot_id is None:
            snapshot_id = read_json(self.root / "latest-bronze.json")["snapshot_id"]
        if Path(snapshot_id).name != snapshot_id or snapshot_id in (".", ".."):
            raise ValueError("Snapshot inválido")
        return read_json(self.root / "snapshots" / snapshot_id / "manifest.json")

    def save_snapshot(self, manifest: dict, publish: bool = True) -> None:
        write_json(self.root / "snapshots" / manifest["snapshot_id"] / "manifest.json", manifest)
        if publish:
            write_json(self.root / "latest-bronze.json", {"snapshot_id": manifest["snapshot_id"]})


def import_legacy(lake: Lake, source: Path) -> dict:
    """Read only the named source; preserve the exact bytes in the new lake."""
    source = source.resolve()
    files = sorted(source.glob("*/*.json"))
    if not files:
        raise ValueError(f"Nenhum envelope bronze em {source}")
    captures = []
    for path in files:
        raw = path.read_bytes()
        envelope = json.loads(raw)
        meta = envelope.get("meta", {})
        if not all(meta.get(k) for k in ("group", "company", "cnpj", "family", "url", "captured_at")):
            raise ValueError(f"Envelope sem identidade completa: {path.name}")
        sha = lake.put(raw)
        captures.append({"endpoint_id": digest(encoded([meta[k] for k in ("group", "cnpj", "family", "url")])),
                         "meta": meta, "objects": [sha], "format": "legacy-envelope",
                         "source_name": str(path.relative_to(source)), "bytes": len(raw)})
    identity = digest(encoded([(c["endpoint_id"], c["objects"]) for c in captures]))
    manifest = {"schema_version": 1, "snapshot_id": f"import-{identity[:20]}", "created_at": utcnow(),
                "origin": "imported_snapshot", "source": str(source), "fingerprint": identity,
                "captures": captures, "directory_evidence": [], "state": "captured"}
    existing = lake.root / "snapshots" / manifest["snapshot_id"] / "manifest.json"
    if existing.exists():
        manifest = read_json(existing)
    lake.save_snapshot(manifest)
    return manifest
