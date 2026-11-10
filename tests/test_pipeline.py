import json
from pathlib import Path

import duckdb
import pyarrow.parquet as pq
import pytest

from observatory.build import build, verify
from observatory.normalize import normalize_capture, number
from observatory.storage import digest, import_legacy, read_json

from conftest import envelope, save_capture, seed


def loan(name="Crédito A", minimum="0.015", maximum="0.04", indexer="PRE_FIXADO"):
    return {"name": name, "interestRates": [{"referentialRateIndexer": indexer,
                                             "minimumRate": minimum, "maximumRate": maximum}]}


def test_import_is_read_only_idempotent_and_byte_exact(lake, legacy_source):
    original = save_capture(legacy_source, "loan", envelope([loan()]))
    before = original.read_bytes()
    first = import_legacy(lake, legacy_source)
    second = import_legacy(lake, legacy_source)
    assert first == second
    assert original.read_bytes() == before
    assert lake.get(first["captures"][0]["objects"][0]) == before
    assert verify(lake)["integrity"] == "passed"


def test_integrity_detects_corruption(lake):
    sha = lake.put(b'{"data":[]}')
    lake.object_path(sha).write_bytes(b'corrupted')
    with pytest.raises(ValueError, match="integridade"):
        lake.get(sha)


def test_writer_lock_excludes_concurrent_writers(lake):
    with lake.lock():
        with pytest.raises(RuntimeError, match="Outro escritor"):
            with lake.lock():
                pass
    with lake.lock():
        pass


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "1.000,50", True, None, {}])
def test_invalid_numbers_never_enter_analytics(value):
    assert number(value) is None


def test_rate_units_and_ranges_are_explicit(lake, legacy_source):
    post = loan("CDI", "0.012", "0.03", "FLUTUANTES_CDI")
    post["interestRates"][0]["rate"] = "1.0"
    manifest = seed(lake, legacy_source, [loan(), post,
                                        loan("High", "0.8", "0.9"), loan("Invertida", "0.04", "0.01")])
    path, _, _ = normalize_capture(lake, manifest["captures"][0])
    rates = {r["name"]: r for r in pq.read_table(path / "rates.parquet").to_pylist()}
    assert rates["Crédito A"]["minimum"] == 1.5
    assert rates["CDI"]["minimum"] == 100
    assert rates["CDI"]["unit"] == "pct_indexer"
    assert rates["CDI"]["effective_minimum"] == 1.2
    assert rates["High"]["minimum"] == 80  # no magnitude-based rescaling to 0.8%
    assert not rates["High"]["valid"]
    assert rates["Invertida"]["reason"] == "inverted_range"


def test_band_medians_do_not_impute_minimum_and_zero_fee_is_preserved(lake, legacy_source):
    record = loan(minimum="0", maximum="0")
    record["interestRates"][0]["applications"] = [{"indexer": {"rate": "0.025"}}, {"indexer": {"rate": "0.05"}}]
    record["fees"] = {"services": [{"name": "Cadastro", "prices": [], "minimum": {"value": "0.00"}, "maximum": {"value": "20"}}]}
    manifest = seed(lake, legacy_source, [record])
    path, _, _ = normalize_capture(lake, manifest["captures"][0])
    rate = pq.read_table(path / "rates.parquet").to_pylist()[0]
    fee = pq.read_table(path / "fees.parquet").to_pylist()[0]
    assert (rate["minimum"], rate["maximum"]) == (0, 0)
    assert not rate["valid"]
    assert fee["minimum"] == 0


def test_nested_products_keep_their_own_rates(lake, legacy_source):
    manifest = seed(lake, legacy_source, [{"society": {"products": [loan("A"), loan("B", "0.02", "0.06")]}}])
    path, _, _ = normalize_capture(lake, manifest["captures"][0])
    rates = pq.read_table(path / "rates.parquet").to_pylist()
    assert sorted((r["name"], r["minimum"]) for r in rates) == [("A", 1.5), ("B", 2)]


def test_channel_explosion_exact_dedup_and_digital_exclusion(lake, legacy_source):
    location = {"postalAddress": {"address": "Rua A", "townName": "São Paulo", "countrySubDivision": "SP"}}
    record = {"bankingAgents": [{"identification": {"corporationName": "Loja", "cnpjNumber": "123"}, "locations": [location, location]}]}
    seed(lake, legacy_source, [record], "channels_banking-agents")
    result = build(lake)
    assert result["deduplicated"]["channels"] == 1
    payload = read_json(lake.root / "gold" / result["build_id"] / "dashboard.json")
    assert payload["group_metrics"][0]["physical_channels"] == 1
    assert payload["group_metrics"][0]["rate_score"] is None
    assert payload["group_metrics"][0]["quality_score"] == 100


def test_product_identity_preserves_issuer_and_payload_distinctions(lake, legacy_source):
    records = [{"investmentType": "CDB", "issuerInstitutionName": "Banco A", "investmentConditions": {"minimumAmount": "100"}},
               {"investmentType": "CDB", "issuerInstitutionName": "Banco A", "investmentConditions": {"minimumAmount": "200"}}]
    seed(lake, legacy_source, records + records[:1], "opendata-investments_bank-fixed-incomes")
    result = build(lake)
    assert result["tables"]["product_catalog"] == 2
    assert result["deduplicated"]["products"] == 1


def test_build_is_reproducible_and_medians_are_per_offer(lake, legacy_source, tmp_path):
    seed(lake, legacy_source, [loan(), loan(), loan("B", ".03", ".06")])
    first = build(lake, output=tmp_path / "dist")
    second = build(lake, output=tmp_path / "dist")
    assert second["reused"] is True
    assert first["build_id"] == second["build_id"]
    payload = read_json(lake.root / "gold" / first["build_id"] / "dashboard.json")
    assert payload["rates_family"][0]["offers"] == 2
    assert payload["rates_family"][0]["median"] == 2.25
    assert next((tmp_path / "dist" / "releases").glob("*/data.js")).read_text(encoding="utf-8").startswith("window.OFB_DATA=")


def test_quality_gate_preserves_previous_publication(lake, legacy_source):
    seed(lake, legacy_source, [loan()])
    first = build(lake)
    previous = read_json(lake.root / "latest.json")
    seed(lake, legacy_source, ["schema drift"])
    with pytest.raises(ValueError, match="Gate de qualidade"):
        build(lake)
    assert read_json(lake.root / "latest.json") == previous
    assert previous["build_id"] == first["build_id"]


def test_http_success_is_distinct_from_presence(lake, legacy_source):
    seed(lake, legacy_source, [], "admin")
    result = build(lake)
    payload = read_json(lake.root / "gold" / result["build_id"] / "dashboard.json")
    group = payload["group_metrics"][0]
    assert group["collection_score"] == 100
    assert group["data_score"] == 0
    assert group["published_families"] == 0
    assert group["quality_score"] == 50
