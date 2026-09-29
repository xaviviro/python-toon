"""Primitive encoding utilities: quoting, escaping, numbers, keys and headers."""

import re
from decimal import Decimal
from typing import List, Optional, Tuple, Union

from .constants import (
    BACKSLASH,
    CLOSE_BRACE,
    CLOSE_BRACKET,
    COLON,
    COMMA,
    DOUBLE_QUOTE,
    FALSE_LITERAL,
    NULL_LITERAL,
    OPEN_BRACE,
    OPEN_BRACKET,
    TRUE_LITERAL,
)
from .types import Delimiter, JsonPrimitive

# A field entry is (name, nested field list or None for a leaf field)
FieldEntry = Tuple[str, Optional[List["FieldEntry"]]]

_UNQUOTED_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
_NUMERIC_LIKE_RE = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?(?:e[+-]?[0-9]+)?", re.IGNORECASE)
_NEEDS_QUOTE_CHARS_RE = re.compile(r'[:"\\\[\]{}\x00-\x1f]')
_LONE_SURROGATE_RE = re.compile("[\ud800-\udfff]")

_ESCAPES = {
    BACKSLASH: "\\\\",
    DOUBLE_QUOTE: '\\"',
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def encode_primitive(value: JsonPrimitive, delimiter: str = COMMA) -> str:
    """Encode a primitive value.

    Args:
        value: Primitive value
        delimiter: Delimiter that governs delimiter-aware quoting

    Returns:
        Encoded string
    """
    if value is None:
        return NULL_LITERAL
    if isinstance(value, bool):
        return TRUE_LITERAL if value else FALSE_LITERAL
    if isinstance(value, (int, float)):
        return format_number(value)
    return encode_string_literal(value, delimiter)


def format_number(value: Union[int, float]) -> str:
    """Format a finite number in canonical TOON form (spec §2).

    Numbers with 1e-6 <= |n| < 1e21 (and zero) use plain decimal notation; numbers
    outside that range use JSON exponent notation with an explicit exponent sign.
    """
    if isinstance(value, int):
        return str(value)
    if value == 0:
        return "0"
    if value.is_integer() and abs(value) < 1e21:
        return str(int(value))

    text = repr(value)
    if 1e-6 <= abs(value) < 1e21:
        if "e" in text or "E" in text:
            text = format(Decimal(text), "f")
        return text

    mantissa, _, exponent = text.lower().partition("e")
    if not exponent:
        # repr() only omits the exponent inside the canonical range handled above
        return text
    sign = "-" if exponent.startswith("-") else "+"
    digits = exponent.lstrip("+-").lstrip("0") or "0"
    if "." in mantissa:
        mantissa = mantissa.rstrip("0").rstrip(".")
    return f"{mantissa}e{sign}{digits}"


def check_scalar_values(value: str) -> None:
    """Raise if a string contains an unpaired surrogate (spec §3)."""
    if _LONE_SURROGATE_RE.search(value):
        raise ValueError(f"String contains an unpaired surrogate and cannot be encoded: {value!r}")


def escape_string(value: str) -> str:
    """Escape a string for use inside double quotes (spec §7.1).

    Args:
        value: String to escape

    Returns:
        Escaped string (without surrounding quotes)
    """
    check_scalar_values(value)
    parts = []
    for char in value:
        escaped = _ESCAPES.get(char)
        if escaped is not None:
            parts.append(escaped)
        elif char < " ":
            parts.append(f"\\u{ord(char):04x}")
        else:
            parts.append(char)
    return "".join(parts)


def is_safe_unquoted(value: str, delimiter: str = COMMA) -> bool:
    """Check if a string value can be emitted without quotes (spec §7.2).

    Args:
        value: String to check
        delimiter: Delimiter that governs delimiter-aware quoting

    Returns:
        True if the string doesn't need quotes
    """
    if not value:
        return False
    if value[0] in " \t" or value[-1] in " \t":
        return False
    if value in (NULL_LITERAL, TRUE_LITERAL, FALSE_LITERAL):
        return False
    if _NUMERIC_LIKE_RE.fullmatch(value):
        return False
    if value[0] in "-#":
        return False
    if _NEEDS_QUOTE_CHARS_RE.search(value):
        return False
    if delimiter in value:
        return False
    return True


def encode_string_literal(value: str, delimiter: str = COMMA) -> str:
    """Encode a string, quoting only if necessary.

    Args:
        value: String value
        delimiter: Delimiter that governs delimiter-aware quoting

    Returns:
        Encoded string
    """
    check_scalar_values(value)
    if is_safe_unquoted(value, delimiter):
        return value
    return f"{DOUBLE_QUOTE}{escape_string(value)}{DOUBLE_QUOTE}"


def encode_key(key: str) -> str:
    """Encode an object key, entry key or field name (spec §7.3).

    Args:
        key: Key string

    Returns:
        Encoded key
    """
    check_scalar_values(key)
    if _UNQUOTED_KEY_RE.fullmatch(key):
        return key
    return f"{DOUBLE_QUOTE}{escape_string(key)}{DOUBLE_QUOTE}"


def format_fields(fields: List[FieldEntry], delimiter: Delimiter) -> str:
    """Format a field list, including nested field groups: ``{a,b{c,d}}``."""
    entries = []
    for name, sub_fields in fields:
        entry = encode_key(name)
        if sub_fields is not None:
            entry += format_fields(sub_fields, delimiter)
        entries.append(entry)
    return f"{OPEN_BRACE}{delimiter.join(entries)}{CLOSE_BRACE}"


def format_header(
    key: Optional[str],
    length: int,
    delimiter: Delimiter,
    fields: Optional[List[FieldEntry]] = None,
    keyed: bool = False,
) -> str:
    """Format an array or keyed tabular header (spec §6).

    Args:
        key: Optional key name (None for keyless headers)
        length: Array length or entry count
        delimiter: Active delimiter (omitted from the bracket when it is a comma)
        fields: Optional field list for tabular and keyed headers
        keyed: Whether this is a keyed tabular header (``[N:]``)

    Returns:
        Formatted header string, ending with a colon
    """
    delimiter_symbol = "" if delimiter == COMMA else delimiter
    keyed_marker = COLON if keyed else ""
    header = f"{OPEN_BRACKET}{length}{keyed_marker}{delimiter_symbol}{CLOSE_BRACKET}"
    if key is not None:
        header = encode_key(key) + header
    if fields is not None:
        header += format_fields(fields, delimiter)
    return header + COLON
