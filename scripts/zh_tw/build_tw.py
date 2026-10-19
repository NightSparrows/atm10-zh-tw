#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""將已建置的 ATM10 8.3 簡中翻譯檔轉成獨立繁中 Client ZIP。"""
import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from importlib.metadata import version

from converter import Converter
from formats import (HAN, VISIBLE, decode_string, js_decode, js_encode,
                     js_strings, js_display_slot, json_load, leaves, replace_spans, snbt_leaves)

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'src/zh_tw'
RP = 'resourcepacks/ATM10-zh_tw-8.3.zip'
LOCALE_VALUES = {'language.code': 'zh_tw', 'language.region': '台灣', 'language.name': '繁體中文'}
REPAIRS = {
    'assets/herbsandharvest/books/chapters/grapes.json',
    'assets/herbsandharvest/books/chapters/herbs.json',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_zip(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP CRC 不符')
        files = {}
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            parts = PurePosixPath(entry.filename).parts
            if (not parts or entry.filename.startswith('/') or '..' in parts or
                    '\\' in entry.filename or entry.filename in files or
                    (entry.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError(f'ZIP 路徑不安全或重複：{entry.filename}')
            files[entry.filename] = archive.read(entry)
        return files


def source_files(path, locked=True):
    if not path.name.endswith('-atm8.3.zip'):
        raise ValueError('來源檔名必須標明 ATM10 8.3')
    source = read_zip(path.read_bytes())
    if locked:
        lock = json_load((DATA / 'source.lock.json').read_bytes())
        from fetch_translation import allowed
        selected = {n: sha(b) for n, b in source.items() if allowed(n)}
        if selected != lock['members_sha256']:
            raise ValueError('8.3 翻譯來源與 source.lock.json 不符')
    output = {}
    omitted = []
    for name, raw in source.items():
        parts = PurePosixPath(name).parts
        if parts[0] != 'atm10-zh_cn-client':
            raise ValueError('來源不是簡中 Client ZIP')
        rel = '/'.join(parts[1:])
        if rel.startswith(('mods/', '可选mods-拼音搜索/')) or rel.lower().endswith('.jar'):
            omitted.append(rel)
            continue
        if rel.startswith('resourcepacks/') and rel.endswith('.zip'):
            if any(k.startswith('RP/') for k in output):
                raise ValueError('來源有多份資源包')
            for item, data in read_zip(raw).items():
                if item.lower().endswith(('.jar', '.class', '.exe', '.dll')):
                    raise ValueError('資源包內含執行檔')
                output['RP/' + item] = data
        elif rel.startswith(('config/', 'kubejs/', 'vaultpatcher/')):
            output[rel] = raw
        else:
            omitted.append(rel)
    required = ('RP/pack.mcmeta', 'config/vaultpatcher_asm/config.json',
                'kubejs/client_scripts/hanhua_pack_check.js')
    if any(n not in output for n in required) or not any('/lang/zh_cn/' in n for n in output):
        raise ValueError('來源缺少資源包、任務書或必要設定')
    return output, omitted


def rename(rel):
    if rel.startswith('RP/'):
        return rel.replace('zh_cn', 'zh_tw')
    return re.sub(r'(?<=/)zh_cn(?=/|\.json$)', 'zh_tw', rel)


def source_json(rel, raw):
    try:
        return json_load(raw)
    except ValueError:
        if rel.removeprefix('RP/') not in REPAIRS:
            raise
        lock = json_load((DATA / 'repairs.json').read_bytes())
        if sha(raw) != lock[rel.removeprefix('RP/')]['sha256']:
            raise ValueError(f'JSON 修正的來源雜湊不符：{rel}')
        text = raw.decode('utf-8-sig')
        _, end = json.JSONDecoder().raw_decode(text)
        if text[end:].strip() != ']\r\n}':
            raise ValueError(f'JSON 修正的尾端不符：{rel}')
        return json_load(text[:end].encode())


def json_visible(rel, path):
    if re.search(r'/lang/zh_cn\.json$', rel):
        return not str(path[0]).startswith('/')
    if '/font/' in rel:
        return False
    if rel.startswith('vaultpatcher/modules/'):
        return len(path) >= 4 and path[-1] == 'value' and 'pairs' in path
    if rel.endswith('_meta.json'):
        return True
    return any(isinstance(k, str) and k.split('.')[-1] in VISIBLE for k in path)


def snbt_visible(rel, path):
    if '/quests/lang/zh_cn/' in rel:
        return True
    if (any(k in {'minecraft:custom_name', 'minecraft:lore'} for k in path) or
            ('nbt' in path and any(k in {'Text1', 'Text2', 'Text3', 'Text4'} for k in path)) or
            ('front_text' in path and 'messages' in path)):
        return True
    return any(k in VISIBLE for k in path if isinstance(k, str))


def text_is_data(text):
    return text.startswith(('/', 'http://', 'https://')) or bool(
        re.match(r'^[a-z_][a-z0-9_.-]*:', text))


class Builder:
    def __init__(self):
        self.conv = Converter()
        self.overrides = json_load((DATA / 'overrides.json').read_bytes())['lang']
        self.changes = []
        self.repairs = []

    def display(self, value, rel, path, command_document=False):
        if not HAN.search(value) or (text_is_data(value) and not command_document):
            return value
        out = self.conv.convert(value)
        if out != value:
            self.changes.append({'file': rel, 'field': list(path), 'source': value, 'output': out})
        return out

    def json(self, rel, raw):
        data = source_json(rel, raw)
        if rel.removeprefix('RP/') in REPAIRS:
            self.repairs.append(rel)

        def walk(value, path=()):
            if isinstance(value, dict):
                return {k: walk(v, path + (k,)) for k, v in value.items()}
            if isinstance(value, list):
                return [walk(v, path + (i,)) for i, v in enumerate(value)]
            if isinstance(value, str) and json_visible(rel, path):
                ns = re.search(r'assets/([^/]+)/lang/zh_cn\.json$', rel)
                if ns and path[0] in LOCALE_VALUES:
                    output = LOCALE_VALUES[path[0]]
                    self.changes.append({'file': rel, 'field': list(path), 'source': value, 'output': output})
                    return output
                override = self.overrides.get(ns[1], {}).get(path[0]) if ns else None
                if override is not None:
                    if not isinstance(override, str):
                        raise ValueError('逐鍵覆寫必須是字串')
                    self.changes.append({'file': rel, 'field': list(path),
                                         'source': value, 'output': override})
                    return override
                command_document = ns is not None and str(path[0]).startswith(('commands.', 'command.'))
                return self.display(value, rel, path, command_document)
            return value

        out = walk(data)
        if rel == 'config/vaultpatcher_asm/config.json':
            if data['default_language'] != 'zh_cn':
                raise ValueError('VaultPatcher 來源語言不符')
            out['default_language'] = 'zh_tw'
        if rel == 'RP/pack.mcmeta':
            out['pack']['description'] = self.conv.convert(data['pack']['description']) + '（繁體中文）'
            if 'zh_cn' in out.get('language', {}):
                out['language']['zh_tw'] = {'name': '繁體中文', 'region': '台灣', 'bidirectional': False}
                del out['language']['zh_cn']
        if out == data and rel not in self.repairs:
            return raw
        return (json.dumps(out, ensure_ascii=False, indent=2) + '\n').encode()

    def snbt(self, rel, raw):
        text = raw.decode('utf-8-sig')
        edits = []
        for path, token in snbt_leaves(text):
            if token.quoted and snbt_visible(rel, path):
                output = self.display(token.value, rel, path)
                if output != token.value:
                    # 保留 SNBT 的非 JSON 跳脫，如任務標題中的 \&。
                    body = token.raw[1:-1]
                    converted = self.conv.convert(body)
                    edits.append((token.start, token.end, token.raw[0] + converted + token.raw[-1]))
        output = replace_spans(text, edits).encode()
        return (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + output

    def javascript(self, rel, raw):
        edits = []
        for node, literal in js_strings(raw):
            value = js_decode(literal)
            out = self.display(value, rel, (node.start_byte,)) if js_display_slot(node, rel) else value
            if rel == 'kubejs/client_scripts/hanhua_pack_check.js' and value == 'lang/zh_cn.json':
                out = 'lang/zh_tw.json'
            if rel == 'kubejs/client_scripts/hanhua_update_check.js' and value == 'chiba233/atm10-zh-cn':
                out = 'NightSparrows/atm10-zh-tw'
            if out != value:
                edits.append((node.start_byte, node.end_byte, js_encode(out, literal[0]).encode()))
        return replace_spans(raw, edits)

    def convert(self, rel, raw):
        if rel.endswith(('.json', '.mcmeta')):
            return self.json(rel, raw)
        if rel.endswith('.snbt'):
            return self.snbt(rel, raw)
        if rel.endswith('.js'):
            return self.javascript(rel, raw)
        if rel.startswith('RP/') and rel.endswith(('.md', '.mdx', '.txt')):
            return self.display(raw.decode('utf-8'), rel, ('document',)).encode()
        if rel.endswith('.gui'):
            text = raw.decode('utf-8')
            edits = []
            for m in re.finditer(r"\b(text|label|tooltips|button|togglebutton)\(([^\n]*)\)", text):
                for i, s in enumerate(re.finditer(r"'((?:\\.|[^'\\])*)'", m[2])):
                    if m[1] in {'button', 'togglebutton'} and i == 0:
                        continue
                    converted = self.display(s[1], rel, (m[1],))
                    if converted != s[1]:
                        edits.append((m.start(2)+s.start(1), m.start(2)+s.end(1), converted))
            return replace_spans(text, edits).encode()
        return raw


def mkzip(destination, source, prefix=None):
    cmd = [sys.executable, str(ROOT / 'scripts/mkzip.py'), str(destination), str(source)]
    if prefix:
        cmd.append(prefix)
    subprocess.run(cmd, check=True)


def installer_files():
    result = {}
    replacements = [('ATM10汉化包-@@MCVER@@.zip', 'ATM10-zh_tw-8.3.zip'),
                    ('@@MCVER@@', '8.3'), ('@@PATCHVER@@', 'r27-tw'),
                    ('@@DEFAULT_PACKS@@', ''),
                    ('chiba233/atm10-zh-cn', 'NightSparrows/atm10-zh-tw'),
                    ('zh_cn', 'zh_tw')]
    for name in ('install.sh', 'install.ps1', '双击安装-Windows.bat'):
        raw = (ROOT / 'installer' / name).read_bytes()
        text = raw.decode('utf-8-sig')
        if name in {'install.sh', 'install.ps1'}:
            expected = [1, 6 if name == 'install.sh' else 5, 1, 1, 1, 6]
            for (old, new), count in zip(replacements, expected):
                if text.count(old) != count:
                    raise ValueError(f'{name}：安裝器樣板改變，請核對 {old}')
                text = text.replace(old, new)
        if name == 'install.sh':
            if text.count('#!/usr/bin/env bash\n') != 1:
                raise ValueError('install.sh：樣板標頭改變')
            text = text.replace('#!/usr/bin/env bash\n',
                                '#!/usr/bin/env bash\nexport ATM_SKIP_UPDATE_CHECK=1\n', 1)
        if name == 'install.ps1':
            anchor = "$ErrorActionPreference = 'Stop'"
            if text.count(anchor) != 1:
                raise ValueError('install.ps1：樣板初始化改變')
            text = text.replace(anchor, anchor + "\n$env:ATM_SKIP_UPDATE_CHECK = '1'", 1)
        result['install-windows.bat' if name.endswith('.bat') else name] = (
            (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + text.encode())
    return result


def build(source, output, report_dir, locked=True):
    if source.resolve() == output.resolve():
        raise ValueError('輸出不可覆蓋來源 ZIP')
    if version('OpenCC') != '1.4.2':
        raise ValueError('請依 requirements-zh_tw.lock 安裝 OpenCC 1.4.2')
    files, omitted = source_files(source, locked)
    baseline = {k: sha(v) for k, v in files.items()}
    builder = Builder()
    converted = {rename(k): builder.convert(k, v) for k, v in sorted(files.items())}
    if len(converted) != len(files):
        raise ValueError('語言路徑轉換發生碰撞')
    report_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='atm10-tw-', dir=ROOT / 'build') as temp:
        stage = Path(temp) / 'client'
        pack = Path(temp) / 'pack'
        for rel, raw in converted.items():
            target = pack / rel[3:] if rel.startswith('RP/') else stage / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        mkzip(stage / RP, pack)
        extras = installer_files()
        extras['README.zh_tw.md'] = (DATA / 'package/README.client.md').read_bytes()
        for name in ('LICENSE', 'LICENSE-GPL-3.0', 'CREDITS.md'):
            extras[name] = (ROOT / name).read_bytes()
        for name, raw in extras.items():
            (stage / name).write_bytes(raw)
        (stage / 'install.sh').chmod(0o755)
        mkzip(output, stage, 'atm10-zh_tw-client')
    if baseline != {k: sha(v) for k, v in source_files(source, locked)[0].items()}:
        raise ValueError('建置修改了來源')
    manifest = {'source_sha256': sha(source.read_bytes()), 'output_sha256': sha(output.read_bytes()),
                'opencc': version('OpenCC'), 'source_files': len(files), 'output_files': len(converted),
                'changed_entries': len(builder.changes), 'repairs': builder.repairs,
                'omitted_non_translation_files': omitted, 'sources_unchanged': True,
                'files': [{'source': k, 'output': rename(k), 'source_sha256': sha(v),
                           'output_sha256': sha(converted[rename(k)])} for k, v in sorted(files.items())]}
    for name, data in [('manifest.json', manifest), ('changes.json', builder.changes)]:
        (report_dir / name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    from check_tw import validate
    report = validate(files, converted, output, report_dir)
    if report['errors']:
        raise ValueError(f'靜態驗證失敗：{report["errors"][:5]}')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--out', type=Path, default=ROOT / 'dist/atm10-zh_tw-client-r27-atm8.3.zip')
    parser.add_argument('--reports', type=Path, default=ROOT / 'dist/reports/zh_tw-8.3')
    parser.add_argument('--unlocked', action='store_true', help='接受重新建置的同版本來源，需自行核對來源')
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.out, args.reports, not args.unlocked), ensure_ascii=False,
                     default=str)[:300])


if __name__ == '__main__':
    main()
