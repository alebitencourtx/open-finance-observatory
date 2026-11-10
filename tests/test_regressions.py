import copy
import json
from unittest.mock import patch

import httpx
import pyarrow.parquet as pq
import pytest

from conftest import seed
from test_collect import TARGET
from test_pipeline import loan
from observatory.build import build
from observatory.collect import Collector, Policy
from observatory.normalize import normalize_capture
from observatory.storage import digest, encoded, read_json


@pytest.mark.asyncio
@pytest.mark.parametrize('payload', [
    {'data': [{}, {}], 'meta': {'totalPages': 1, 'totalRecords': 1}},
    {'data': [], 'meta': {'totalPages': 3}},
    {'data': [{}], 'meta': ['invalid']},
    {'data': [{}], 'meta': {'totalPages': -1}},
    {'data': [{}], 'meta': {'totalPages': 1.5}},
])
async def test_pagination_contract_failures_are_isolated(lake, payload):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))) as client:
        result = await Collector(lake, Policy(interval=0, retries=0)).capture(client, TARGET)
    assert result['meta']['error']
    assert result['page_log']


@pytest.mark.asyncio
async def test_resume_final_checkpoint_closes_without_network(lake):
    capture = {'endpoint_id': TARGET['endpoint_id'], 'meta': {**TARGET, 'status': 200}, 'objects': []}
    catalog = {'targets': [TARGET], 'evidence': []}
    lake.save_snapshot({'snapshot_id': 'interrupted', 'state': 'collecting', 'captures': [capture],
                        'catalog_fingerprint': digest(encoded(catalog['targets']))}, publish=False)
    result = await Collector(lake).run(catalog, 'interrupted')
    assert result['state'] == 'captured'
    assert result['fingerprint']
    assert read_json(lake.root / 'latest-bronze.json')['snapshot_id'] == 'interrupted'


@pytest.mark.parametrize('record', [{}, {'society': {'products': [42]}}, {'interestRates': {} }])
def test_malformed_products_are_quarantined(lake, legacy_source, record):
    manifest = seed(lake, legacy_source, [record])
    path, _, _ = normalize_capture(lake, manifest['captures'][0])
    assert pq.read_table(path / 'quarantine.parquet').num_rows == 1
    with pytest.raises(ValueError, match='Gate'):
        build(lake)


def test_repeated_products_do_not_repeat_fees(lake, legacy_source):
    record = loan()
    record['fees'] = {'services': [{'name': 'Cadastro', 'prices': [], 'minimum': {'value': '1'}, 'maximum': {'value': '2'}}]}
    seed(lake, legacy_source, [record, record])
    result = build(lake)
    assert result['deduplicated']['fees'] == 1
    assert result['deduplicated']['rates'] == 1


def test_inverted_fees_are_preserved_but_excluded(lake, legacy_source):
    record = loan()
    record['fees'] = {'services': [{'name': 'Cadastro', 'prices': [], 'minimum': {'value': '10'}, 'maximum': {'value': '2'}}]}
    seed(lake, legacy_source, [record])
    result = build(lake)
    payload = read_json(lake.root / 'gold' / result['build_id'] / 'dashboard.json')
    assert payload['fees_family'] == []
    assert next(c for c in result['quality'] if c['id'] == 'fees_consistency')['failures'] == 1


def test_post_effective_inversion_is_excluded(lake, legacy_source):
    record = loan(minimum='.04', maximum='.01', indexer='FLUTUANTES_CDI')
    record['interestRates'][0]['rate'] = '1.0'
    manifest = seed(lake, legacy_source, [record])
    path, _, _ = normalize_capture(lake, manifest['captures'][0])
    rate = pq.read_table(path / 'rates.parquet').to_pylist()[0]
    assert not rate['valid']
    assert rate['reason'] == 'inverted_range'


def test_vet_keeps_distribution_and_context(lake, legacy_source):
    record = {'foreignCurrency': 'EUR', 'transactionType': 'COMPRA', 'deliveryForeignCurrency': 'ESPECIE',
              'vetAmount': {'minimum': '5.0', 'maximum': '6.0', 'prices': [{'interval': '1_FAIXA', 'value': '5.2'}]}}
    manifest = seed(lake, legacy_source, [record], 'opendata-exchange_vet-values')
    path, _, _ = normalize_capture(lake, manifest['captures'][0])
    row = pq.read_table(path / 'exchange.parquet').to_pylist()[0]
    assert row['value'] is None
    assert (row['vet_minimum'], row['vet_maximum'], row['transaction_type']) == (5, 6, 'COMPRA')
    assert json.loads(row['vet_prices'])[0]['value'] == '5.2'


def test_cache_reuses_content_without_stale_capture_metadata(lake, legacy_source):
    manifest = seed(lake, legacy_source, [loan()])
    first = manifest['captures'][0]
    normalize_capture(lake, first)
    second = copy.deepcopy(first)
    second['meta']['captured_at'] = '2026-11-11T00:00:00+00:00'
    path, _, hit = normalize_capture(lake, second)
    assert hit
    assert pq.read_table(path / 'endpoints.parquet').to_pylist()[0]['captured_at'] == second['meta']['captured_at']
    (path / 'products.parquet').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='corrompido'):
        normalize_capture(lake, second)


def test_failed_manual_keeps_published_entry_and_release(lake, legacy_source, tmp_path):
    seed(lake, legacy_source, [loan()])
    output = tmp_path / 'site'
    first = build(lake, output=output)
    before = (output / 'index.html').read_bytes()
    releases = list((output / 'releases').iterdir())
    seed(lake, legacy_source, [loan('New')])
    with patch('observatory.documentation.generate', side_effect=RuntimeError('injected')):
        with pytest.raises(RuntimeError):
            build(lake, output=output)
    assert (output / 'index.html').read_bytes() == before
    assert list((output / 'releases').iterdir()) == releases
    assert read_json(lake.root / 'latest.json')['build_id'] == first['build_id']


def test_reused_build_checks_bronze_and_gold(lake, legacy_source):
    manifest = seed(lake, legacy_source, [loan()])
    result = build(lake)
    gold = lake.root / 'gold' / result['build_id']
    (gold / 'products_family.parquet').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='corrompido'):
        build(lake)
    lake.object_path(manifest['captures'][0]['objects'][0]).write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='integridade'):
        build(lake)


def test_manual_origin_and_date_follow_snapshot(lake, legacy_source, tmp_path):
    seed(lake, legacy_source, [loan()])
    build(lake, output=tmp_path / 'site')
    manual = (tmp_path / 'site' / 'manual.html').read_text(encoding='utf-8')
    assert 'DADOS REAIS · 2026-11-10' in manual
    assert 'Replay de bronze importado' in manual
