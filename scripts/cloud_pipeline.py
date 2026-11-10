"""Actions entry point: prepare a candidate, then promote only after Pages succeeds."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import zipfile

from observatory.snapshots import archive, publication_check, restore
from observatory.storage import Lake, digest, read_json, write_json

PREFIX = 'extraction-'


def gh(*args):
    return subprocess.run(['gh', *args], check=True, capture_output=True, text=True).stdout


def releases():
    pages = json.loads(gh('api', '--paginate', '--slurp', 'repos/{owner}/{repo}/releases?per_page=100'))
    return [r for page in pages for r in page if r['tag_name'].startswith(PREFIX)]


def approved(items):
    # Use publication time: release tag target dates need not be ordered.
    return sorted((r for r in items if not r['draft']), key=lambda r: (r['published_at'], r['id']), reverse=True)


def output(key, value):
    if os.getenv('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
            stream.write(f'{key}={value}\n')
    print(f'{key}={value}', flush=True)


def prepare(refresh=False):
    from observatory.build import build
    from observatory.collect import Collector, Policy, discover
    work = Path('.runtime')
    work.mkdir(exist_ok=True)
    current = Lake(work / 'current')
    history = approved(releases())
    if history:
        gh('release', 'download', history[0]['tag_name'], '--pattern', 'snapshot.zip', '--pattern', 'SHA256SUMS', '--dir', str(work), '--clobber')
        if digest((work / 'snapshot.zip').read_bytes()) != (work / 'SHA256SUMS').read_text().split()[0]:
            raise ValueError('Checksum do snapshot remoto divergente')
        restore(current, work / 'snapshot.zip')
    else:
        # Explicit bootstrap only; a failed download must never silently restore stale data.
        package = Path('datasets/bronze-2026-11-10.zip')
        if digest(package.read_bytes()) != Path('datasets/SHA256SUMS').read_text().split()[0]:
            raise ValueError('Checksum do bootstrap divergente')
        with zipfile.ZipFile(package) as source:
            source.extractall(work / 'bootstrap')
        from observatory.storage import import_legacy
        import_legacy(current, work / 'bootstrap')
    baseline_result = build(current)
    baseline = read_json(current.root / 'gold' / baseline_result['build_id'] / 'dashboard.json')
    lake = current
    if refresh:
        lake = Lake(work / 'candidate')
        catalog = discover(lake, Path('config/groups.json'))
        asyncio.run(Collector(lake, Policy()).run(catalog))
    result = build(lake, output=Path('site'))
    payload = read_json(lake.root / 'gold' / result['build_id'] / 'dashboard.json')
    gate = publication_check(payload, baseline if refresh else None)
    write_json(Path('site/publication.json'), {**gate, 'snapshot_id': payload['meta']['snapshot_id'],
                                             'origin': payload['meta']['origin'], 'retention': 2})
    Path('site/.nojekyll').touch()
    candidate = ''
    if refresh or not history:
        candidate = PREFIX + os.environ.get('GITHUB_RUN_ID', 'local') + '-' + os.environ.get('GITHUB_RUN_ATTEMPT', '1')
        info = archive(lake, work / 'snapshot.zip')
        (work / 'SHA256SUMS').write_text(info['sha256'] + '  snapshot.zip\n')
        notes = work / 'notes.md'
        notes.write_text('Extração aprovada pelos gates analíticos e de publicação.\n\nSnapshot: ' + info['snapshot_id'] + '\n\nRetenção: atual e anterior. Bronze e manifesto permitem reconstruir o DuckDB.\n', encoding='utf-8')
        output('candidate_tag', candidate)
        gh('release', 'create', candidate, str(work / 'snapshot.zip'), str(work / 'SHA256SUMS'),
           '--draft', '--target', os.environ.get('GITHUB_SHA', 'main'), '--title', 'Extração ' + info['snapshot_id'], '--notes-file', str(notes))
    output('candidate_tag', candidate)


def promote(tag):
    if not tag.startswith(PREFIX):
        raise ValueError('Tag fora do escopo de extrações')
    gh('release', 'edit', tag, '--draft=false', '--latest=false')
    history = approved(releases())
    if not any(r['tag_name'] == tag for r in history[:2]):
        raise ValueError('Nova extração não confirmada; retenção não executada')
    for old in history[2:]:
        gh('release', 'delete', old['tag_name'], '--yes', '--cleanup-tag')


def discard(tag):
    for release in releases():
        if release['tag_name'] == tag and release['draft']:
            gh('release', 'delete', tag, '--yes', '--cleanup-tag')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare', 'promote', 'discard'])
    parser.add_argument('--tag', default='')
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.refresh)
    elif args.command == 'promote':
        promote(args.tag)
    else:
        discard(args.tag)
