"""Validate bounded values and preserve exact arithmetic until result output."""

import math
import re
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext
from fractions import Fraction

MAX_INTEGER = 9_007_199_254_740_991
MAX_ITEMS = 1000
DECIMAL_PATTERN = r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$"


def numeric(value):
    if isinstance(value, Fraction):
        return value
    if type(value) is int:
        return Fraction(value)
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("A decimal must be finite.")
        value = str(value)
    if not isinstance(value, str) or len(value) > 128 or not re.fullmatch(DECIMAL_PATTERN, value):
        raise ValueError("Invalid decimal value.")
    try:
        number = Decimal(value)
        if not number.is_finite() or abs(number.adjusted()) > 100:
            raise ValueError("Decimal exponent is outside the supported range.")
        result = Fraction(number)
    except (InvalidOperation, OverflowError) as error:
        raise ValueError("Invalid decimal value.") from error
    if abs(result) > MAX_INTEGER:
        raise ValueError("Decimal magnitude is outside the supported range.")
    return result


def decimal_text(value):
    value = numeric(value)
    with localcontext() as context:
        context.prec = 28
        context.rounding = ROUND_HALF_EVEN
        result = format(Decimal(value.numerator) / Decimal(value.denominator), "f")
    if "." in result:
        result = result.rstrip("0").rstrip(".")
    return "0" if result == "-0" else result


def valid_value(value, kind, nullable=False, item_type=None, *, internal=False):
    if value is None:
        return nullable
    if kind == "array":
        return (
            type(value) is list
            and len(value) <= MAX_ITEMS
            and item_type in {"string", "integer", "boolean", "decimal"}
            and all(valid_value(v, item_type, internal=internal) for v in value)
        )
    if kind == "decimal":
        try:
            if isinstance(value, Fraction) and not internal:
                return False
            return abs(numeric(value)) <= MAX_INTEGER
        except (ValueError, TypeError):
            return False
    expected = {"string": str, "integer": int, "boolean": bool}.get(kind)
    return type(value) is expected and (kind != "integer" or abs(value) <= MAX_INTEGER)


def normalize(value, spec):
    kind, item_type = spec.type, getattr(spec, "item_type", None)
    if not valid_value(value, kind, getattr(spec, "nullable", False), item_type, internal=True):
        raise ValueError("The value does not match its declared type or limit.")
    if value is None:
        return None
    if kind == "decimal":
        return numeric(value)
    if kind == "array" and item_type == "decimal":
        return [numeric(v) for v in value]
    return value


def json_value(value):
    if isinstance(value, Fraction):
        return decimal_text(value)
    if isinstance(value, dict):
        return {k: json_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(v) for v in value]
    return value


def source_value(value, spec):
    """Keep every supplied decimal digit. Round only calculated result output."""
    normalize(value, spec)
    if value is None:
        return None
    if spec.type == "decimal":
        return format(Decimal(str(value)), "f")
    if spec.type == "array" and spec.item_type == "decimal":
        return [format(Decimal(str(v)), "f") for v in value]
    return value


def value_schema(spec):
    kind = spec.type
    schema = (
        {"type": "string", "pattern": DECIMAL_PATTERN, "maxLength": 128}
        if kind == "decimal"
        else {"type": kind}
    )
    if kind == "array":
        schema.update(
            items={"type": "string", "pattern": DECIMAL_PATTERN, "maxLength": 128}
            if spec.item_type == "decimal"
            else {"type": spec.item_type},
            maxItems=MAX_ITEMS,
        )
    if getattr(spec, "nullable", False):
        schema["type"] = [schema["type"], "null"]
    return schema
