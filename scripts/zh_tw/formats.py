#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""解析可翻譯字串，保留檔案語法與識別值。"""
import json
import re
from dataclasses import dataclass

HAN = re.compile('[㐀-鿿豈-﫿]')
PROTECTED = re.compile(
    r'(```[\s\S]*?```|`[^`\n]*`|https?://[^\s<>）]+|'
    r'\$\([^)]*\)|\$\{[^}]*\}|\{[\w.:-]+\}|'
    r'%(?:\d+\$)?[-#+ 0,(<]*\d*(?:\.\d+)?[a-zA-Z%]|'
    r'§(?:x(?:§[0-9a-fA-F]){6}|[0-9a-fk-orA-FK-OR])|'
    r'&(?:#[0-9a-fA-F]{6}|[0-9a-fk-orA-FK-OR])|'
    r'<[^>\n]+>|\]\([^\n)]*\))')
VISIBLE = {'text', 'name', 'title', 'subtitle', 'description', 'hover', 'header',
           'caption', 'summary', 'landing_text', 'button_text', 'display_name',
           'tooltip', 'tooltips', 'label', 'desc', 'lore', 'flavour_text',
           'literal_text', 'title1', 'title2', 'heading', 'link_text', 'spotlightText'}


def markers(text):
    return PROTECTED.findall(text)


def json_load(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError(f'JSON 重複鍵：{key}')
            out[key] = value
        return out
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs)


def leaves(obj, path=()):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from leaves(value, path + (key,))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            yield from leaves(value, path + (index,))
    else:
        yield path, obj


@dataclass
class Token:
    start: int
    end: int
    raw: str
    value: str
    quoted: bool = False


TOKEN = re.compile(r'\s+|//[^\n]*|/\*[\s\S]*?\*/|'
                   r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|'
                   r'[{}\[\]:,;]|[^\s{}\[\]:,;]+')


def decode_string(raw):
    if raw[0] == '"':
        normalized = re.sub(r'\\(?:u[0-9a-fA-F]{4}|.)',
                            lambda m: m[0] if m[0][1] in '"\\/bfnrtu' else '\\' + m[0], raw)
        return json.loads(normalized)
    body = raw[1:-1]
    return re.sub(r"\\(['\\])", r'\1', body)


def snbt_tokens(text):
    result = []
    end = 0
    for match in TOKEN.finditer(text):
        if match.start() != end:
            raise ValueError(f'SNBT 無法解析：{text[end:end+40]!r}')
        end = match.end()
        raw = match.group()
        if raw.isspace() or raw.startswith(('//', '/*')):
            continue
        quoted = raw.startswith(('"', "'"))
        result.append(Token(match.start(), match.end(), raw,
                            decode_string(raw) if quoted else raw, quoted))
    if end != len(text):
        raise ValueError('SNBT 尾端無法解析')
    return result


def snbt_leaves(text):
    tokens = snbt_tokens(text)
    index = 0
    result = []

    def take(expected=None):
        nonlocal index
        if index >= len(tokens):
            raise ValueError('SNBT 提早結束')
        token = tokens[index]
        index += 1
        if expected is not None and token.raw != expected:
            raise ValueError(f'SNBT 預期 {expected!r}，得到 {token.raw!r}')
        return token

    def value(path):
        token = take()
        if token.raw == '{':
            seen = set()
            while index < len(tokens) and tokens[index].raw != '}':
                key = take().value
                if key in seen:
                    raise ValueError(f'SNBT 重複鍵：{path + (key,)}')
                seen.add(key)
                take(':')
                value(path + (key,))
                if index < len(tokens) and tokens[index].raw == ',':
                    take(',')
            take('}')
        elif token.raw == '[':
            if index + 1 < len(tokens) and tokens[index+1].raw == ';':
                take()
                take(';')
            count = 0
            while index < len(tokens) and tokens[index].raw != ']':
                value(path + (count,))
                count += 1
                if index < len(tokens) and tokens[index].raw == ',':
                    take(',')
            take(']')
        elif token.raw in {'}', ']', ':', ',', ';'}:
            raise ValueError(f'SNBT 非預期符號：{token.raw}')
        else:
            result.append((path, token))

    value(())
    if index != len(tokens):
        raise ValueError('SNBT 有多餘資料')
    return result


def replace_spans(raw, edits):
    for start, end, replacement in sorted(edits, reverse=True):
        raw = raw[:start] + replacement + raw[end:]
    return raw


def js_tree(raw):
    from tree_sitter import Language, Parser
    import tree_sitter_javascript
    tree = Parser(Language(tree_sitter_javascript.language())).parse(raw)
    if tree.root_node.has_error:
        raise ValueError('JavaScript 語法無法解析')
    return tree


def js_strings(raw):
    tree = js_tree(raw)
    result = []

    def visit(node):
        if node.type == 'string':
            text = raw[node.start_byte:node.end_byte].decode('utf-8')
            parent = node.parent
            is_key = (parent.type == 'pair' and parent.child_by_field_name('key') == node)
            comparison = (parent.type == 'binary_expression' and
                          parent.child_by_field_name('operator').text != b'+')
            if not is_key and not comparison:
                result.append((node, text))
            return
        if node.type == 'template_string':
            # 模板含運算式，先保留整段並在殘留報告列出。
            return
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return result


def js_display_slot(node, rel):
    parent = node.parent
    if parent.type == 'pair':
        current = parent
        while current and current.type != 'variable_declarator':
            current = current.parent
        if current:
            return current.child_by_field_name('name').text.decode() in {
                'PB_ID2ZH', 'PB_TYPE2ZH', 'PB_BID2ZH', 'PB_EN2ZH',
                'PB_EXTRA_ID2ZH', 'PB_ZH_ALIAS', 'FLAME_ID2ZH'}
        return False
    current = parent
    while current:
        if current.type == 'assignment_expression':
            left = current.child_by_field_name('left').text.decode()
            return left.endswith('.statusMessage')
        if current.type == 'arguments':
            call = current.parent
            if call.type != 'call_expression':
                return False
            function = call.child_by_field_name('function')
            text = function.text.decode()
            prop = function.child_by_field_name('property')
            method = prop.text.decode() if prop else text
            arguments = current.named_children
            # 外層 arguments 的直屬節點才是參數。
            argument = node
            while argument.parent != current:
                argument = argument.parent
            position = arguments.index(argument)
            if text.startswith('Text.'):
                return method not in {'translate', 'translatable'}
            if text in {'console.info', 'console.warn', 'say', 'done', 'addAnnouncement'}:
                return True
            if method in {'displayName', 'sourceName', 'text', 'showText', 'tooltip',
                          'hover', 'append', 'tell'}:
                return True
            if method == 'name' and 'allthemods.create(' in text:
                return True
            if method == 'scene':
                return position == 1
            if text in {'allthemods.add', '$SystemToast.add'}:
                return position >= 1
            if text == 'ns.replace':
                return position == 1
            if text == 'event.cancel':
                return position == 0
            if text == 'event.checkModVersion':
                return position == 2
            if text == 'event.checkModLoaded':
                return position == 1
            if '/Modern-Industrialization/' in rel:
                if method == 'simpleElectricCraftingMultiBlock':
                    return position == 1
                if rel.endswith('/casing.js'):
                    return ((method == 'register' and position in (1, 2)) or
                            (method in {'fluid', 'item'} and position == 0))
            return False
        if current.type in {'statement_block', 'program', 'variable_declarator'}:
            return False
        current = current.parent
    return False


def js_decode(text):
    body = text[1:-1]
    if text.startswith("'"):
        body = body.replace("\\'", "'").replace('"', '\\"')
    return json.loads('"' + body + '"')


def js_encode(value, quote):
    body = json.dumps(value, ensure_ascii=False)[1:-1]
    if quote == "'":
        body = body.replace('\\"', '"').replace("'", "\\'")
    return quote + body + quote
