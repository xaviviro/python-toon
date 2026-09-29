"""TOON decoder (spec §4–§14).

Numeric policy (spec §4): tokens without a fraction or exponent decode to ``int``
(arbitrary precision, lossless). Other numeric tokens decode to ``float``, except that
integral values below 2**53 decode to ``int`` (e.g. ``2.5e2`` -> ``250``, ``-0.0`` -> ``0``);
values beyond the float range decode to ``float('inf')``.

Non-strict indentation (spec §12): depth is ``floor(spaces / indent)``, and each
leading tab counts as one indentation level.
"""

import re
from typing import List, NamedTuple, Optional, Tuple, Union

from .constants import COMMA, FALSE_LITERAL, NULL_LITERAL, PIPE, TAB, TRUE_LITERAL
from .types import DecodeOptions, JsonObject, JsonValue

_NUMBER_RE = re.compile(r"-?([0-9]+)(\.[0-9]+)?([eE][+-]?[0-9]+)?")
_BRACKET_RE = re.compile(r"(0|[1-9][0-9]*)(:?)([\t|]?)")
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_SIMPLE_ESCAPES = {"\\": "\\", '"': '"', "n": "\n", "r": "\r", "t": "\t"}
_DELIMITERS = (COMMA, TAB, PIPE)
# Integral fraction/exponent tokens below this magnitude decode to int (exact in a float)
_MAX_SAFE_INTEGER = 2**53

# A field entry is (name, nested field list or None for a leaf field)
Fields = List[Tuple[str, Optional["Fields"]]]


class ToonDecodeError(ValueError):
    """TOON decoding error."""


class _MalformedHeader(ToonDecodeError):
    """Header syntax error; non-strict decoders fall through to key-value parsing."""


class Line(NamedTuple):
    """A comment-stripped line of the document."""

    content: str
    depth: int
    number: int
    blank: bool


class Header(NamedTuple):
    """A parsed array or keyed tabular header."""

    key: Optional[str]
    length: int
    delimiter: str
    keyed: bool
    fields: Optional[Fields]
    rest: str


def decode(input_str: Union[str, bytes], options: Optional[DecodeOptions] = None) -> JsonValue:
    """Decode a TOON document into Python values.

    Args:
        input_str: TOON text, or UTF-8 bytes
        options: Optional decoding options (indent, strict)

    Returns:
        Decoded value (dict, list or primitive)

    Raises:
        ToonDecodeError: If the input is not valid TOON
    """
    if options is None:
        options = DecodeOptions()
    if isinstance(input_str, (bytes, bytearray)):
        try:
            input_str = bytes(input_str).decode("utf-8", "strict" if options.strict else "replace")
        except UnicodeDecodeError as e:
            raise ToonDecodeError(f"Input is not valid UTF-8: {e}") from e

    lines = _split_lines(input_str, options.indent, options.strict)
    try:
        return _Parser(lines, options.strict).parse_document()
    except RecursionError as e:
        raise ToonDecodeError("Document nesting is too deep to decode") from e


def _split_lines(text: str, indent: int, strict: bool) -> List[Line]:
    """Split text into lines, removing BOM, CRs, trailing spaces and comment lines."""
    if text.startswith("﻿"):
        text = text[1:]

    lines = []
    for number, raw in enumerate(text.split("\n"), 1):
        if raw.endswith("\r"):
            raw = raw[:-1]
        raw = raw.rstrip(" ")
        if raw.lstrip(" ").startswith("#"):
            continue
        if not raw.strip(" \t"):
            lines.append(Line("", 0, number, True))
            continue

        spaces = tabs = 0
        index = 0
        while raw[index] in " \t":
            if raw[index] == " ":
                spaces += 1
            else:
                tabs += 1
            index += 1

        if strict:
            if tabs:
                raise ToonDecodeError(f"Line {number}: tabs are not allowed in indentation")
            if spaces % indent:
                raise ToonDecodeError(
                    f"Line {number}: indentation of {spaces} spaces is not a multiple of {indent}"
                )
        lines.append(Line(raw[index:], spaces // indent + tabs, number, False))
    return lines


class _Parser:
    """Recursive-descent parser over the comment-stripped line sequence."""

    def __init__(self, lines: List[Line], strict: bool) -> None:
        self.lines = lines
        self.strict = strict
        self.pos = 0

    # ----------------------------------------------------------------- helpers

    def error(self, line: Optional[Line], message: str) -> ToonDecodeError:
        prefix = f"Line {line.number}: " if line is not None else ""
        return ToonDecodeError(prefix + message)

    def peek(self, depth: int) -> Optional[Tuple[int, Line, bool]]:
        """Return the next non-blank line if it is at ``depth`` or deeper.

        Returns (index, line, skipped_blank_lines) without consuming anything.
        """
        index = self.pos
        skipped = False
        while index < len(self.lines) and self.lines[index].blank:
            index += 1
            skipped = True
        if index >= len(self.lines) or self.lines[index].depth < depth:
            return None
        return index, self.lines[index], skipped

    def accept(self, peeked: Tuple[int, Line, bool], in_span: bool) -> Line:
        """Consume a peeked line, enforcing the header-span blank line rule (§12)."""
        index, line, skipped = peeked
        if skipped and in_span and self.strict:
            raise self.error(line, "blank lines are not allowed inside arrays")
        self.pos = index + 1
        return line

    def skip_over_indented(self, line: Line) -> None:
        """Handle a line deeper than its scope's content depth (§8, §14.2)."""
        if self.strict:
            raise self.error(line, "unexpected indentation")
        if _find_unquoted(line.content, ":") < 0:
            raise self.error(line, f"unexpected value line: {line.content!r}")

    def assign(self, obj: JsonObject, key: str, value: JsonValue, line: Line) -> None:
        """Set a key, erroring on duplicates in strict mode (last write wins otherwise)."""
        if self.strict and key in obj:
            raise self.error(line, f"duplicate key {key!r}")
        obj[key] = value

    def value(self, token: str, line: Line) -> JsonValue:
        try:
            return _parse_primitive(token)
        except ToonDecodeError as e:
            raise self.error(line, str(e)) from None

    def key(self, token: str, line: Line) -> str:
        try:
            return _parse_key(token)
        except ToonDecodeError as e:
            raise self.error(line, str(e)) from None

    # ---------------------------------------------------------------- document

    def parse_document(self) -> JsonValue:
        non_blank = [(index, line) for index, line in enumerate(self.lines) if not line.blank]
        if not non_blank:
            return {}

        first_index, first = non_blank[0]
        if first.depth == 0:
            header = self.try_header(first.content, first)
            if header is not None and header.key is None:
                self.pos = first_index + 1
                result = self.parse_header_value(header, first, 1, False)
                self.check_trailing()
                return result
            if first.content == "[]":
                self.pos = first_index + 1
                self.check_trailing()
                return []
            if len(non_blank) == 1 and header is None and _find_unquoted(first.content, ":") < 0:
                return self.value(first.content, first)

        root: JsonObject = {}
        self.parse_object_body(root, 0, False)
        return root

    def check_trailing(self) -> None:
        """Reject content after a completed root array or keyed object (§5)."""
        peeked = self.peek(0)
        if peeked is not None and self.strict:
            raise self.error(peeked[1], "unexpected content after the root value")

    # ----------------------------------------------------------------- objects

    def parse_object_body(self, obj: JsonObject, depth: int, in_span: bool) -> None:
        """Parse the fields of an object whose content is at ``depth``."""
        while True:
            peeked = self.peek(depth)
            if peeked is None:
                return
            line = self.accept(peeked, in_span)
            if line.depth > depth:
                self.skip_over_indented(line)
                continue
            self.parse_field_line(obj, line.content, line, depth, in_span)

    def parse_field_line(
        self, obj: JsonObject, content: str, line: Line, depth: int, in_span: bool
    ) -> None:
        """Parse a key-value or header line whose field stands at ``depth``."""
        header = self.try_header(content, line)
        if header is not None:
            if header.key is not None:
                array = self.parse_header_value(header, line, depth + 1, in_span)
                self.assign(obj, header.key, array, line)
                return
            if self.strict:
                raise self.error(
                    line, "a keyless array header is only valid at the root or in a list item"
                )

        colon = _find_unquoted(content, ":")
        if colon < 0:
            raise self.error(line, f"missing colon after key: {content!r}")
        key = self.key(content[:colon], line)
        rest = content[colon + 1 :].strip(" ")
        value: JsonValue
        if not rest:
            nested: JsonObject = {}
            self.parse_object_body(nested, depth + 1, in_span)
            value = nested
        elif rest == "[]":
            value = []
        else:
            value = self.value(rest, line)
        self.assign(obj, key, value, line)

    # ------------------------------------------------------------------ headers

    def try_header(self, content: str, line: Line) -> Optional[Header]:
        """Parse ``content`` as an array or keyed header.

        Returns None when the line is not a header. Malformed headers raise in strict
        mode and return None in non-strict mode (key-value fall-through, §6).
        """
        if content.startswith('"'):
            try:
                key, bracket = _parse_quoted(content, 0)
            except ToonDecodeError:
                return None
            if bracket >= len(content) or content[bracket] != "[":
                return None
            if _find_unquoted(content, ":", bracket) < 0:
                return None
            key_or_none: Optional[str] = key
        else:
            bracket = _find_unquoted(content, "[")
            colon = _find_unquoted(content, ":")
            if bracket < 0 or colon < 0 or colon < bracket:
                return None
            key_or_none = content[:bracket] or None

        try:
            return self._parse_header(content, bracket, key_or_none, not content.startswith('"'))
        except _MalformedHeader as e:
            if self.strict:
                raise self.error(line, str(e)) from None
            return None

    def _parse_header(
        self, content: str, bracket: int, key: Optional[str], unquoted_key: bool
    ) -> Header:
        if unquoted_key and key is not None and (" " in key or "\t" in key):
            raise _MalformedHeader(f"whitespace is not allowed in an array header key: {key!r}")

        close = content.find("]", bracket)
        if close < 0:
            raise _MalformedHeader("unterminated bracket segment")
        match = _BRACKET_RE.fullmatch(content[bracket + 1 : close])
        if match is None:
            raise _MalformedHeader(f"malformed bracket segment: {content[bracket : close + 1]!r}")
        length = int(match.group(1))
        keyed = bool(match.group(2))
        delimiter = match.group(3) or COMMA

        pos = close + 1
        fields = None
        if pos < len(content) and content[pos] == "{":
            fields, pos = self._parse_fields(content, pos, delimiter)
        if pos >= len(content) or content[pos] != ":":
            raise _MalformedHeader("expected ':' after the array header")
        rest = content[pos + 1 :].strip(" ")

        if keyed and fields is None:
            raise _MalformedHeader("a keyed header requires a field list")
        if fields is not None and rest:
            raise _MalformedHeader("unexpected content after a tabular header")
        return Header(key, length, delimiter, keyed, fields, rest)

    def _parse_fields(self, text: str, pos: int, delimiter: str) -> Tuple[Fields, int]:
        """Parse a (possibly nested) field list starting at ``text[pos] == '{'``."""
        pos += 1
        fields: Fields = []
        names = set()
        while True:
            if pos < len(text) and text[pos] == '"':
                try:
                    name, pos = _parse_quoted(text, pos)
                except ToonDecodeError as e:
                    raise _MalformedHeader(str(e)) from None
            else:
                start = pos
                while pos < len(text) and text[pos] not in "{}" and text[pos] != delimiter:
                    pos += 1
                name = text[start:pos].strip(" ")
                if not name:
                    raise _MalformedHeader("empty field name in field list")
                if '"' in name or any(d in name for d in _DELIMITERS):
                    raise _MalformedHeader(f"field list delimiter mismatch near {name!r}")

            sub_fields = None
            if pos < len(text) and text[pos] == "{":
                sub_fields, pos = self._parse_fields(text, pos, delimiter)
            if name in names and self.strict:
                raise _MalformedHeader(f"duplicate field name {name!r}")
            names.add(name)
            fields.append((name, sub_fields))

            if pos >= len(text):
                raise _MalformedHeader("unmatched '{' in field list")
            if text[pos] == delimiter:
                pos += 1
            elif text[pos] == "}":
                return fields, pos + 1
            else:
                raise _MalformedHeader(f"unexpected {text[pos]!r} in field list")

    def parse_header_value(
        self, header: Header, line: Line, depth: int, in_span: bool
    ) -> JsonValue:
        """Decode the value opened by ``header``; its content is at ``depth``."""
        if header.keyed:
            return self.parse_keyed(header, line, depth, in_span)
        if header.fields is not None:
            return self.parse_tabular(header, line, depth, in_span)
        if header.rest:
            values = [self.value(t, line) for t in _split_delimited(header.rest, header.delimiter)]
            self.check_count(header, len(values), line, "values")
            return values
        return self.parse_list(header, line, depth, in_span)

    def check_count(self, header: Header, count: int, line: Line, what: str) -> None:
        if self.strict and count != header.length:
            raise self.error(line, f"expected {header.length} {what}, found {count}")

    # ------------------------------------------------------------------- arrays

    def parse_tabular(self, header: Header, line: Line, depth: int, in_span: bool) -> JsonValue:
        assert header.fields is not None
        leaf_count = _count_leaves(header.fields)
        rows = []
        span = in_span
        while True:
            peeked = self.peek(depth)
            if peeked is None:
                break
            row_line = peeked[1]
            if row_line.depth == depth:
                delimiter_at = _find_unquoted(row_line.content, header.delimiter)
                colon_at = _find_unquoted(row_line.content, ":")
                if colon_at >= 0 and (delimiter_at < 0 or colon_at < delimiter_at):
                    break
            self.accept(peeked, span)
            if row_line.depth > depth:
                self.skip_over_indented(row_line)
                continue
            span = True
            cells = _split_delimited(row_line.content, header.delimiter)
            if self.strict and len(cells) != leaf_count:
                raise self.error(row_line, f"expected {leaf_count} cells, found {len(cells)}")
            rows.append(self.materialize(header.fields, cells, row_line))
        self.check_count(header, len(rows), line, "rows")
        return rows

    def parse_keyed(self, header: Header, line: Line, depth: int, in_span: bool) -> JsonValue:
        assert header.fields is not None
        leaf_count = _count_leaves(header.fields)
        entries: JsonObject = {}
        count = 0
        span = in_span
        while True:
            peeked = self.peek(depth)
            if peeked is None:
                break
            entry_line = self.accept(peeked, span)
            if entry_line.depth > depth:
                self.skip_over_indented(entry_line)
                continue
            span = True
            colon = _find_unquoted(entry_line.content, ":")
            if colon < 0:
                if self.strict:
                    raise self.error(entry_line, "expected 'key: cells' entry row")
                continue
            key = self.key(entry_line.content[:colon], entry_line)
            cells = _split_delimited(entry_line.content[colon + 1 :], header.delimiter)
            if self.strict and len(cells) != leaf_count:
                raise self.error(entry_line, f"expected {leaf_count} cells, found {len(cells)}")
            self.assign(
                entries, key, self.materialize(header.fields, cells, entry_line), entry_line
            )
            count += 1
        self.check_count(header, count, line, "entries")
        return entries

    def materialize(self, fields: Fields, cells: List[str], line: Line) -> JsonObject:
        """Build an object from row cells, walking the field list depth-first."""
        position = 0

        def build(group: Fields) -> JsonObject:
            nonlocal position
            obj: JsonObject = {}
            for name, sub_fields in group:
                if sub_fields is not None:
                    obj[name] = build(sub_fields)
                elif position < len(cells):
                    obj[name] = self.value(cells[position], line)
                    position += 1
            return obj

        return build(fields)

    def parse_list(self, header: Header, line: Line, depth: int, in_span: bool) -> JsonValue:
        items = []
        span = in_span
        while True:
            peeked = self.peek(depth)
            if peeked is None:
                break
            item_line = peeked[1]
            content = item_line.content
            if item_line.depth == depth and not (content == "-" or content.startswith("- ")):
                break
            self.accept(peeked, span)
            if item_line.depth > depth:
                self.skip_over_indented(item_line)
                continue
            span = True
            items.append(self.parse_list_item(content[2:].strip(" "), item_line, depth))
        self.check_count(header, len(items), line, "list items")
        return items

    def parse_list_item(self, rest: str, line: Line, depth: int) -> JsonValue:
        """Parse the text after a list-item marker at ``depth`` (§9.4, §10)."""
        if not rest:
            return {}
        if rest == "[]":
            return []

        header = self.try_header(rest, line)
        if header is not None and header.key is None:
            if header.fields is None:
                return self.parse_header_value(header, line, depth + 1, True)
            if self.strict:
                raise self.error(line, "a keyless tabular header is only valid at the root")

        if _find_unquoted(rest, ":") >= 0:
            # Fields of a list-item object stand at depth + 1; the first one is
            # carried on the hyphen line.
            obj: JsonObject = {}
            self.parse_field_line(obj, rest, line, depth + 1, True)
            self.parse_object_body(obj, depth + 1, True)
            return obj
        return self.value(rest, line)


# --------------------------------------------------------------------- tokens


def _find_unquoted(text: str, target: str, start: int = 0) -> int:
    """Return the index of the first ``target`` outside double quotes, or -1."""
    in_quotes = False
    index = start
    while index < len(text):
        char = text[index]
        if in_quotes:
            if char == "\\":
                index += 1
            elif char == '"':
                in_quotes = False
        elif char == '"':
            in_quotes = True
        elif char == target:
            return index
        index += 1
    return -1


def _parse_quoted(text: str, start: int) -> Tuple[str, int]:
    """Parse a quoted string at ``text[start] == '"'``.

    Returns the unescaped value and the index just past the closing quote.
    """
    parts: List[str] = []
    index = start + 1
    while index < len(text):
        char = text[index]
        if char == '"':
            return "".join(parts), index + 1
        if char != "\\":
            parts.append(char)
            index += 1
            continue
        if index + 1 >= len(text):
            break
        escape = text[index + 1]
        if escape in _SIMPLE_ESCAPES:
            parts.append(_SIMPLE_ESCAPES[escape])
            index += 2
        elif escape == "u":
            digits = text[index + 2 : index + 6]
            if len(digits) != 4 or not all(d in _HEX_DIGITS for d in digits):
                raise ToonDecodeError(f"invalid unicode escape: \\u{digits}")
            codepoint = int(digits, 16)
            if 0xD800 <= codepoint <= 0xDFFF:
                raise ToonDecodeError(f"surrogate escapes are not allowed: \\u{digits}")
            parts.append(chr(codepoint))
            index += 6
        else:
            raise ToonDecodeError(f"invalid escape sequence: \\{escape}")
    raise ToonDecodeError("unterminated string")


def _parse_complete_quoted(token: str) -> str:
    value, end = _parse_quoted(token, 0)
    if end != len(token):
        raise ToonDecodeError(f"unexpected characters after closing quote: {token!r}")
    return value


def _parse_key(token: str) -> str:
    """Decode a key token (§7.4): quoted keys are unescaped, others are literal."""
    token = token.strip(" ")
    if token.startswith('"'):
        return _parse_complete_quoted(token)
    return token


def _parse_primitive(token: str) -> JsonValue:
    """Decode a primitive value token (§4)."""
    token = token.strip(" ")
    if token.startswith('"'):
        return _parse_complete_quoted(token)
    if token == TRUE_LITERAL:
        return True
    if token == FALSE_LITERAL:
        return False
    if token == NULL_LITERAL:
        return None
    number = _parse_number(token)
    return token if number is None else number


def _parse_number(token: str) -> Optional[Union[int, float]]:
    match = _NUMBER_RE.fullmatch(token)
    if match is None:
        return None
    integer_part, fraction, exponent = match.groups()
    if len(integer_part) > 1 and integer_part[0] == "0":
        return None
    if fraction is None and exponent is None:
        return int(token)
    value = float(token)
    if value.is_integer() and abs(value) < _MAX_SAFE_INTEGER:
        return int(value)
    return value


def _split_delimited(text: str, delimiter: str) -> List[str]:
    """Split on unquoted delimiters, trimming spaces around each token (§11.2)."""
    if not text.strip(" "):
        return []
    tokens = []
    start = 0
    while True:
        index = _find_unquoted(text, delimiter, start)
        if index < 0:
            tokens.append(text[start:].strip(" "))
            return tokens
        tokens.append(text[start:index].strip(" "))
        start = index + 1


def _count_leaves(fields: Fields) -> int:
    return sum(1 if sub is None else _count_leaves(sub) for _, sub in fields)
