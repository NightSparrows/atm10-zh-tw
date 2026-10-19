#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""離線比對來源與繁中產物，缺少基準即失敗。"""
import argparse
import io
import json
import re
import subprocess
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

import opencc
from formats import (HAN, PROTECTED, js_decode, js_strings, js_display_slot, js_tree, json_load,
                     leaves, markers, replace_spans, snbt_leaves)

ASCII = re.compile(r'[\x00-\x7f]+')


def string_errors(a, b, label):
    errors = []
    if markers(a) != markers(b):
        errors.append(f'{label}：格式參數或特殊標記改變')
    if ASCII.findall(a) != ASCII.findall(b):
        errors.append(f'{label}：ASCII 內容改變')
    return errors


def json_errors(rel, a, b):
    from build_tw import LOCALE_VALUES, json_visible, source_json
    source = source_json(rel, a)
    target = json_load(b)
    errors = []

    def compare(x, y, path=()):
        label = f'{rel}:{path}'
        if isinstance(x, dict):
            if not isinstance(y, dict) or set(x) != set(y):
                errors.append(f'{label}：JSON keys 不同')
                return
            for key in x:
                compare(x[key], y[key], path + (key,))
        elif isinstance(x, list):
            if not isinstance(y, list) or len(x) != len(y):
                errors.append(f'{label}：陣列結構改變')
                return
            for i, (u, v) in enumerate(zip(x, y)):
                compare(u, v, path + (i,))
        elif type(x) is not type(y):
            errors.append(f'{label}：資料型別改變')
        elif isinstance(x, str) and json_visible(rel, path):
            if re.search(r'/lang/zh_cn\.json$', rel) and path[0] in LOCALE_VALUES:
                if y != LOCALE_VALUES[path[0]]:
                    errors.append(f'{label}：語言中繼資料不符')
                return
            if rel == 'RP/pack.mcmeta' and path == ('pack', 'description'):
                y = y.removesuffix('（繁體中文）')
            errors.extend(string_errors(x, y, label))
        elif x != y:
            errors.append(f'{label}：非翻譯欄位改變')

    if rel == 'config/vaultpatcher_asm/config.json':
        if source['default_language'] != 'zh_cn' or target['default_language'] != 'zh_tw':
            errors.append('VaultPatcher 語言選擇不符')
        source['default_language'] = 'zh_tw'
    if rel == 'RP/pack.mcmeta' and 'zh_cn' in source.get('language', {}):
        source['language']['zh_tw'] = {'name': '繁體中文', 'region': '台灣', 'bidirectional': False}
        del source['language']['zh_cn']
    compare(source, target)
    return errors


def snbt_errors(rel, a, b):
    from build_tw import snbt_visible
    source, target = a.decode('utf-8-sig'), b.decode('utf-8-sig')
    A, B = snbt_leaves(source), snbt_leaves(target)
    errors = []
    if [p for p, _ in A] != [p for p, _ in B]:
        return [f'{rel}：SNBT 欄位或陣列結構改變']
    masks_a, masks_b = [], []
    for (path, x), (_, y) in zip(A, B):
        if snbt_visible(rel, path) and x.quoted:
            errors.extend(string_errors(x.value, y.value, f'{rel}:{path}'))
            masks_a.append((x.start, x.end, '"TEXT"'))
            masks_b.append((y.start, y.end, '"TEXT"'))
        elif x.raw != y.raw:
            errors.append(f'{rel}:{path}：任務 ID、依賴或其他資料改變')
    if replace_spans(source, masks_a) != replace_spans(target, masks_b):
        errors.append(f'{rel}：SNBT 非文字內容改變')
    return errors


def javascript_errors(rel, a, b):
    from build_tw import text_is_data
    A, B = js_strings(a), js_strings(b)
    if len(A) != len(B):
        return [f'{rel}：JavaScript 字串數量改變']
    errors, masks_a, masks_b = [], [], []
    for (x, u), (y, v) in zip(A, B):
        source, target = js_decode(u), js_decode(v)
        exception = ((rel.endswith('/hanhua_pack_check.js') and
                      source == 'lang/zh_cn.json' and target == 'lang/zh_tw.json') or
                     (rel.endswith('/hanhua_update_check.js') and
                      source == 'chiba233/atm10-zh-cn' and target == 'NightSparrows/atm10-zh-tw'))
        if exception or (HAN.search(source) and not text_is_data(source) and js_display_slot(x, rel)):
            if not exception:
                errors.extend(string_errors(source, target, f'{rel}:{x.start_byte}'))
            masks_a.append((x.start_byte, x.end_byte, b'"TEXT"'))
            masks_b.append((y.start_byte, y.end_byte, b'"TEXT"'))
        elif u != v:
            errors.append(f'{rel}:{x.start_byte}：非文字字串改變')
    if replace_spans(a, masks_a) != replace_spans(b, masks_b):
        errors.append(f'{rel}：JavaScript 程式或物件鍵改變')
    return errors


def residuals(files):
    from build_tw import json_visible, snbt_visible
    s2t = opencc.OpenCC('s2tw')
    allowed = json_load((Path(__file__).resolve().parents[2] / 'src/zh_tw/terms.json').read_bytes())
    words = allowed.get('check_allow_words', {}).get('words', [])
    shared = set('岩丑游斗台里占划霉后几')
    counts, samples, ambiguous = Counter(), [], Counter()
    cache = {}
    for rel, raw in sorted(files.items()):
        if rel.endswith(('.json', '.mcmeta')):
            obj = json_load(raw)
            source_rel = rel.replace('zh_tw', 'zh_cn')
            values = [(str(path), value, 'display' if json_visible(source_rel, path) else 'protected_data') for path, value in leaves(obj)
                      if isinstance(value, str)]
        elif rel.endswith('.snbt'):
            source_rel = rel.replace('zh_tw', 'zh_cn')
            values = [(str(path), token.value, 'display' if snbt_visible(source_rel, path) else 'protected_data')
                      for path, token in snbt_leaves(raw.decode('utf-8-sig'))]
        elif rel.endswith('.js'):
            values = [(str(node.start_byte), js_decode(value),
                       'display' if js_display_slot(node, rel) else 'protected_data')
                      for node, value in js_strings(raw)]
        elif rel.endswith(('.md', '.mdx', '.txt', '.gui')):
            values = [('document', raw.decode('utf-8-sig'), 'document')]
        else:
            continue
        for field, value, category in values:
            value = PROTECTED.sub('', value)
            for word in words:
                value = value.replace(word, '')
            hits = []
            for char in HAN.findall(value):
                if char not in cache:
                    cache[char] = s2t.convert(char) != char
                if cache[char]:
                    if char in shared:
                        ambiguous[char] += 1
                    else:
                        hits.append(char)
            if hits:
                counts.update(hits)
                samples.append({'file': rel, 'field': field, 'category': category,
                                'characters': ''.join(sorted(set(hits))), 'occurrences': len(hits),
                                'sample': value[:240]})
    return {'method': 'OpenCC s2tw 單字候選。允許詞與共用字分列，候選仍需人工判讀。',
            'scope': '掃描 JSON 值、SNBT 值、JavaScript 字串及手冊正文。鍵、註解、模板字串與特殊標記不作漏譯判定。',
            'characters': dict(counts), 'occurrences': sum(counts.values()),
            'shared_or_ambiguous_characters': dict(ambiguous),
            'entries': samples}


def validate(source, target, output_zip, report_dir):
    from build_tw import RP, rename, read_zip, source_json
    if not source or not target:
        raise ValueError('缺少來源或產物基準')
    errors, counts = [], Counter()
    expected = {rename(k) for k in source}
    missing, extra = sorted(expected-set(target)), sorted(set(target)-expected)
    if missing or extra:
        errors.append('來源與產物檔案清單不同')
    for rel, raw in sorted(source.items()):
        if rename(rel) not in target:
            continue
        translated = target[rename(rel)]
        try:
            if rel.endswith(('.json', '.mcmeta')):
                errors.extend(json_errors(rel, raw, translated))
                counts['json_files'] += 1
                if re.search(r'/lang/zh_cn\.json$', rel):
                    counts['source_lang_entries'] += len(source_json(rel, raw))
                    counts['output_lang_entries'] += len(json_load(translated))
                    counts['lang_files'] += 1
            elif rel.endswith('.snbt'):
                errors.extend(snbt_errors(rel, raw, translated))
                counts['snbt_files'] += 1
                if '/quests/lang/' in rel:
                    counts['source_quest_entries'] += len(snbt_leaves(raw.decode('utf-8-sig')))
                    counts['output_quest_entries'] += len(snbt_leaves(translated.decode('utf-8-sig')))
            elif rel.endswith('.js'):
                errors.extend(javascript_errors(rel, raw, translated))
                counts['javascript_files'] += 1
            elif rel.endswith(('.md', '.mdx', '.txt', '.gui')) and rel.startswith('RP/'):
                errors.extend(string_errors(raw.decode('utf-8'), translated.decode('utf-8'), rel))
                counts['manual_text_files'] += 1
            elif raw != translated:
                errors.append(f'{rel}：二進位或未支援檔案改變')
        except Exception as exc:
            errors.append(f'{rel}：{exc}')
    images = [{'source': rel, 'output': rename(rel), 'sha256': __import__('hashlib').sha256(raw).hexdigest(),
               'status': '保留原圖，文字與字形未驗證'} for rel, raw in sorted(source.items())
              if rel.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
    outer = read_zip(output_zip.read_bytes())
    actual = {}
    for rel, raw in outer.items():
        if not rel.startswith('atm10-zh_tw-client/'):
            errors.append('Client ZIP 頂層目錄不符')
        rel = rel.removeprefix('atm10-zh_tw-client/')
        if rel == RP:
            actual.update({'RP/'+n: v for n, v in read_zip(raw).items()})
        elif rel.startswith(('config/', 'kubejs/', 'vaultpatcher/')):
            actual[rel] = raw
        if rel.lower().endswith('.jar'):
            errors.append('ZIP 不得包含 JAR')
    if actual != target:
        errors.append('ZIP 實際資源與驗證基準不同')
    for name in ('install.sh', 'install.ps1', 'install-windows.bat', 'README.zh_tw.md'):
        if 'atm10-zh_tw-client/'+name not in outer:
            errors.append(f'ZIP 缺少安裝檔案：{name}')
    with tempfile.TemporaryDirectory(prefix='atm10-tw-check-', dir=Path(__file__).resolve().parents[2]/'build') as temp:
        root = Path(temp)
        for name, raw in outer.items():
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(raw)
        script = root / 'atm10-zh_tw-client/install.sh'
        subprocess.run(['bash', '-n', str(script)], check=True, capture_output=True)
        for name, raw in outer.items():
            if (root/name).read_bytes() != raw:
                errors.append(f'ZIP 解壓內容不符：{name}')
    residue = residuals(target)
    report = {'status': '通過' if not errors else '失敗', 'errors': errors,
              'source_files': len(source), 'output_files': len(target), 'missing_files': missing,
              'extra_files': extra, 'counts': dict(counts),
              'language_schema_exception': 'pack.mcmeta 的 language.zh_cn 改為 language.zh_tw。其他 JSON keys 完全保留。',
              'language_value_exceptions': '語言檔的 language.code、language.name、language.region 設為 zh_tw、繁體中文、台灣。',
              'unverified': ['遊戲內載入與顯示', 'KubeJS / NeoForge 執行時 API 相容性',
                             '模組 JAR 自帶簡中但翻譯包未收錄的內容', 'VaultPatcher 執行效果與依賴安裝',
                             '圖片文字與台灣字形', 'Windows PowerShell 安裝器執行',
                             '多人伺服器同步與權限', '獎杯等以顯示名形成的動態翻譯鍵'],
              'residual_candidates': residue['occurrences'], 'images_pending': len(images)}
    for name, data in [('validation.json', report), ('simplified-residue.json', residue),
                       ('images-manual.json', images)]:
        (report_dir/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return report


def main():
    from build_tw import source_files, read_zip, RP
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--reports', type=Path, default=Path('dist/reports/zh_tw-8.3'))
    parser.add_argument('--unlocked', action='store_true')
    args = parser.parse_args()
    files, _ = source_files(args.source, not args.unlocked)
    outer = read_zip(args.output.read_bytes())
    target = {}
    for name, raw in outer.items():
        rel = name.removeprefix('atm10-zh_tw-client/')
        if rel == RP:
            target.update({'RP/'+n: v for n, v in read_zip(raw).items()})
        elif rel.startswith(('config/', 'kubejs/', 'vaultpatcher/')):
            target[rel] = raw
    args.reports.mkdir(parents=True, exist_ok=True)
    report = validate(files, target, args.output, args.reports)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(bool(report['errors']))


if __name__ == '__main__':
    main()
