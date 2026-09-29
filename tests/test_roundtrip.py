"""Round-trip and normalization tests: decode(encode(x)) == x."""

import dataclasses
import random
from datetime import date, datetime
from decimal import Decimal

import pytest

from toon import DecodeOptions, decode, encode

ISSUE_4_PAYLOAD = {
    "operations": [
        {
            "additionalData": {"asd": "1234", "country": "380", "status": "000"},
            "cancelledOperationId": "",
            "channel": "BACKOFFICE",
            "customerInfo": {
                "billingAddress": {"city": "Milano", "country": "ITA", "postCode": "20151"},
                "email": "test@email.it",
            },
            "operationTime": "2025-11-11 19:07:34.295",
            "warnings": [
                {"code": "005", "description": "Warning - BillingAddress: not valid"},
                {"code": "012", "description": "Warning - ShippingAddress: not valid"},
            ],
        }
    ],
    "orderStatus": {
        "order": {
            "amount": "44900",
            "termsAndConditionsIds": [],
            "transactionSummary": [],
        }
    },
}


def test_issue_4_object_list_item_with_nested_first_field():
    """Regression for issue #4: the first field of a list-item object is on the hyphen line."""
    text = encode(ISSUE_4_PAYLOAD)
    assert "  - additionalData:\n" in text
    assert "termsAndConditionsIds: []" in text
    assert decode(text) == ISSUE_4_PAYLOAD


def _random_string(rng):
    alphabet = [
        "a",
        "Z",
        "_",
        " ",
        ",",
        "|",
        "\t",
        ":",
        "-",
        "#",
        '"',
        "\\",
        "\n",
        "[",
        "é",
        "😀",
        "1",
    ]
    return "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 6)))


def _random_value(rng, depth=0):
    kind = rng.randint(0, 9 if depth < 4 else 4)
    if kind == 0:
        return None
    if kind == 1:
        return rng.choice([True, False])
    if kind == 2:
        return rng.choice([0, -1, 7, 10**25, 1.5, -0.25, 1e-7, 3.5e22, 0.1])
    if kind in (3, 4):
        return rng.choice([_random_string(rng), "true", "42", "-x", "#tag", "05", ""])
    if kind in (5, 6):
        return {
            _random_string(rng): _random_value(rng, depth + 1) for _ in range(rng.randint(0, 4))
        }
    if kind == 7:
        # Uniform objects, eligible for tabular / keyed tabular forms
        keys = [_random_string(rng) or "k" for _ in range(rng.randint(1, 3))]
        return [{k: _random_value(rng, 4) for k in keys} for _ in range(rng.randint(1, 3))]
    return [_random_value(rng, depth + 1) for _ in range(rng.randint(0, 4))]


@pytest.mark.parametrize("delimiter", [",", "\t", "|"])
@pytest.mark.parametrize("indent", [2, 4])
def test_random_round_trip(delimiter, indent):
    rng = random.Random(f"{delimiter}{indent}")
    for _ in range(400):
        value = _random_value(rng)
        text = encode(value, {"delimiter": delimiter, "indent": indent})
        assert not text.endswith("\n")
        assert all(line == line.rstrip(" ") for line in text.split("\n"))
        assert decode(text, DecodeOptions(indent=indent)) == value, text


def test_normalization_of_host_types():
    @dataclasses.dataclass
    class Point:
        x: int
        y: float

    value = {
        "when": datetime(2025, 1, 2, 3, 4, 5),
        "day": date(2025, 1, 2),
        "price": Decimal("9.50"),
        "count": Decimal("3"),
        "tags": frozenset(["a"]),
        "point": Point(1, 2.5),
        "nan": float("nan"),
        "neg_zero": -0.0,
    }
    assert decode(encode(value)) == {
        "when": "2025-01-02T03:04:05",
        "day": "2025-01-02",
        "price": 9.5,
        "count": 3,
        "tags": ["a"],
        "point": {"x": 1, "y": 2.5},
        "nan": None,
        "neg_zero": 0,
    }


def test_unpaired_surrogate_is_rejected():
    with pytest.raises(ValueError):
        encode({"bad": "\ud800"})


def test_decode_accepts_bytes_and_bom():
    assert decode("﻿a: 1\r\nb: 2\r\n".encode()) == {"a": 1, "b": 2}
