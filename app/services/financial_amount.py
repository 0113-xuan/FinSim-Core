from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


ARABIC_AMOUNT_PATTERN = r"\d[\d,]*(?:\.\d+)?(?:\s*萬\s*[零一二兩三四五六七八九\d]?(?:千)?)?|\d[\d,]*(?:\.\d+)?\s*(?:千|[kK])?"
CHINESE_AMOUNT_PATTERN = r"[零一二兩三四五六七八九十百千萬]+"
FINANCIAL_AMOUNT_PATTERN = rf"(?:{ARABIC_AMOUNT_PATTERN}|{CHINESE_AMOUNT_PATTERN})"

_DIGITS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "兩": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_SMALL_UNITS = {"十": 10, "百": 100, "千": 1000}


@dataclass(frozen=True)
class ParsedFinancialAmount:
    value: Decimal
    original_text: str


def _parse_under_ten_thousand(text: str) -> int:
    if not text:
        return 0
    if all(character in _DIGITS for character in text):
        if len(text) != 1:
            raise ValueError("ambiguous Chinese amount")
        return _DIGITS[text]
    total = 0
    pending: int | None = None
    previous_unit = 10_000
    for character in text:
        if character in _DIGITS:
            if pending is not None:
                raise ValueError("malformed Chinese amount")
            pending = _DIGITS[character]
            continue
        unit = _SMALL_UNITS.get(character)
        if unit is None or unit >= previous_unit:
            raise ValueError("malformed Chinese amount")
        total += (pending if pending is not None else 1) * unit
        pending = None
        previous_unit = unit
    return total + (pending or 0)


def _parse_chinese(text: str) -> Decimal:
    if text.count("萬") > 1:
        raise ValueError("malformed Chinese amount")
    if "萬" not in text:
        return Decimal(_parse_under_ten_thousand(text))
    high, low = text.split("萬", 1)
    high_value = _parse_under_ten_thousand(high) if high else 1
    if not low:
        low_value = 0
    elif len(low) == 1 and low in _DIGITS:
        low_value = _DIGITS[low] * 1000
    else:
        low_value = _parse_under_ten_thousand(low)
    return Decimal(high_value * 10_000 + low_value)


def parse_financial_amount(text: str) -> ParsedFinancialAmount:
    original = text.strip()
    compact = re.sub(r"\s+", "", original).removesuffix("元").removesuffix("塊")
    if not compact:
        raise ValueError("empty financial amount")

    arabic = re.fullmatch(r"([\d,]+(?:\.\d+)?)(萬|千|[kK])?([零一二兩三四五六七八九\d]?)(千)?", compact)
    if arabic:
        try:
            value = Decimal(arabic.group(1).replace(",", ""))
        except InvalidOperation as exc:
            raise ValueError("invalid financial amount") from exc
        unit = arabic.group(2)
        shorthand = arabic.group(3)
        if unit == "萬":
            value *= Decimal(10_000)
            if shorthand:
                digit = int(shorthand) if shorthand.isdigit() else _DIGITS[shorthand]
                value += Decimal(digit * 1000)
        elif shorthand:
            raise ValueError("ambiguous financial amount")
        elif unit in {"千", "k", "K"}:
            value *= Decimal(1000)
    elif re.fullmatch(CHINESE_AMOUNT_PATTERN, compact):
        value = _parse_chinese(compact)
    else:
        raise ValueError("unsupported financial amount")
    if value < 0:
        raise ValueError("financial amount cannot be negative")
    return ParsedFinancialAmount(
        value=value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        original_text=original,
    )


def find_financial_amounts(text: str) -> list[tuple[int, int, ParsedFinancialAmount]]:
    results = []
    for match in re.finditer(FINANCIAL_AMOUNT_PATTERN, text):
        try:
            parsed = parse_financial_amount(match.group(0))
        except ValueError:
            continue
        results.append((match.start(), match.end(), parsed))
    return results
