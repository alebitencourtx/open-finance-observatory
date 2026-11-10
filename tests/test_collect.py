import asyncio
import json

import httpx
import pytest

from observatory.collect import Collector, Policy, discover, retry_after, validate_url
from observatory.storage import digest, encoded, write_json


TARGET = {"endpoint_id": "example", "group": "santander", "group_label": "Santander", "company": "Teste",
          "cnpj": "1", "family": "opendata-loans_personal-loans", "url": "https://api.example/loans"}


async def capture(lake, handler, **policy):
    collector = Collector(lake, Policy(interval=0, retries=0, **policy))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        return await collector.capture(client, TARGET)


@pytest.mark.asyncio
async def test_pagination_uses_full_page_hash_not_first_record(lake):
    def handler(request):
        page = int(request.url.params["page"])
        return httpx.Response(200, json={"data": [{"name": "same first"}, {"name": str(page)}], "meta": {"totalPages": 2, "totalRecords": 4}})
    result = await capture(lake, handler)
    assert len(result["objects"]) == 2
    assert result["meta"]["records"] == 4
    assert result["meta"]["error"] == ""


@pytest.mark.asyncio
async def test_repeated_page_is_incomplete_without_duplicate_data(lake):
    result = await capture(lake, lambda _: httpx.Response(200, json={"data": [{"name": "A"}], "meta": {"totalPages": 5}}))
    assert result["meta"]["error"] == "pagination_repeated"
    assert result["meta"]["truncated"]
    assert len(result["objects"]) == 1


@pytest.mark.asyncio
async def test_second_page_http_failure_preserves_first_and_raw_error(lake):
    def handler(request):
        return httpx.Response(200, json={"data": [{"name": "A"}], "meta": {"totalPages": 2}}) if request.url.params["page"] == "1" else httpx.Response(403, text="Forbidden")
    result = await capture(lake, handler)
    assert result["meta"]["status"] == 403
    assert result["meta"]["truncated"]
    assert result["meta"]["records"] == 1
    assert lake.get(result["page_log"][-1]["sha"]) == b"Forbidden"


@pytest.mark.asyncio
async def test_empty_data_and_reported_total_mismatch(lake):
    result = await capture(lake, lambda _: httpx.Response(200, json={"data": [], "meta": {"totalRecords": 10}}))
    assert result["meta"]["error"] == "reported_total_mismatch"


@pytest.mark.asyncio
async def test_page_limit_is_not_success(lake):
    result = await capture(lake, lambda _: httpx.Response(200, json={"data": [{"name": "A"}]}), max_pages=1)
    assert result["meta"]["error"] == "page_limit"


@pytest.mark.asyncio
async def test_response_size_limit(lake):
    result = await capture(lake, lambda _: httpx.Response(200, text="x"*100), max_bytes=20)
    assert result["meta"]["error"] == "response_size_limit"


@pytest.mark.asyncio
async def test_retry_on_429_but_not_403(lake):
    count = 0
    def handler(request):
        nonlocal count
        count += 1
        return httpx.Response(429, headers={"Retry-After": "0"}) if count == 1 else httpx.Response(200, json={"data": [], "meta": {"totalPages": 1}})
    collector = Collector(lake, Policy(interval=0, retries=2))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collector.capture(client, TARGET)
    assert count == 2
    assert result["meta"]["status"] == 200
    count = 0
    def forbidden(_):
        nonlocal count
        count += 1
        return httpx.Response(403)
    async with httpx.AsyncClient(transport=httpx.MockTransport(forbidden)) as client:
        result = await collector.capture(client, TARGET)
    assert count == 1


@pytest.mark.asyncio
async def test_bounded_workers_and_resume_skip_complete(lake):
    active = peak = calls = 0
    async def handler(request):
        nonlocal active, peak, calls
        active += 1; calls += 1; peak = max(active, peak)
        await asyncio.sleep(.005)
        active -= 1
        return httpx.Response(200, json={"data": [], "meta": {"totalPages": 1}})
    catalog = {"targets": [{**TARGET, "endpoint_id": str(i), "url": f"https://api.example/{i}"} for i in range(5)], "evidence": []}
    collector = Collector(lake, Policy(concurrency=3, per_host=2, interval=0), httpx.MockTransport(handler))
    first = await collector.run(catalog)
    second = await collector.run(catalog, first["snapshot_id"])
    assert calls == 5
    assert peak <= 2
    assert len(second["captures"]) == 5


@pytest.mark.parametrize("url", ["http://public.example", "https://localhost/a", "https://127.0.0.1", "https://user:secret@example.com", "https://evil.internal", "https://10.0.0.1"])
def test_https_and_public_host_policy(url):
    with pytest.raises(ValueError):
        validate_url(url)


def test_retry_after_is_capped():
    assert retry_after("3600", 30) == 30
    assert retry_after("invalid", 30) is None


def test_discovery_domain_boundaries_and_ambiguity(lake, tmp_path):
    def org(cnpj, host):
        return {"Status": "Active", "RegistrationNumber": cnpj, "OrganisationName": "Test", "AuthorisationServers": [
            {"ApiResources": [{"ApiFamilyType": "opendata-loans_personal-loans", "ApiVersion": "1.0.0", "ApiDiscoveryEndpoints": [{"ApiEndpoint": f"https://{host}/loans"}]}]}]}
    groups = tmp_path / "groups.json"
    directory = tmp_path / "directory.json"
    write_json(groups, {"santander": {"label": "Santander", "domains": ["santander.com.br"], "cnpjs": []}})
    write_json(directory, [org("1", "api.santander.com.br"), org("2", "evil-santander.com.br"), org("3", "santander.com.br.evil.com")])
    result = discover(lake, groups, directory)
    assert len(result["targets"]) == 1
    assert result["evidence"][0]["method"] == "api_domain"


@pytest.mark.asyncio
async def test_retry_closed_snapshot_creates_new_revision(lake):
    from observatory.storage import read_json
    catalog = {"targets": [TARGET], "evidence": []}
    first = await Collector(lake, Policy(interval=0, retries=0), httpx.MockTransport(lambda _: httpx.Response(403))).run(catalog)
    before = read_json(lake.root / "snapshots" / first["snapshot_id"] / "manifest.json")
    second = await Collector(lake, Policy(interval=0, retries=0), httpx.MockTransport(lambda _: httpx.Response(200,json={"data": []}))).run(catalog, first["snapshot_id"])
    assert second["snapshot_id"] != first["snapshot_id"]
    assert second["parent_snapshot"] == first["snapshot_id"]
    assert read_json(lake.root / "snapshots" / first["snapshot_id"] / "manifest.json") == before


@pytest.mark.asyncio
async def test_record_limit_applies_even_on_last_page(lake):
    result = await capture(lake, lambda _: httpx.Response(200,json={"data": [{},{}], "meta": {"totalPages": 1}}),max_records=1)
    assert result["meta"]["error"] == "record_limit"


@pytest.mark.asyncio
async def test_failed_endpoint_preserves_error_body_lineage(lake):
    import pyarrow.parquet as pq
    from observatory.normalize import normalize_capture
    result = await capture(lake, lambda _: httpx.Response(403,text="Forbidden"))
    path, _, _ = normalize_capture(lake,result)
    endpoint = pq.read_table(path / "endpoints.parquet").to_pylist()[0]
    assert endpoint["source_sha"] == result["page_log"][0]["sha"]
    assert lake.get(endpoint["source_sha"]) == b"Forbidden"


@pytest.mark.asyncio
@pytest.mark.parametrize('family,data,total,grain', [
    ('opendata-insurance_personals', [{'society': {'products': [{'name': 'a'}, {'name': 'b'}]}}], 2, 'products'),
    ('channels_banking-agents', [{'bankingAgents': [{'locations': [{}, {}]}]}], 2, 'locations'),
])
async def test_pagination_reconciles_nested_records(lake, family, data, total, grain):
    collector = Collector(lake, Policy(interval=0, retries=0))
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={
            'data': data, 'meta': {'totalPages': 1, 'totalRecords': total}}))) as client:
        result = await collector.capture(client, {**TARGET, 'family': family})
    assert result['meta']['error'] == ''
    assert result['meta']['records'] == 1
    assert grain in result['meta']['reported_count_grains']


@pytest.mark.asyncio
async def test_itau_branches_scoped_page_totals_still_require_all_pages(lake):
    def handler(request):
        page = int(request.url.params['page'])
        data = [{'name': 'A'}, {'name': 'B'}] if page == 1 else [{'name': 'C'}]
        return httpx.Response(200, json={'data': data, 'meta': {'totalRecords': len(data), 'totalPages': 2}})
    collector = Collector(lake, Policy(interval=0, retries=0))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collector.capture(client, {**TARGET, 'family': 'channels_branches',
                         'url': 'https://api.itau/open-banking/channels/v2/branches'})
    assert result['meta']['error'] == ''
    assert result['meta']['records'] == 3
    assert result['meta']['reported_total_scope'] == 'page'
