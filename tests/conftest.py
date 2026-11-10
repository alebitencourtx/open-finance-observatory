import json

import pytest

from observatory.storage import Lake, import_legacy


@pytest.fixture
def lake(tmp_path):
    return Lake(tmp_path / "lake")


@pytest.fixture
def legacy_source(tmp_path):
    path = tmp_path / "original" / "santander"
    path.mkdir(parents=True)
    return path.parent


def envelope(data, family="opendata-loans_personal-loans", **overrides):
    return {"meta": {"group": "santander", "group_label": "Santander", "company": "Banco de teste",
                     "cnpj": "00000000000001", "family": family, "url": f"https://public.example/{family}",
                     "captured_at": "2026-11-10T03:00:00+00:00", "status": 200, "truncated": False,
                     "error": "", **overrides}, "pages": [{"elapsed_ms": 50}], "data": data}


def save_capture(source, name, payload):
    path = source / "santander" / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def seed(lake, source, data, family="opendata-loans_personal-loans"):
    save_capture(source, "capture", envelope(data, family))
    return import_legacy(lake, source)
