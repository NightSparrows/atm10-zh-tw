#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""依官方原始碼索引核對任務圖片，不讀取遊戲環境。"""
import re
from collections import Counter, defaultdict
from pathlib import Path

from formats import json_load, snbt_leaves

BASELINE = Path(__file__).resolve().parents[2] / 'src/zh_tw/quest_images.json'
IMAGE = re.compile(r'\{image:([^\s}]+)[^}]*\}')


def load_baseline():
    data = json_load(BASELINE.read_bytes())
    if data.get('pack_version') != '8.3' or not data.get('commit') or not data.get('pack_assets'):
        raise ValueError('缺少 ATM10 8.3 任務圖片基準')
    return data


def repair_for(rel, path, value, baseline=None):
    data = load_baseline() if baseline is None else baseline
    for entry in data['repairs']:
        if entry['file'] == rel and entry['field'] == list(path):
            if value != entry['source']:
                raise ValueError(f'{rel}:{path}：過期圖片引用的來源已改變')
            return entry
    return None


def audit(source, target, baseline=None):
    from build_tw import rename
    data = load_baseline() if baseline is None else baseline
    errors, repairs = [], []
    for entry in data['repairs']:
        rel, field = entry['file'], tuple(entry['field'])
        if rel not in source or rename(rel) not in target:
            errors.append(f'{rel}：圖片修正缺少來源或產物')
            continue
        before = {p: t.value for p, t in snbt_leaves(source[rel].decode('utf-8-sig'))}
        after = {p: t.value for p, t in snbt_leaves(target[rename(rel)].decode('utf-8-sig'))}
        if before.get(field) != entry['source'] or after.get(field) != entry['replacement']:
            errors.append(f'{rel}:{field}：圖片修正未依指定原文套用')
        repairs.append(entry)
    references = defaultdict(list)
    for rel, raw in sorted(target.items()):
        if not rel.startswith('config/ftbquests/') or not rel.endswith('.snbt'):
            continue
        for path, token in snbt_leaves(raw.decode('utf-8-sig')):
            for resource in IMAGE.findall(token.value):
                references[resource].append({'file': rel, 'field': list(path)})
    stale = {resource for entry in data['repairs'] for resource in IMAGE.findall(entry['source'])}
    entries, counts = [], Counter()
    for resource, locations in sorted(references.items()):
        ns, separator, path = resource.partition(':')
        bundled = f'RP/assets/{ns}/{path}'
        kubejs = f'kubejs/assets/{ns}/{path}'
        if not separator:
            status = '圖片 ID 無法解析'
        elif bundled in target or kubejs in target:
            status = '包內有檔'
        elif data['pack_assets'].get(resource):
            status = '官方 8.3 原始碼有檔，安裝狀態未驗證'
        elif resource in data.get('case_mismatches', {}):
            status = '官方路徑大小寫不同，未驗證'
        elif ns == 'atm':
            status = '翻譯包與官方索引均無檔，待查'
        else:
            status = '模組資源，未驗證'
        if resource in stale:
            errors.append(f'已失效的圖片仍被引用：{resource}')
        counts[status] += 1
        entries.append({'resource': resource, 'status': status, 'references': locations,
                        'official_path': data['pack_assets'].get(resource),
                        'case_candidates': data.get('case_mismatches', {}).get(resource, [])})
    return {'status': '部份未驗證', 'scope': 'FTB Quests 正文的內嵌圖片。官方 GitHub 索引不等於安裝後的資源載入結果。',
            'repository': data.get('repository'), 'commit': data['commit'],
            'pack_version': data['pack_version'], 'errors': errors, 'repairs': repairs,
            'counts': dict(counts), 'entries': entries}
