"""Encoders for different value types (spec §8–§10)."""

from typing import Any, Iterator, List, Optional

from .constants import LIST_ITEM_MARKER, LIST_ITEM_PREFIX
from .normalize import is_json_array, is_json_object, is_json_primitive
from .primitives import FieldEntry, encode_key, encode_primitive, format_header
from .types import Depth, JsonArray, JsonObject, JsonValue, ResolvedEncodeOptions
from .writer import LineWriter


def encode_value(
    value: JsonValue, options: ResolvedEncodeOptions, writer: LineWriter, depth: Depth = 0
) -> None:
    """Encode a root value to TOON format.

    Args:
        value: Normalized JSON value
        options: Resolved encoding options
        writer: Line writer for output
        depth: Current indentation depth
    """
    if is_json_primitive(value):
        writer.push(depth, encode_primitive(value, options.delimiter))
    elif is_json_array(value):
        if not value:
            writer.push(depth, "[]")
        else:
            encode_array(value, options, writer, depth, None, allow_tabular=True)
    elif is_json_object(value):
        keyed_fields = detect_keyed_fields(value)
        if keyed_fields is not None:
            encode_keyed_object(value, keyed_fields, options, writer, depth, None)
        else:
            encode_object_fields(value, options, writer, depth)


def encode_object_fields(
    obj: JsonObject, options: ResolvedEncodeOptions, writer: LineWriter, depth: Depth
) -> None:
    """Encode each field of an object at the given depth."""
    for key, value in obj.items():
        encode_field(key, value, options, writer, depth)


def encode_field(
    key: str, value: JsonValue, options: ResolvedEncodeOptions, writer: LineWriter, depth: Depth
) -> None:
    """Encode a single object field (spec §8).

    Args:
        key: Key name
        value: Value to encode
        options: Resolved encoding options
        writer: Line writer for output
        depth: Current indentation depth
    """
    encoded_key = encode_key(key)
    if is_json_primitive(value):
        writer.push(depth, f"{encoded_key}: {encode_primitive(value, options.delimiter)}")
    elif is_json_array(value):
        if not value:
            writer.push(depth, f"{encoded_key}: []")
        else:
            encode_array(value, options, writer, depth, key, allow_tabular=True)
    elif is_json_object(value):
        keyed_fields = detect_keyed_fields(value)
        if keyed_fields is not None:
            encode_keyed_object(value, keyed_fields, options, writer, depth, key)
        else:
            writer.push(depth, f"{encoded_key}:")
            encode_object_fields(value, options, writer, depth + 1)


def encode_array(
    arr: JsonArray,
    options: ResolvedEncodeOptions,
    writer: LineWriter,
    depth: Depth,
    key: Optional[str],
    allow_tabular: bool,
) -> None:
    """Encode a non-empty array, choosing the form from its shape (spec §9).

    Args:
        arr: Non-empty array
        options: Resolved encoding options
        writer: Line writer for output
        depth: Depth of the header line
        key: Optional key name
        allow_tabular: False for keyless arrays inside list items, where only the
            inline and list forms are available
    """
    delimiter = options.delimiter

    if all(is_json_primitive(item) for item in arr):
        values = delimiter.join(encode_primitive(item, delimiter) for item in arr)
        writer.push(depth, f"{format_header(key, len(arr), delimiter)} {values}")
        return

    if allow_tabular:
        fields = detect_fields(arr)
        if fields is not None:
            writer.push(depth, format_header(key, len(arr), delimiter, fields))
            for obj in arr:
                writer.push(depth + 1, encode_row(obj, fields, options))
            return

    writer.push(depth, format_header(key, len(arr), delimiter))
    for item in arr:
        encode_list_item(item, options, writer, depth + 1)


def encode_list_item(
    item: JsonValue, options: ResolvedEncodeOptions, writer: LineWriter, depth: Depth
) -> None:
    """Encode one element of an array in list form (spec §9.2, §9.4)."""
    delimiter = options.delimiter
    if is_json_primitive(item):
        writer.push(depth, f"{LIST_ITEM_PREFIX}{encode_primitive(item, delimiter)}")
    elif is_json_array(item):
        if not item:
            writer.push(depth, f"{LIST_ITEM_PREFIX}{format_header(None, 0, delimiter)}")
        else:
            marker = writer.mark()
            encode_array(item, options, writer, depth, None, allow_tabular=False)
            writer.hoist_to_list_item(marker, depth)
            # Nested items were written relative to the header, which now sits on the
            # hyphen line; they already are at depth + 1 as required.
    elif is_json_object(item):
        encode_object_as_list_item(item, options, writer, depth)


def encode_object_as_list_item(
    obj: JsonObject, options: ResolvedEncodeOptions, writer: LineWriter, depth: Depth
) -> None:
    """Encode an object as a list item (spec §10).

    The first field is carried on the hyphen line; it is encoded as if it stood at
    depth + 1, so its own content lands at depth + 2 and the remaining fields at
    depth + 1.
    """
    if not obj:
        writer.push(depth, LIST_ITEM_MARKER)
        return

    items = iter(obj.items())
    first_key, first_value = next(items)
    marker = writer.mark()
    encode_field(first_key, first_value, options, writer, depth + 1)
    writer.hoist_to_list_item(marker, depth)

    for key, value in items:
        encode_field(key, value, options, writer, depth + 1)


def encode_keyed_object(
    obj: JsonObject,
    fields: List[FieldEntry],
    options: ResolvedEncodeOptions,
    writer: LineWriter,
    depth: Depth,
    key: Optional[str],
) -> None:
    """Encode an object of uniform objects in keyed tabular form (spec §9.5)."""
    writer.push(depth, format_header(key, len(obj), options.delimiter, fields, keyed=True))
    for entry_key, entry_value in obj.items():
        row = encode_row(entry_value, fields, options)
        writer.push(depth + 1, f"{encode_key(entry_key)}: {row}")


def encode_row(obj: JsonObject, fields: List[FieldEntry], options: ResolvedEncodeOptions) -> str:
    """Encode an object's leaf values as a delimiter-joined row."""
    delimiter = options.delimiter
    return delimiter.join(encode_primitive(value, delimiter) for value in iter_leaves(obj, fields))


def iter_leaves(obj: JsonObject, fields: List[FieldEntry]) -> Iterator[Any]:
    """Yield leaf values in depth-first, pre-order field-list order."""
    for name, sub_fields in fields:
        if sub_fields is None:
            yield obj[name]
        else:
            yield from iter_leaves(obj[name], sub_fields)


def detect_fields(values: List[Any]) -> Optional[List[FieldEntry]]:
    """Return the field list if ``values`` qualifies for a tabular form (spec §9.3).

    Every value must be a non-empty object, all with the same key set, and every
    column must be uniform-primitive or nested-uniform (recursively).

    Args:
        values: Array elements, or entry values of a keyed tabular candidate

    Returns:
        The field list in the first object's encounter order, or None
    """
    first = values[0] if values else None
    if not isinstance(first, dict) or not first:
        return None

    key_set = set(first)
    for value in values:
        if not isinstance(value, dict) or len(value) != len(key_set) or set(value) != key_set:
            return None

    fields: List[FieldEntry] = []
    for name in first:
        column = [value[name] for value in values]
        if all(is_json_primitive(cell) for cell in column):
            fields.append((name, None))
        else:
            sub_fields = detect_fields(column)
            if sub_fields is None:
                return None
            fields.append((name, sub_fields))
    return fields


def detect_keyed_fields(obj: JsonObject) -> Optional[List[FieldEntry]]:
    """Return the field list if ``obj`` qualifies for keyed tabular form (spec §9.5)."""
    if len(obj) < 2:
        return None
    return detect_fields(list(obj.values()))
