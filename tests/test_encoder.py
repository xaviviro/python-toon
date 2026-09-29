"""Tests for TOON encoder."""

import pytest

from toon import encode


class TestPrimitives:
    """Test encoding of primitive values."""

    def test_null(self) -> None:
        assert encode(None) == "null"

    def test_boolean_true(self) -> None:
        assert encode(True) == "true"

    def test_boolean_false(self) -> None:
        assert encode(False) == "false"

    def test_integer(self) -> None:
        assert encode(42) == "42"

    def test_float(self) -> None:
        result = encode(3.14)
        assert result.startswith("3.14")

    def test_string_simple(self) -> None:
        assert encode("hello") == "hello"

    def test_string_with_spaces(self) -> None:
        # Spaces don't require quoting unless there are structural characters
        assert encode("hello world") == "hello world"

    def test_string_empty(self) -> None:
        assert encode("") == '""'

    def test_string_special_keywords(self) -> None:
        assert encode("null") == '"null"'
        assert encode("true") == '"true"'
        assert encode("false") == '"false"'

    def test_string_with_hyphens(self) -> None:
        # Strings starting with hyphen must be quoted (list marker conflict)
        assert encode("-hello") == '"-hello"'
        assert encode("-") == '"-"'
        # Strings containing or ending with hyphen don't need quotes
        assert encode("hello-world") == "hello-world"
        assert encode("hello-") == "hello-"


class TestObjects:
    """Test encoding of objects."""

    def test_simple_object(self) -> None:
        obj = {"name": "Alice", "age": 30}
        result = encode(obj)
        assert "name: Alice" in result
        assert "age: 30" in result

    def test_nested_object(self) -> None:
        obj = {"user": {"name": "Bob", "city": "NYC"}}
        result = encode(obj)
        assert "user:" in result
        assert "name: Bob" in result
        assert "city: NYC" in result

    def test_object_with_null(self) -> None:
        obj = {"value": None}
        result = encode(obj)
        assert "value: null" in result

    def test_empty_object(self) -> None:
        result = encode({})
        assert result == ""


class TestPrimitiveArrays:
    """Test encoding of primitive arrays."""

    def test_number_array(self) -> None:
        arr = [1, 2, 3, 4, 5]
        result = encode(arr)
        # Primitive arrays always include length marker
        assert result == "[5]: 1,2,3,4,5"

    def test_string_array(self) -> None:
        arr = ["apple", "banana", "cherry"]
        result = encode(arr)
        # Primitive arrays always include length marker
        assert result == "[3]: apple,banana,cherry"

    def test_mixed_primitive_array(self) -> None:
        arr = [1, "two", True, None]
        result = encode(arr)
        assert "1" in result
        assert "two" in result
        assert "true" in result
        assert "null" in result

    def test_empty_array(self) -> None:
        result = encode([])
        # Empty root arrays use the literal [] form
        assert result == "[]"


class TestTabularArrays:
    """Test encoding of tabular (uniform object) arrays."""

    def test_simple_tabular(self) -> None:
        arr = [
            {"id": 1, "name": "Alice", "age": 30},
            {"id": 2, "name": "Bob", "age": 25},
            {"id": 3, "name": "Charlie", "age": 35},
        ]
        result = encode(arr)
        # Should have header with keys
        assert "{id,name,age}" in result
        # Should have data rows
        assert "1,Alice,30" in result
        assert "2,Bob,25" in result
        assert "3,Charlie,35" in result

    def test_tabular_with_strings_needing_quotes(self) -> None:
        arr = [
            {"name": "Alice Smith", "city": "New York"},
            {"name": "Bob Jones", "city": "Los Angeles"},
        ]
        result = encode(arr)
        # Spaces don't require quoting in tabular format
        assert "Alice Smith" in result
        assert "New York" in result

    def test_length_marker_is_deprecated_and_ignored(self) -> None:
        arr = [
            {"id": 1, "value": "a"},
            {"id": 2, "value": "b"},
        ]
        with pytest.warns(DeprecationWarning):
            result = encode(arr, {"lengthMarker": "#"})
        assert result == encode(arr)


class TestMixedArrays:
    """Test encoding of mixed/nested arrays."""

    def test_array_of_mixed_types(self) -> None:
        arr = [
            {"name": "Alice"},
            42,
            "hello",
        ]
        result = encode(arr)
        # Should use list format with hyphens
        assert "- " in result
        assert "name: Alice" in result

    def test_nested_array(self) -> None:
        arr = [
            [1, 2, 3],
            [4, 5, 6],
        ]
        result = encode(arr)
        # Nested arrays use list format with length markers
        assert "[2]:" in result
        assert "- " in result
        assert "- [3]: 1,2,3" in result


class TestObjectsWithArrays:
    """Test objects containing arrays."""

    def test_object_with_primitive_array(self) -> None:
        obj = {"numbers": [1, 2, 3]}
        result = encode(obj)
        # Primitive arrays always include length marker
        assert "numbers[3]: 1,2,3" in result

    def test_object_with_tabular_array(self) -> None:
        obj = {
            "users": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ]
        }
        result = encode(obj)
        # Tabular arrays include length with delimiter
        assert "users[2]{id,name}:" in result
        assert "1,Alice" in result


class TestDelimiters:
    """Test different delimiter options."""

    def test_comma_delimiter(self) -> None:
        arr = [1, 2, 3]
        result = encode(arr, {"delimiter": ","})
        assert result == "[3]: 1,2,3"

    def test_tab_delimiter(self) -> None:
        arr = [1, 2, 3]
        result = encode(arr, {"delimiter": "\t"})
        assert result == "[3\t]: 1\t2\t3"

    def test_pipe_delimiter(self) -> None:
        arr = [1, 2, 3]
        result = encode(arr, {"delimiter": "|"})
        assert result == "[3|]: 1|2|3"

    def test_tabular_with_pipe_delimiter(self) -> None:
        arr = [
            {"a": 1, "b": 2},
            {"a": 3, "b": 4},
        ]
        result = encode(arr, {"delimiter": "|"})
        assert "{a|b}" in result
        assert "1|2" in result


class TestIndentation:
    """Test indentation options."""

    def test_default_indentation(self) -> None:
        obj = {"parent": {"child": "value"}}
        result = encode(obj)
        lines = result.split("\n")
        # Child should be indented by 2 spaces
        assert lines[1].startswith("  ")

    def test_custom_indentation(self) -> None:
        obj = {"parent": {"child": "value"}}
        result = encode(obj, {"indent": 4})
        lines = result.split("\n")
        # Child should be indented by 4 spaces
        assert lines[1].startswith("    ")


class TestComplexStructures:
    """Test complex nested structures."""

    def test_deep_nesting(self) -> None:
        obj = {
            "level1": {
                "level2": {
                    "level3": {"value": "deep"},
                }
            }
        }
        result = encode(obj)
        assert "level1:" in result
        assert "level2:" in result
        assert "level3:" in result
        assert "value: deep" in result

    def test_mixed_structure(self) -> None:
        obj = {
            "metadata": {"version": 1, "author": "test"},
            "items": [
                {"id": 1, "name": "Item1"},
                {"id": 2, "name": "Item2"},
            ],
            "tags": ["alpha", "beta", "gamma"],
        }
        result = encode(obj)
        assert "metadata:" in result
        assert "version: 1" in result
        # Tabular arrays include length with delimiter
        assert "items[2]{id,name}:" in result
        # Primitive arrays include length marker
        assert "tags[3]: alpha,beta,gamma" in result


class TestEdgeCases:
    """Test edge cases and special values."""

    def test_infinity(self) -> None:
        assert encode(float("inf")) == "null"
        assert encode(float("-inf")) == "null"

    def test_nan(self) -> None:
        assert encode(float("nan")) == "null"

    def test_callable(self) -> None:
        def func() -> None:
            pass

        assert encode(func) == "null"

    def test_none_in_object(self) -> None:
        obj = {"key": None}
        result = encode(obj)
        assert "key: null" in result

    def test_empty_string_in_array(self) -> None:
        arr = ["", "hello", ""]
        result = encode(arr)
        assert '""' in result
