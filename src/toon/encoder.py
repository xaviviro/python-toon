"""Core TOON encoding functionality."""

import warnings
from typing import Any, Optional

from .constants import DEFAULT_DELIMITER, DELIMITERS
from .encoders import encode_value
from .normalize import normalize_value
from .types import EncodeOptions, ResolvedEncodeOptions
from .writer import LineWriter


def encode(value: Any, options: Optional[EncodeOptions] = None) -> str:
    """Encode a value into TOON format.

    Args:
        value: The value to encode (must be JSON-serializable after normalization)
        options: Optional encoding options

    Returns:
        TOON-formatted string (LF line endings, no trailing newline)

    Raises:
        ValueError: If options are invalid or a string contains an unpaired surrogate
    """
    normalized = normalize_value(value)
    resolved_options = resolve_options(options)
    writer = LineWriter(resolved_options.indent)
    encode_value(normalized, resolved_options, writer, 0)
    return writer.to_string()


def resolve_options(options: Optional[EncodeOptions]) -> ResolvedEncodeOptions:
    """Resolve encoding options with defaults.

    Args:
        options: Optional user-provided options

    Returns:
        Resolved options with defaults applied
    """
    if options is None:
        return ResolvedEncodeOptions()

    indent = options.get("indent", 2)
    delimiter = options.get("delimiter", DEFAULT_DELIMITER)

    if options.get("lengthMarker"):
        warnings.warn(
            "The 'lengthMarker' option is deprecated and ignored: TOON spec 4 removed "
            "the '#' length marker.",
            DeprecationWarning,
            stacklevel=3,
        )

    # Resolve delimiter if it's a key
    if delimiter in DELIMITERS:
        delimiter = DELIMITERS[delimiter]
    if delimiter not in DELIMITERS.values():
        raise ValueError(f"Invalid delimiter {delimiter!r}: use ',', '\\t' or '|'")
    if not isinstance(indent, int) or isinstance(indent, bool) or indent < 1:
        raise ValueError(f"Invalid indent {indent!r}: must be a positive integer")

    return ResolvedEncodeOptions(indent=indent, delimiter=delimiter)
