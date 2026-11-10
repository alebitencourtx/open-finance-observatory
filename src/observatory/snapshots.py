"""Portable, verified bronze archives; derived DuckDB files can be rebuilt."""
from pathlib import Path, PurePosixPath
import json
import os
import tempfile
import zipfile

from .storage import Lake, digest, encoded


def archive(lake: Lake, destination: Path):
    manifest = dict(lake.snapshot())
    if manifest.get('state') != 'captured':
        raise ValueError('Snapshot ainda aberto')
    manifest.pop('source', None)  # Machine-specific import path is not portable provenance.
    shas = {sha for c in manifest['captures'] for sha in c['objects']}
    shas.update(p['sha'] for c in manifest['captures'] for p in c.get('page_log', []))
    shas.update(e['directory_sha'] for e in manifest.get('directory_evidence', []) if e.get('directory_sha'))
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=destination.parent, suffix='.zip')
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as out:
            out.writestr('manifest.json', encoded(manifest))
            for sha in sorted(shas):
                out.writestr('objects/' + sha + '.json', lake.get(sha))
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {'snapshot_id': manifest['snapshot_id'], 'sha256': digest(destination.read_bytes()), 'objects': len(shas)}


def restore(lake: Lake, source: Path):
    with zipfile.ZipFile(source) as package:
        names = package.namelist()
        if len(names) != len(set(names)) or 'manifest.json' not in names:
            raise ValueError('Arquivo de snapshot inválido')
        # Do not extract arbitrary paths supplied by a ZIP.
        for info in package.infolist():
            path = PurePosixPath(info.filename)
            if info.file_size > 512 * 1024 * 1024 or (info.filename != 'manifest.json' and
                    (len(path.parts) != 2 or path.parts[0] != 'objects' or not path.name.endswith('.json'))):
                raise ValueError('Entrada não permitida no snapshot')
        manifest = json.loads(package.read('manifest.json'))
        snapshot_id = manifest['snapshot_id']
        if manifest.get('state') != 'captured' or Path(snapshot_id).name != snapshot_id or snapshot_id in ('.', '..'):
            raise ValueError('Manifesto inválido')
        for name in names:
            if name == 'manifest.json':
                continue
            sha = PurePosixPath(name).stem
            lake.object_path(sha)  # Validate the identifier before writing anything.
            raw = package.read(name)
            if digest(raw) != sha:
                raise ValueError('Hash do pacote divergente')
        required = {sha for c in manifest['captures'] for sha in c['objects']}
        required.update(p['sha'] for c in manifest['captures'] for p in c.get('page_log', []))
        required.update(e['directory_sha'] for e in manifest.get('directory_evidence', []) if e.get('directory_sha'))
        if not all('objects/' + sha + '.json' in names for sha in required):
            raise ValueError('Objeto ausente no pacote')
        for name in names:
            if name != 'manifest.json':
                lake.put(package.read(name))
        lake.save_snapshot(manifest)
    return manifest


def publication_check(payload, baseline=None):
    """Remote collection must remain useful before replacing an approved publication."""
    groups = {g['group_id']: g for g in payload['group_metrics']}
    if set(groups) != {'santander', 'itau', 'bradesco'}:
        raise ValueError('Perímetro incompleto: exigidos os três grupos')
    for group in groups.values():
        if group['collection_score'] is None or group['collection_score'] < 90:
            raise ValueError('Menos de 90% de coleta completa: ' + group['group_id'])
        if not group['products'] or not group['physical_channels']:
            raise ValueError('Grupo sem produtos ou rede: ' + group['group_id'])
    if baseline:
        old = {g['group_id']: g for g in baseline['group_metrics']}
        for key, group in groups.items():
            for metric in ('endpoints', 'products', 'physical_channels'):
                if key in old and group[metric] < .9 * old[key][metric]:
                    raise ValueError('Queda superior a 10% exige investigação: ' + key + '/' + metric)
    return {'approved': True, 'groups': len(groups), 'minimum_complete_pct': 90,
            'maximum_drop_pct': 10}
