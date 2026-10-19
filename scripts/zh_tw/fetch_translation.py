#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""只取得漢化 ZIP 的翻譯檔，拒絕下載 JAR 與遊戲內容。"""
import argparse
import hashlib
import io
import json
import struct
import urllib.request
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]


class RemoteZip:
    def __init__(self, url, size):
        if not url.startswith('https://github.com/chiba233/atm10-zh-cn/releases/download/'):
            raise ValueError('只接受上游漢化 release URL')
        self.url, self.size = url, size
        end = self.read(size - 22, 22)
        fields = struct.unpack('<4s4H2LH', end)
        if fields[0] != b'PK\x05\x06' or fields[-1] or fields[1] or fields[2]:
            raise ValueError('不支援分卷、ZIP64 或帶註解的 ZIP')
        central_size, self.central_offset = fields[5:7]
        central = self.read(self.central_offset, central_size)
        probe = io.BytesIO(central + struct.pack('<4s4H2LH', b'PK\x05\x06', 0, 0,
                            fields[3], fields[4], central_size, 0, 0))
        with zipfile.ZipFile(probe) as archive:
            self.entries = archive.infolist()

    def read(self, offset, size):
        req = urllib.request.Request(self.url, headers={
            'Range': f'bytes={offset}-{offset + size - 1}',
            'Accept-Encoding': 'identity', 'User-Agent': 'atm10-translation-only'})
        with urllib.request.urlopen(req, timeout=60) as response:
            expected = f'bytes {offset}-{offset + size - 1}/{self.size}'
            if response.status != 206 or response.headers.get('Content-Range') != expected:
                raise ValueError('伺服器未遵守 Range，停止讀取以避免下載 JAR')
            data = response.read(size + 1)
            if len(data) != size:
                raise ValueError('Range 長度不符')
            return data

    def member(self, entry):
        header = self.read(entry.header_offset, 30)
        sig, _, flags, method, _, _, crc, packed, unpacked, names, extra = struct.unpack(
            '<4s5H3L2H', header)
        if sig != b'PK\x03\x04' or flags & 9 or method not in (0, 8):
            raise ValueError(f'不支援的 ZIP 成員：{entry.filename}')
        if (method, crc, packed, unpacked) != (
                entry.compress_type, entry.CRC, entry.compress_size, entry.file_size):
            raise ValueError('ZIP 目錄與檔頭不符')
        raw = self.read(entry.header_offset + 30 + names + extra, packed)
        data = zlib.decompress(raw, -15) if method == 8 else raw
        if len(data) != unpacked or zlib.crc32(data) != crc:
            raise ValueError(f'CRC 不符：{entry.filename}')
        return data


def allowed(name):
    parts = PurePosixPath(name).parts
    if len(parts) < 2 or parts[0] != 'atm10-zh_cn-client' or '..' in parts:
        return False
    if any(part.lower().endswith(('.jar', '.class', '.exe', '.dll')) for part in parts):
        return False
    return parts[1] in {'resourcepacks', 'config', 'kubejs', 'vaultpatcher'}


def fetch(lock, output, record=False):
    source = json.loads(lock.read_text(encoding='utf-8'))
    remote = RemoteZip(source['url'], source['size'])
    selected = [e for e in remote.entries if not e.is_dir() and allowed(e.filename)]
    if not selected or len({e.filename for e in selected}) != len(selected):
        raise ValueError('翻譯成員缺失或重複')
    manifest = {}
    files = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for entry, data in zip(selected, pool.map(remote.member, selected)):
            manifest[entry.filename] = hashlib.sha256(data).hexdigest()
            files[entry.filename] = data
    if record:
        source['members_sha256'] = manifest
        source['excluded'] = [e.filename for e in remote.entries
                              if not e.is_dir() and not allowed(e.filename)]
        lock.write_text(json.dumps(source, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    elif not source.get('members_sha256') or manifest != source['members_sha256']:
        raise ValueError('翻譯成員與鎖檔不符')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    print(f'取得翻譯檔 {len(files)} 個，排除 {len(source.get("excluded", []))} 個成員')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lock', type=Path, default=ROOT / 'src/zh_tw/source.lock.json')
    parser.add_argument('--out', type=Path, default=ROOT / 'build/inputs/atm10-zh_cn-client-r27-atm8.3.zip')
    parser.add_argument('--record', action='store_true', help='更新翻譯成員雜湊')
    args = parser.parse_args()
    fetch(args.lock, args.out, args.record)


if __name__ == '__main__':
    main()
