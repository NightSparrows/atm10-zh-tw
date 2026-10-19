#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""繁中轉換與靜態驗證的反例測試。"""
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from build_tw import Builder, installer_files, json_visible, read_zip, rename, source_files, source_json
from check_tw import json_errors, javascript_errors, snbt_errors, string_errors, validate, residuals
from converter import Converter, load_terms
from fetch_translation import RemoteZip, allowed
from formats import markers, snbt_leaves
from quest_images import audit, load_baseline


class ConversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = Builder()

    def test_fork_terms(self):
        c = self.builder.conv
        for a, b in [('下界合金', '獄髓'), ('末地', '終界'), ('台阶', '半磚'),
                     ('暮色森林', '暮光森林'), ('天境', '天堂'),
                     ('探险家罗盘', '結構羅盤'), ('僵尸', '殭屍')]:
            self.assertEqual(c.convert(a), b)
        terms, post, exclude, rules = load_terms()
        self.assertGreater(len(terms), 200)
        self.assertTrue(rules)

    def test_markup(self):
        source = '红色§c下界合金§r %s %1$s %d %1$04d &#4497DB超频 $(l:mod:path)文字$(/l) ${variable} {player} <item id="mod:x"/> `模式`'
        result = self.builder.conv.convert(source)
        self.assertEqual(markers(source), markers(result))
        self.assertIn('&#4497DB', result)
        self.assertIn('獄髓', result)
        self.assertFalse(string_errors(source, result, 'text'))

    def test_escaped_json_and_chinese_keys(self):
        raw = json.dumps({'简体键': '下界合金 %1$s'}).encode()
        rel = 'RP/assets/demo/lang/zh_cn.json'
        output = self.builder.convert(rel, raw)
        self.assertEqual(json.loads(output), {'简体键': '獄髓 %1$s'})
        self.assertFalse(json_errors(rel, raw, output))

    def test_language_metadata(self):
        rel = 'RP/assets/demo/lang/zh_cn.json'
        raw = '{"language.code":"zh_cn","language.region":"中国大陆","language.name":"简体中文"}'.encode()
        out = self.builder.json(rel, raw)
        self.assertEqual(json.loads(out)['language.code'], 'zh_tw')
        self.assertEqual(json.loads(out)['language.region'], '台灣')
        self.assertFalse(json_errors(rel, raw, out))
        self.assertTrue(json_errors(rel, raw, out.replace(b'zh_tw', b'zh_cn')))

    def test_keys_extra_and_missing_fail(self):
        rel = 'RP/assets/demo/lang/zh_cn.json'
        for changed in [b'{}', b'{"a":"text", "extra":"x"}']:
            self.assertTrue(json_errors(rel, b'{"a":"text"}', changed))

    def test_invalid_json_and_duplicate_keys_fail(self):
        for raw in [b'{', b'{"a":1,"a":2}']:
            with self.assertRaises(ValueError):
                self.builder.json('RP/assets/demo/lang/zh_cn.json', raw)

    def test_format_mutations_fail(self):
        for a, b in [('文字 %1$s', '文字 %s'), ('§c文字', '§a文字'),
                     ('$(l:a:b)文字', '$(l:a:c)文字'), ('${x}', '${y}')]:
            self.assertTrue(string_errors(a, b, 'format'))

    def test_json_non_text_unchanged(self):
        raw = '{"id":"mod:机器", "name":"下界合金", "size":2, "key":"模式"}'.encode()
        out = self.builder.json('config/test.json', raw)
        self.assertEqual(json.loads(out)['id'], 'mod:机器')
        self.assertEqual(json.loads(out)['key'], '模式')
        self.assertFalse(json_errors('config/test.json', raw, out))
        self.assertTrue(json_errors('config/test.json', raw, out.replace(b'"size": 2', b'"size": 3')))

    def test_snbt_quest_identity(self):
        rel = 'config/ftbquests/quests/chapters/test.snbt'
        raw = '{id:"ABCD" quests:[{id:"0123" dependencies:["4567"] title:"下界合金" x:1.5d}] }'.encode()
        out = self.builder.snbt(rel, raw)
        self.assertIn('獄髓'.encode(), out)
        self.assertFalse(snbt_errors(rel, raw, out))
        for a, b in [(b'0123', b'9999'), (b'4567', b'7777'), (b'1.5d', b'2.0d')]:
            self.assertTrue(snbt_errors(rel, raw, out.replace(a, b)))

    def test_snbt_escape_and_glyph_data(self):
        rel = 'config/ftbquests/quests/lang/zh_cn/chapter.snbt'
        raw = r'{"quest.A.title":"粉色史莱姆液 \& 肉汤"}'.encode()
        out = self.builder.snbt(rel, raw)
        self.assertIn(b'\\&', out)
        self.assertFalse(snbt_errors(rel, raw, out))
        glyph = '{"providers":[{"chars":["简体"]}]}'.encode()
        self.assertEqual(self.builder.json('RP/assets/minecraft/font/font.json', glyph), glyph)

    def test_snbt_sign_display_only(self):
        raw = r'{data:[{nbt:{id:"mod:block" Text1:"{\"text\":\"一些机器\"}"} x:4}]}'.encode()
        rel = 'RP/assets/ae2/ae2guide/_zh_cn/assets/test.snbt'
        out = self.builder.snbt(rel, raw)
        self.assertIn('機器'.encode(), out)
        self.assertFalse(snbt_errors(rel, raw, out))

    def test_stale_quest_image_removed(self):
        rule = load_baseline()['repairs'][0]
        rel = rule['file']
        raw = ('{' + rule['field'][0] + ': ["原本文字" ' + json.dumps(rule['source']) + ']}').encode()
        out = self.builder.snbt(rel, raw)
        values = {p: t.value for p, t in snbt_leaves(out.decode())}
        self.assertEqual(values[tuple(rule['field'])], '')
        self.assertEqual(values[(rule['field'][0], 0)], '原本文字')
        self.assertFalse(snbt_errors(rel, raw, out))
        self.assertTrue(snbt_errors(rel, raw, raw))

    def test_image_repair_source_drift_fails(self):
        rule = load_baseline()['repairs'][0]
        changed = rule['source'].replace('width:200', 'width:201')
        raw = ('{' + rule['field'][0] + ': ["原本文字" ' + json.dumps(changed) + ']}').encode()
        with self.assertRaises(ValueError):
            self.builder.snbt(rule['file'], raw)

    def test_other_image_markers_cannot_disappear(self):
        rel = 'config/ftbquests/quests/lang/zh_cn/test.snbt'
        raw = b'{"quest.X.quest_desc":["{image:atm:textures/other.png width:20}"]}'
        self.assertEqual(self.builder.snbt(rel, raw), raw)
        self.assertTrue(snbt_errors(rel, raw, b'{"quest.X.quest_desc":[""]}'))

    def test_image_index_separates_external_dependencies(self):
        baseline = {'pack_version': '8.3', 'commit': 'test', 'repairs': [],
                    'pack_assets': {'atm:official.png': 'kubejs/assets/atm/official.png'},
                    'case_mismatches': {'atm:case.png': ['kubejs/assets/atm/CASE.png']}}
        text = '{k:["{image:atm:bundled.png}" "{image:atm:official.png}" "{image:atm:case.png}" "{image:atm:missing.png}" "{image:mod:external.png}"]}'
        target = {'config/ftbquests/quests/lang/zh_tw/test.snbt': text.encode(),
                  'RP/assets/atm/bundled.png': b'fixture'}
        report = audit({}, target, baseline)
        self.assertEqual(len(report['entries']), 5)
        self.assertEqual(report['counts']['包內有檔'], 1)
        self.assertEqual(report['counts']['翻譯包與官方索引均無檔，待查'], 1)
        self.assertEqual(report['status'], '部份未驗證')

    def test_missing_image_baseline_fails(self):
        with patch('quest_images.BASELINE', Path('absent-image-baseline.json')):
            with self.assertRaises(FileNotFoundError):
                Builder()

    def test_javascript_non_text_and_keys(self):
        rel = 'kubejs/client_scripts/test.js'
        raw = '''const PB_ID2ZH = {"简体键":"下界合金"};
const data = {"机器":"模式"}; mode("模式");
if (name === "下界合金") save("/give @s mod:item");
event.create("mod:id").displayName("下界合金 %s");
Text.of("红色");
'''.encode()
        out = self.builder.javascript(rel, raw)
        self.assertIn('"简体键":"獄髓"'.encode(), out)
        self.assertIn('mode("模式")'.encode(), out)
        self.assertIn('name === "下界合金"'.encode(), out)
        self.assertIn('"机器":"模式"'.encode(), out)
        self.assertFalse(javascript_errors(rel, raw, out))
        self.assertTrue(javascript_errors(rel, raw, out.replace(b'mod:id', b'mod:changed')))
        self.assertTrue(javascript_errors(rel, raw, out.replace('简体键'.encode(), '繁體鍵'.encode())))

    def test_broken_javascript_fails(self):
        with self.assertRaises(ValueError):
            self.builder.javascript('test.js', b'const x = {')

    def test_gui_choice_stays_protocol(self):
        raw = "choice('模式','模式')\nbutton('id','红色')\ntooltips('下界合金')".encode()
        out = self.builder.convert('RP/assets/test/gui/test.gui', raw)
        self.assertIn("choice('模式','模式')".encode(), out)
        self.assertIn('獄髓'.encode(), out)

    def test_path_renames(self):
        for a, b in [('RP/assets/x/lang/zh_cn.json', 'RP/assets/x/lang/zh_tw.json'),
                     ('RP/assets/x/book/_zh_cn/a.mdx', 'RP/assets/x/book/_zh_tw/a.mdx'),
                     ('config/ftbquests/quests/lang/zh_cn/a.snbt', 'config/ftbquests/quests/lang/zh_tw/a.snbt')]:
            self.assertEqual(rename(a), b)

    def test_installer_language_and_parameter_order(self):
        files = installer_files()
        for name in ['install.sh', 'install.ps1']:
            text = files[name].decode('utf-8-sig')
            self.assertNotIn('@@', text)
            self.assertIn('ATM10-zh_tw-8.3.zip', text)
            self.assertNotIn('zh_cn', text)
            self.assertIn('ATM_SKIP_UPDATE_CHECK', text)
        text = files['install.ps1'].decode('utf-8-sig')
        self.assertLess(text.index('param('), text.index("$env:ATM_SKIP_UPDATE_CHECK = '1'"))

    def test_zip_path_and_duplicate_rejected(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('../escape', b'bad')
        with self.assertRaises(ValueError):
            read_zip(stream.getvalue())

    def test_no_missing_baseline_success(self):
        with self.assertRaises(ValueError):
            validate({}, {}, Path('missing'), Path('missing'))
        with self.assertRaises(FileNotFoundError):
            source_files(Path('absent-atm8.3.zip'))

    def test_version_rejected(self):
        with self.assertRaises(ValueError):
            source_files(Path('source-atm8.1.zip'), locked=False)

    def test_download_filter(self):
        self.assertTrue(allowed('atm10-zh_cn-client/resourcepacks/translation.zip'))
        for name in ['atm10-zh_cn-client/mods/test.jar',
                     'atm10-zh_cn-client/config/test.jar',
                     'atm10-zh_cn-client/../outside', 'mods/test.jar']:
            self.assertFalse(allowed(name))

    def test_range_ignored_fails_before_body(self):
        class Response:
            status = 200
            headers = {}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, *args): raise AssertionError('不得讀取完整下載')
        remote = object.__new__(RemoteZip)
        remote.url, remote.size = 'https://example.invalid', 100
        with patch('urllib.request.urlopen', return_value=Response()):
            with self.assertRaises(ValueError):
                remote.read(10, 5)

    def test_residue_scanner_positive_control(self):
        raw = '{"x":"机器"}'.encode()
        result = residuals({'RP/assets/test/lang/zh_tw.json': raw})
        self.assertGreater(result['occurrences'], 0)
        self.assertIn('机', result['characters'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
