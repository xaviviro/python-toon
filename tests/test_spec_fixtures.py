"""Conformance tests against the official TOON spec fixtures.

Fixtures are vendored from https://github.com/toon-format/spec/tree/main/tests/fixtures
(MIT licensed). Tests are keyed on file path and array index, as the fixture README
recommends.
"""

import json
from pathlib import Path

import pytest

from toon import DecodeOptions, decode, encode

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load(category):
    cases = []
    for path in sorted((FIXTURES_DIR / category).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for index, test in enumerate(data["tests"]):
            cases.append(pytest.param(test, id=f"{path.stem}[{index}]"))
    return cases


def _encode_options(options):
    if not options:
        return None
    resolved = {}
    if "delimiter" in options:
        resolved["delimiter"] = options["delimiter"]
    if "indentSize" in options:
        resolved["indent"] = options["indentSize"]
    return resolved


def _decode_options(options):
    options = options or {}
    return DecodeOptions(
        indent=options.get("indentSize", 2),
        strict=options.get("strict", True),
    )


@pytest.mark.parametrize("test", _load("encode"))
def test_encode_fixture(test):
    options = _encode_options(test.get("options"))
    if test.get("shouldError"):
        with pytest.raises(Exception):
            encode(test["input"], options)
    else:
        assert encode(test["input"], options) == test["expected"]


@pytest.mark.parametrize("test", _load("decode"))
def test_decode_fixture(test):
    options = _decode_options(test.get("options"))
    if test.get("shouldError"):
        with pytest.raises(Exception):
            decode(test["input"], options)
    else:
        result = decode(test["input"], options)
        # Compare with json round-trip so key order and int/float equality match JSON semantics
        assert result == test["expected"]
        assert list(_key_paths(result)) == list(_key_paths(test["expected"]))


def _key_paths(value, prefix=()):
    """Yield key paths in order, so decoded key order is checked too."""
    if isinstance(value, dict):
        for key, child in value.items():
            yield prefix + (key,)
            yield from _key_paths(child, prefix + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _key_paths(child, prefix + (index,))
