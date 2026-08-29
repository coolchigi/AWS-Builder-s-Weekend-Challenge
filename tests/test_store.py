from decimal import Decimal

from roost import store


def test_floats_become_decimal_for_dynamodb():
    out = store._to_ddb({"price": 1299.5, "n": 3, "s": "x", "nested": {"p": 42.0}})
    assert out["price"] == Decimal("1299.5")
    assert isinstance(out["price"], Decimal)
    assert isinstance(out["nested"]["p"], Decimal)
    assert out["n"] == 3 and out["s"] == "x"  # ints/strs untouched


def test_lists_are_converted_recursively():
    out = store._to_ddb({"xs": [1.5, 2.0]})
    assert out["xs"] == [Decimal("1.5"), Decimal("2.0")]
