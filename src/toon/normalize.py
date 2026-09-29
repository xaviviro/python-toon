"""Value normalization for TOON encoding."""

import dataclasses
import math
from collections.abc import Mapping
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, List

from .types import JsonValue


def normalize_value(value: Any) -> JsonValue:
    """Normalize a value to JSON-compatible type.

    Args:
        value: Input value

    Returns:
        JSON-compatible value
    """
    # Handle None and booleans
    if value is None or isinstance(value, bool):
        return value

    # Handle numbers
    if isinstance(value, int):
        # int() also unwraps subclasses such as IntEnum
        return int(value)
    if isinstance(value, float):
        # Convert NaN and Infinity to null
        if math.isnan(value) or math.isinf(value):
            return None
        # Convert -0 to 0
        if value == 0:
            return 0
        return float(value)

    # Handle Decimal
    if isinstance(value, Decimal):
        if not value.is_finite():
            return None
        if value == value.to_integral_value():
            return int(value)
        return float(value)

    # Handle strings
    if isinstance(value, str):
        return value

    # Handle dates
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()

    # Handle lists/tuples
    if isinstance(value, (list, tuple)):
        return [normalize_value(item) for item in value]

    # Handle sets
    if isinstance(value, (set, frozenset)):
        return [normalize_value(item) for item in value]

    # Handle dicts and other mappings
    if isinstance(value, Mapping):
        return {str(key): normalize_value(val) for key, val in value.items()}

    # Handle dataclass instances
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return normalize_value(dataclasses.asdict(value))

    # Handle callables, undefined, symbols -> null
    if callable(value):
        return None

    # Try to convert to string, otherwise null
    try:
        if hasattr(value, "__dict__"):
            return None
        return str(value)
    except Exception:
        return None


def is_json_primitive(value: Any) -> bool:
    """Check if value is a JSON primitive."""
    return value is None or isinstance(value, (bool, int, float, str))


def is_json_array(value: Any) -> bool:
    """Check if value is an array."""
    return isinstance(value, list)


def is_json_object(value: Any) -> bool:
    """Check if value is an object (dict but not a list)."""
    return isinstance(value, dict) and not isinstance(value, list)


def is_array_of_primitives(arr: List[Any]) -> bool:
    """Check if all array elements are primitives."""
    return all(is_json_primitive(item) for item in arr)


def is_array_of_arrays(arr: List[Any]) -> bool:
    """Check if all array elements are arrays."""
    return all(is_json_array(item) for item in arr)


def is_array_of_objects(arr: List[Any]) -> bool:
    """Check if all array elements are objects."""
    return all(is_json_object(item) for item in arr)
