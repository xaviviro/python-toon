# python-toon encoder/decoder

> **Note**: This is an **unofficial** community implementation. The official TOON projects live in the [toon-format](https://github.com/toon-format) organization, including the [specification](https://github.com/toon-format/spec) and the official Python implementation [toon-format/toon-python](https://github.com/toon-format/toon-python).

**Token-Oriented Object Notation for Python**

A compact data format optimized for transmitting structured information to Large Language Models (LLMs) with 30-60% fewer tokens than JSON.

[![Tests](https://github.com/xaviviro/python-toon/actions/workflows/test.yml/badge.svg)](https://github.com/xaviviro/python-toon/actions)
[![PyPI](https://img.shields.io/pypi/v/python-toon.svg)](https://pypi.org/project/python-toon/)
[![Python Versions](https://img.shields.io/pypi/pyversions/python-toon.svg)](https://pypi.org/project/python-toon/)

[![Downloads](https://static.pepy.tech/badge/python-toon)](https://pepy.tech/project/python-toon)
[![Downloads per month](https://static.pepy.tech/badge/python-toon/month)](https://pepy.tech/project/python-toon)

## Installation

```bash
pip install python-toon
```

## What is TOON?

TOON (Token-Oriented Object Notation) combines YAML's indentation-based structure for nested objects and CSV's tabular format for uniform data rows, optimized specifically for token efficiency in LLM contexts.

**Spec compliance:** `toon-spec: 4.1`. The encoder and decoder pass the full language-agnostic fixture suite of the [official TOON specification](https://github.com/toon-format/spec) (vendored in `tests/fixtures/`).

### Key Features

- **30-60% token reduction** compared to standard JSON on uniform data
- **Minimal syntax**: Eliminates redundant punctuation (braces, brackets, most quotes)
- **Tabular arrays**: CSV-like rows for uniform object collections, including nested uniform objects
- **Keyed tables**: Objects whose values share one shape collapse into a single table
- **Explicit metadata**: Array length indicators `[N]` for validation
- **Bidirectional**: `encode` and `decode`, with strict validation by default
- **No dependencies**: Pure Python, 3.8+

## Quick Start

```python
from toon import encode

# Simple object
data = {"name": "Alice", "age": 30}
print(encode(data))
# name: Alice
# age: 30

# Tabular array (uniform objects)
users = [
    {"id": 1, "name": "Alice", "age": 30},
    {"id": 2, "name": "Bob", "age": 25},
    {"id": 3, "name": "Charlie", "age": 35},
]
print(encode(users))
# [3]{id,name,age}:
#   1,Alice,30
#   2,Bob,25
#   3,Charlie,35

# Complex nested structure
data = {
    "metadata": {"version": 1, "author": "test"},
    "items": [
        {"id": 1, "name": "Item1"},
        {"id": 2, "name": "Item2"},
    ],
    "tags": ["alpha", "beta", "gamma"],
}
print(encode(data))
# metadata:
#   version: 1
#   author: test
# items[2]{id,name}:
#   1,Item1
#   2,Item2
# tags[3]: alpha,beta,gamma
```

## CLI Usage

Command-line tool for converting between JSON and TOON formats.

```bash
# Encode JSON to TOON (auto-detected by .json extension)
toon input.json -o output.toon

# Decode TOON to JSON (auto-detected by .toon extension)
toon data.toon -o output.json

# Use stdin/stdout
echo '{"name": "Ada"}' | toon -
# Output: name: Ada

# Force encode mode
toon data.json --encode

# Force decode mode
toon data.toon --decode

# Custom delimiter
toon data.json --delimiter tab -o output.toon

# Lenient decoding (disable strict validation)
toon data.toon --no-strict -o output.json
```

### CLI Options

| Option | Description |
|--------|-------------|
| `-o, --output <file>` | Output file path (prints to stdout if omitted) |
| `-e, --encode` | Force encode mode (overrides auto-detection) |
| `-d, --decode` | Force decode mode (overrides auto-detection) |
| `--delimiter <char>` | Array delimiter: `,`/`comma`, `\t`/`tab`, `\|`/`pipe` |
| `--indent <number>` | Indentation size (default: 2) |
| `--no-strict` | Disable strict validation when decoding |

## API Reference

### `encode(value, options=None)`

Converts a Python value to TOON format.

**Parameters:**
- `value` (Any): JSON-serializable value to encode (see [Type Conversions](#type-conversions))
- `options` (dict, optional): Encoding options

**Returns:** `str` - TOON-formatted string (LF line endings, no trailing newline)

**Example:**

```python
from toon import encode

data = {"id": 123, "name": "Ada"}
print(encode(data))
# id: 123
# name: Ada
```

### `decode(input_str, options=None)`

Converts a TOON-formatted string (or UTF-8 bytes) back to Python values.

**Parameters:**
- `input_str` (str | bytes): TOON-formatted input
- `options` (DecodeOptions, optional): Decoding options

**Returns:** Python value (dict, list, or primitive)

**Raises:** `ToonDecodeError` (a `ValueError` subclass) on invalid input

**Example:**

```python
from toon import decode

toon_str = """items[2]{sku,qty,price}:
  A1,2,9.99
  B2,1,14.5"""

data = decode(toon_str)
print(data)
# {'items': [{'sku': 'A1', 'qty': 2, 'price': 9.99}, {'sku': 'B2', 'qty': 1, 'price': 14.5}]}
```

### Encoding Options

```python
from toon import encode

encode(data, {
    "indent": 2,        # Spaces per indentation level (default: 2)
    "delimiter": ",",   # Document delimiter: "," | "\t" | "|" (default: ",")
})
```

The `lengthMarker` option from earlier versions is deprecated and ignored: TOON spec 4 removed the `#` length marker.

### Decoding Options

```python
from toon import decode, DecodeOptions

options = DecodeOptions(
    indent=2,    # Expected number of spaces per indentation level (default: 2)
    strict=True  # Enable strict validation (default: True)
)

data = decode(toon_str, options)
```

**Strict Mode:**

By default, the decoder validates input strictly (spec §14):
- **Counts and widths**: declared `[N]` must match the values, items, rows or entries; every row must have one cell per field
- **Syntax**: invalid escapes, unterminated strings, missing colons, malformed headers
- **Indentation**: must be a multiple of `indent`, no tabs, no unexpected depth jumps
- **Structure**: no blank lines inside arrays, no duplicate keys, no trailing content after a root array

Set `strict=False` for lenient parsing (duplicate keys resolve last-write-wins, count mismatches are accepted, malformed headers fall back to plain keys).

**Numbers:** integers decode to `int` (arbitrary precision). Tokens with a fraction or exponent decode to `float`, except integral values below 2^53, which decode to `int` (`2.5e2` → `250`). Tokens with leading zeros such as `05` decode as strings.

### Delimiter Options

```python
data = [1, 2, 3, 4, 5]

print(encode(data))                       # [5]: 1,2,3,4,5
print(encode(data, {"delimiter": "\t"}))  # [5<TAB>]: 1<TAB>2<TAB>3<TAB>4<TAB>5
print(encode(data, {"delimiter": "|"}))   # [5|]: 1|2|3|4|5
```

You can also use the string keys `"comma"`, `"tab"` and `"pipe"`.

## Format Rules

### Objects
Key-value pairs with primitives or nested structures:
```python
{"name": "Alice", "age": 30}
# name: Alice
# age: 30
```

### Primitive Arrays
Inline, with the length `[N]`:
```python
{"tags": ["alpha", "beta", "gamma"]}
# tags[3]: alpha,beta,gamma
```

### Empty Arrays and Objects
```python
{"tags": [], "config": {}}
# tags: []
# config:
```

### Tabular Arrays
Uniform objects with primitive values use a CSV-like form:
```python
{"items": [{"sku": "A1", "qty": 2}, {"sku": "B2", "qty": 1}]}
# items[2]{sku,qty}:
#   A1,2
#   B2,1
```

Uniform nested objects collapse into nested field groups, so rows stay flat:
```python
{"orders": [
    {"id": 1, "customer": {"name": "Ada", "country": "DK"}, "total": 99},
    {"id": 2, "customer": {"name": "Bob", "country": "UK"}, "total": 149},
]}
# orders[2]{id,customer{name,country},total}:
#   1,Ada,DK,99
#   2,Bob,UK,149
```

### Keyed Tables
An object with two or more entries whose values share one shape becomes a keyed table (note the `:` after the length):
```python
{"servers": {
    "alpha": {"host": "a.example.com", "port": 8080},
    "beta": {"host": "b.example.com", "port": 9090},
}}
# servers[2:]{host,port}:
#   alpha: a.example.com,8080
#   beta: b.example.com,9090
```

### Mixed Arrays
Non-uniform data uses list items with `-`. The first field of an object item sits on the hyphen line:
```python
{"items": [{"id": 1, "tags": ["a", "b"], "meta": {"x": 1}}, {"id": 2, "note": "n"}]}
# items[2]:
#   - id: 1
#     tags[2]: a,b
#     meta:
#       x: 1
#   - id: 2
#     note: n
```

### Delimiters in Headers

The comma is the default and is never written in the header. Tab and pipe are declared inside the brackets and used for the field list and rows:

```
items[2|]{sku|qty}:
  A1|2
  B2|1
```

### Comments

The decoder ignores full-line comments, meaning lines whose first non-space character is `#`. The encoder never writes comments, and it always quotes strings that start with `#`.

### Quoting Rules

Strings are quoted only when necessary:

- Empty strings
- Keywords: `null`, `true`, `false`
- Numeric-like strings: `42`, `-3.14`, `05`, `1e6`
- Leading or trailing whitespace
- Contains `:`, `"`, `\`, `[`, `]`, `{`, `}` or control characters
- Contains the active delimiter (`,`, `|`, or tab)
- Starts with `-` or `#`

```python
"hello"          # hello (no quotes)
"hello world"    # hello world (internal spaces OK)
" hello"         # " hello" (leading space requires quotes)
"null"           # "null" (keyword)
"42"             # "42" (looks like number)
"#tag"           # "#tag" (would read as a comment)
""               # "" (empty)
```

## Type Conversions

Non-JSON types are normalized automatically:
- **Numbers**: Plain decimal form for 1e-6 ≤ |n| < 1e21, exponent form (`1e-7`, `1e+21`) outside that range
- **Infinity/NaN**: Converted to `null`
- **-0**: Normalized to `0`
- **Decimal**: Converted to `int` if integral, otherwise `float`
- **datetime / date / time**: ISO 8601 strings via `.isoformat()`
- **set / frozenset / tuple**: Converted to arrays
- **Mappings**: Converted to objects, with keys coerced to strings
- **Dataclasses**: Converted to objects via `dataclasses.asdict()`
- **Functions/Callables**: Converted to `null`

Strings with unpaired surrogates raise `ValueError`.

## LLM Integration Best Practices

When using TOON with LLMs:

1. **Wrap in code blocks** for clarity:
   ````markdown
   ```toon
   name: Alice
   age: 30
   ```
   ````

2. **Instruct the model** about the format:
   > "Respond using TOON format (Token-Oriented Object Notation). Use `key: value` syntax, indentation for nesting, and tabular format `[N]{fields}:` for uniform arrays."

3. **Use array lengths for validation**: tell the model "Array lengths are declared as `[N]`. Ensure your response matches these counts." Then decode the response in strict mode.

4. **Acknowledge tokenizer variance**: Token savings depend on the tokenizer, the model and above all the shape of your data. Deeply nested, non-uniform documents can use as many tokens as compact JSON, or more.

## Token Efficiency Example

```python
import json
from toon import encode

data = {
    "users": [
        {"id": 1, "name": "Alice", "age": 30, "active": True},
        {"id": 2, "name": "Bob", "age": 25, "active": True},
        {"id": 3, "name": "Charlie", "age": 35, "active": False},
    ]
}

json_str = json.dumps(data)
toon_str = encode(data)

print(f"JSON: {len(json_str)} characters")
print(f"TOON: {len(toon_str)} characters")
print(f"Reduction: {100 * (1 - len(toon_str) / len(json_str)):.1f}%")

# JSON: 177 characters
# TOON: 84 characters
# Reduction: 52.5%
```

**JSON output:**
```json
{"users": [{"id": 1, "name": "Alice", "age": 30, "active": true}, {"id": 2, "name": "Bob", "age": 25, "active": true}, {"id": 3, "name": "Charlie", "age": 35, "active": false}]}
```

**TOON output:**
```
users[3]{id,name,age,active}:
  1,Alice,30,true
  2,Bob,25,true
  3,Charlie,35,false
```

## Development

This project uses [uv](https://docs.astral.sh/uv/) for fast, reliable package and environment management.

### Setup with uv (Recommended)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/xaviviro/python-toon.git
cd python-toon

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install package in editable mode with dev dependencies
uv pip install -e ".[dev]"
```

### Setup with pip (Alternative)

```bash
# Clone the repository
git clone https://github.com/xaviviro/python-toon.git
cd python-toon

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .

# Install development dependencies
pip install -r requirements-dev.txt
```

### Running Tests

```bash
# Run all tests (includes the official spec fixtures in tests/fixtures/)
pytest

# Run only the spec conformance suite
pytest tests/test_spec_fixtures.py

# Run with coverage
pytest --cov=toon --cov-report=term
```

### Type Checking

```bash
mypy src/toon
```

### Linting

```bash
ruff check src/toon tests
```

## Credits

This project is an unofficial Python implementation of the TOON format. The conformance fixtures in `tests/fixtures/` come from the [TOON specification](https://github.com/toon-format/spec) (MIT License).

## License

MIT License - see [LICENSE](LICENSE) file for details

## Related

- [TOON Format Specification](https://github.com/toon-format/spec) - Official specification with normative encoding rules
- [TOON Format Organization](https://github.com/toon-format) - Official TOON format organization
- [toon-format/toon-python](https://github.com/toon-format/toon-python) - Official Python implementation

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

When contributing, please:
- Add tests for new features
- Update documentation as needed
- Ensure compatibility with the TOON specification

## Support

For bugs and feature requests, please [open an issue](https://github.com/xaviviro/python-toon/issues).
