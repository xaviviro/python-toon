"""Tests for TOON decoder."""

import pytest

from toon import ToonDecodeError, decode
from toon.types import DecodeOptions


class TestBasicDecoding:
    """Test basic decoding functionality."""

    def test_decode_simple_object(self):
        """Test decoding a simple object."""
        toon = """id: 123
name: Ada
active: true"""
        result = decode(toon)
        assert result == {"id": 123, "name": "Ada", "active": True}

    def test_decode_nested_object(self):
        """Test decoding a nested object."""
        toon = """user:
  id: 123
  name: Ada"""
        result = decode(toon)
        assert result == {"user": {"id": 123, "name": "Ada"}}

    def test_decode_inline_primitive_array(self):
        """Test decoding an inline primitive array."""
        toon = "tags[3]: reading,gaming,coding"
        result = decode(toon)
        assert result == {"tags": ["reading", "gaming", "coding"]}

    def test_decode_empty_array(self):
        """Test decoding an empty array."""
        toon = "items[0]:"
        result = decode(toon)
        assert result == {"items": []}

    def test_decode_tabular_array(self):
        """Test decoding a tabular array."""
        toon = """items[2]{sku,qty,price}:
  A1,2,9.99
  B2,1,14.5"""
        result = decode(toon)
        assert result == {
            "items": [
                {"sku": "A1", "qty": 2, "price": 9.99},
                {"sku": "B2", "qty": 1, "price": 14.5},
            ]
        }

    def test_decode_list_array_with_objects(self):
        """Test decoding a list array with objects."""
        toon = """items[2]:
  - id: 1
    name: First
  - id: 2
    name: Second"""
        result = decode(toon)
        assert result == {
            "items": [
                {"id": 1, "name": "First"},
                {"id": 2, "name": "Second"},
            ]
        }

    def test_decode_list_array_with_primitives(self):
        """Test decoding a list array with primitives."""
        toon = """items[3]:
  - 1
  - foo
  - true"""
        result = decode(toon)
        assert result == {"items": [1, "foo", True]}

    def test_decode_root_array(self):
        """Test decoding a root array."""
        toon = "[3]: a,b,c"
        result = decode(toon)
        assert result == ["a", "b", "c"]

    def test_decode_root_primitive(self):
        """Test decoding a root primitive."""
        toon = "hello world"
        result = decode(toon)
        assert result == "hello world"

    def test_decode_quoted_strings(self):
        """Test decoding quoted strings."""
        toon = 'name: "hello, world"'
        result = decode(toon)
        assert result == {"name": "hello, world"}

    def test_decode_escaped_strings(self):
        """Test decoding escaped strings."""
        toon = r'text: "line1\nline2"'
        result = decode(toon)
        assert result == {"text": "line1\nline2"}

    def test_decode_booleans_and_null(self):
        """Test decoding booleans and null."""
        toon = """active: true
inactive: false
missing: null"""
        result = decode(toon)
        assert result == {"active": True, "inactive": False, "missing": None}

    def test_decode_numbers(self):
        """Test decoding various number formats."""
        toon = """int: 42
negative: -10
float: 3.14
exponent: 1e-6"""
        result = decode(toon)
        assert result == {
            "int": 42,
            "negative": -10,
            "float": 3.14,
            "exponent": 1e-6,
        }


class TestDelimiters:
    """Test different delimiter types."""

    def test_decode_tab_delimiter_primitive_array(self):
        """Test tab-delimited primitive array."""
        toon = "tags[3\t]: reading\tgaming\tcoding"
        result = decode(toon)
        assert result == {"tags": ["reading", "gaming", "coding"]}

    def test_decode_tab_delimiter_tabular(self):
        """Test tab-delimited tabular array."""
        toon = """items[2\t]{sku\tqty}:
  A1\t5
  B2\t3"""
        result = decode(toon)
        assert result == {
            "items": [
                {"sku": "A1", "qty": 5},
                {"sku": "B2", "qty": 3},
            ]
        }

    def test_decode_pipe_delimiter_primitive_array(self):
        """Test pipe-delimited primitive array."""
        toon = "tags[3|]: reading|gaming|coding"
        result = decode(toon)
        assert result == {"tags": ["reading", "gaming", "coding"]}

    def test_decode_pipe_delimiter_tabular(self):
        """Test pipe-delimited tabular array."""
        toon = """items[2|]{sku|qty}:
  A1|5
  B2|3"""
        result = decode(toon)
        assert result == {
            "items": [
                {"sku": "A1", "qty": 5},
                {"sku": "B2", "qty": 3},
            ]
        }


class TestLegacyLengthMarker:
    """The '#' length marker was removed from the TOON spec."""

    def test_length_marker_is_rejected(self):
        with pytest.raises(ToonDecodeError, match="malformed bracket"):
            decode("tags[#3]: a,b,c")

    def test_length_marker_falls_through_in_non_strict_mode(self):
        result = decode("tags[#3]: a,b,c", DecodeOptions(strict=False))
        assert result == {"tags[#3]": "a,b,c"}


class TestStrictMode:
    """Test strict mode validation."""

    def test_strict_array_length_mismatch(self):
        """Test that strict mode errors on length mismatch."""
        toon = "items[3]: a,b"  # Declared 3, only 2 values
        with pytest.raises(ToonDecodeError, match="expected 3"):
            decode(toon)

    def test_non_strict_array_length_mismatch(self):
        """Test that non-strict mode allows length mismatch."""
        toon = "items[3]: a,b"
        options = DecodeOptions(strict=False)
        result = decode(toon, options)
        assert result == {"items": ["a", "b"]}

    def test_strict_indentation_error(self):
        """Test that strict mode errors on bad indentation."""
        toon = """user:
   id: 1"""  # 3 spaces instead of 2
        with pytest.raises(ToonDecodeError, match="not a multiple"):
            decode(toon)

    def test_strict_tabular_row_width_mismatch(self):
        """Test that strict mode errors on row width mismatch."""
        toon = """items[2]{a,b,c}:
  1,2,3
  4,5"""  # Second row has only 2 values instead of 3
        with pytest.raises(ToonDecodeError, match="expected 3"):
            decode(toon)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_decode_empty_string_value(self):
        """Test decoding empty string values."""
        toon = 'text: ""'
        result = decode(toon)
        assert result == {"text": ""}

    def test_decode_quoted_keywords(self):
        """Test that quoted keywords remain strings."""
        toon = """items[3]: "true","false","null" """
        result = decode(toon)
        assert result == {"items": ["true", "false", "null"]}

    def test_decode_quoted_numbers(self):
        """Test that quoted numbers remain strings."""
        toon = """items[2]: "42","3.14" """
        result = decode(toon)
        assert result == {"items": ["42", "3.14"]}

    def test_invalid_escape_sequence(self):
        """Test that invalid escape sequences error."""
        toon = r'text: "invalid\x"'
        with pytest.raises(ToonDecodeError, match="invalid escape"):
            decode(toon)

    def test_unterminated_string(self):
        """Test that unterminated strings error."""
        toon = 'text: "unterminated'
        with pytest.raises(ToonDecodeError, match="unterminated"):
            decode(toon)

    def test_missing_colon(self):
        """Test that missing colon errors in strict mode."""
        toon = """key: value
invalid line without colon"""
        with pytest.raises(ToonDecodeError, match="missing colon"):
            decode(toon)


class TestComplexStructures:
    """Test complex nested structures."""

    def test_nested_tabular_in_list(self):
        """Test tabular array inside a list item."""
        toon = """items[1]:
  - users[2]{id,name}:
      1,Alice
      2,Bob
    status: active"""
        result = decode(toon)
        assert result == {
            "items": [
                {
                    "users": [
                        {"id": 1, "name": "Alice"},
                        {"id": 2, "name": "Bob"},
                    ],
                    "status": "active",
                }
            ]
        }

    def test_array_of_arrays(self):
        """Test array of arrays."""
        toon = """pairs[2]:
  - [2]: 1,2
  - [2]: 3,4"""
        result = decode(toon)
        assert result == {"pairs": [[1, 2], [3, 4]]}

    def test_deeply_nested_objects(self):
        """Test deeply nested object structures."""
        toon = """root:
  level1:
    level2:
      level3:
        value: deep"""
        result = decode(toon)
        assert result == {
            "root": {
                "level1": {
                    "level2": {
                        "level3": {"value": "deep"}
                    }
                }
            }
        }


class TestRoundtrip:
    """Test encoding and decoding roundtrip."""

    def test_roundtrip_simple(self):
        """Test simple roundtrip."""
        from toon import encode

        original = {"id": 123, "name": "Ada", "active": True}
        toon = encode(original)
        decoded = decode(toon)
        assert decoded == original

    def test_roundtrip_tabular(self):
        """Test tabular array roundtrip."""
        from toon import encode

        original = {
            "items": [
                {"sku": "A1", "qty": 2, "price": 9.99},
                {"sku": "B2", "qty": 1, "price": 14.5},
            ]
        }
        toon = encode(original)
        decoded = decode(toon)
        assert decoded == original

    def test_roundtrip_nested(self):
        """Test nested structure roundtrip."""
        from toon import encode

        original = {
            "user": {
                "id": 123,
                "profile": {"name": "Ada", "tags": ["dev", "ops"]},
            }
        }
        toon = encode(original)
        decoded = decode(toon)
        assert decoded == original
