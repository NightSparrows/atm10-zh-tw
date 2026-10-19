#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""重建繁中包，比對 ZIP 位元組與來源雜湊。"""
import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from build_tw import ROOT, build, sha


def source_snapshot():
    roots = ['src', 'versions', 'installer']
    files = {}
    for folder in roots:
        for path in sorted((ROOT/folder).rglob('*')):
            if path.is_file():
                files[path.relative_to(ROOT).as_posix()] = sha(path.read_bytes())
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--reports', type=Path, default=ROOT/'dist/reports/zh_tw-8.3')
    args = parser.parse_args()
    original = sha(args.output.read_bytes())
    source_hash = sha(args.source.read_bytes())
    before = source_snapshot()
    with tempfile.TemporaryDirectory(prefix='atm10-tw-repeat-', dir=ROOT/'build') as temp:
        target = Path(temp)/args.output.name
        build(args.source, target, Path(temp)/'reports')
        repeated = sha(target.read_bytes())
    after = source_snapshot()
    report = {'zip_identical': original == repeated, 'first_sha256': original,
              'second_sha256': repeated, 'translation_source_unchanged': sha(args.source.read_bytes()) == source_hash,
              'repository_sources_unchanged': before == after, 'repository_source_files': len(before),
              'scope': '同一工具鏈重建。未與上游標準容器的壓縮位元組比對。'}
    args.reports.mkdir(parents=True, exist_ok=True)
    (args.reports/'reproducibility.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not all(report[k] for k in ['zip_identical', 'translation_source_unchanged', 'repository_sources_unchanged']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
