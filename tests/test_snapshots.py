import copy
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest

from conftest import seed
from observatory.snapshots import archive, publication_check, restore
from observatory.storage import Lake


def test_portable_archive_preserves_exact_objects_and_ignores_unreferenced_history(lake, legacy_source, tmp_path):
    original = seed(lake, legacy_source, [{'name': 'first'}])
    old_sha = original['captures'][0]['objects'][0]
    current = seed(lake, legacy_source, [{'name': 'second'}])
    package = tmp_path / 'snapshot.zip'
    archive(lake, package)
    with zipfile.ZipFile(package) as source:
        assert 'objects/' + old_sha + '.json' not in source.namelist()
    target = Lake(tmp_path / 'restore')
    restored = restore(target, package)
    assert restored['snapshot_id'] == current['snapshot_id']
    sha = restored['captures'][0]['objects'][0]
    assert target.get(sha) == lake.get(sha)
    assert 'source' not in restored


@pytest.mark.parametrize('entry', ['../escape.json', 'objects/../../escape.json', 'objects/not-a-sha.json'])
def test_restore_rejects_untrusted_paths_without_publishing(lake, tmp_path, entry):
    path = tmp_path / 'bad.zip'
    with zipfile.ZipFile(path, 'w') as out:
        out.writestr('manifest.json', json.dumps({'snapshot_id': 'x', 'state': 'captured', 'captures': []}))
        out.writestr(entry, '{}')
    with pytest.raises(ValueError):
        restore(lake, path)
    assert not (lake.root / 'latest-bronze.json').exists()


def payload():
    return {'group_metrics': [{'group_id': key, 'collection_score': 95, 'products': 100,
                              'physical_channels': 100, 'endpoints': 100}
                             for key in ('santander', 'itau', 'bradesco')]}


def test_publication_blocks_loss_of_scope_and_massive_drop():
    baseline = payload()
    assert publication_check(baseline, baseline)['approved']
    incomplete = payload()
    incomplete['group_metrics'].pop()
    with pytest.raises(ValueError, match='Perímetro'):
        publication_check(incomplete)
    for key, value in [('collection_score', 89), ('products', 0), ('endpoints', 89)]:
        candidate = copy.deepcopy(baseline)
        candidate['group_metrics'][0][key] = value
        with pytest.raises(ValueError):
            publication_check(candidate, baseline)


def cloud_module():
    spec = importlib.util.spec_from_file_location('cloud_pipeline', Path(__file__).parents[1] / 'scripts/cloud_pipeline.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_promotion_keeps_current_and_previous_without_touching_other_releases(monkeypatch):
    module = cloud_module()
    records = [{'tag_name': 'extraction-' + str(i), 'draft': False, 'published_at': f'2026-11-{i:02}', 'id': i}
               for i in range(1, 5)]
    calls = []
    monkeypatch.setattr(module, 'gh', lambda *args: calls.append(args))
    monkeypatch.setattr(module, 'releases', lambda: records)
    module.promote('extraction-4')
    deletions = [args[2] for args in calls if args[:2] == ('release', 'delete')]
    assert deletions == ['extraction-2', 'extraction-1']


def test_unconfirmed_promotion_never_prunes_and_discard_only_deletes_drafts(monkeypatch):
    module = cloud_module()
    calls = []
    monkeypatch.setattr(module, 'gh', lambda *args: calls.append(args))
    monkeypatch.setattr(module, 'releases', lambda: [{'tag_name': 'extraction-old', 'draft': False, 'published_at': '2026', 'id': 1}])
    with pytest.raises(ValueError):
        module.promote('extraction-missing')
    module.discard('extraction-old')
    assert not any(args[:2] == ('release', 'delete') for args in calls)
