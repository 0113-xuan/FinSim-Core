from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True, order=True)
class YearMonth:
    year: int
    month: int

    def __post_init__(self) -> None:
        if not 1 <= self.month <= 12:
            raise ValueError("month must be between 1 and 12")

    @classmethod
    def parse(cls, value: str) -> "YearMonth":
        match = re.fullmatch(r"(\d{4})-(\d{2})", value)
        if not match:
            raise ValueError("period must use YYYY-MM")
        return cls(int(match.group(1)), int(match.group(2)))

    def add_months(self, count: int) -> "YearMonth":
        absolute = self.year * 12 + self.month - 1 + count
        return YearMonth(absolute // 12, absolute % 12 + 1)

    def months_until(self, other: "YearMonth") -> int:
        return (other.year - self.year) * 12 + other.month - self.month

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


def resolve_reference_date(reference_date: date | None, timezone_name: str) -> date:
    if reference_date is not None:
        return reference_date
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("不支援的使用者時區") from exc
    return datetime.now(timezone).date()


def normalize_date_text(text: str, reference_date: date) -> str | None:
    normalized = re.sub(r"\s+", "", text)
    base = YearMonth(reference_date.year, reference_date.month)
    if normalized in {"下個月", "下月"}:
        return str(base.add_months(1))
    if normalized in {"下下個月", "兩個月後", "2個月後"}:
        return str(base.add_months(2))
    if normalized in {"今年年底", "今年年末", "年底", "年末"}:
        return str(YearMonth(reference_date.year, 12))
    if normalized in {"明年", "明年年初"}:
        return str(YearMonth(reference_date.year + 1, 1))

    next_year_month = re.fullmatch(r"明年(\d{1,2})月", normalized)
    if next_year_month:
        month = int(next_year_month.group(1))
        return str(YearMonth(reference_date.year + 1, month)) if 1 <= month <= 12 else None

    explicit = re.fullmatch(r"(\d{4})年(\d{1,2})月", normalized)
    if explicit:
        year, month = int(explicit.group(1)), int(explicit.group(2))
        return str(YearMonth(year, month)) if 1 <= month <= 12 else None

    current_year = re.fullmatch(r"今年(\d{1,2})月", normalized)
    if current_year:
        month = int(current_year.group(1))
        return str(YearMonth(reference_date.year, month)) if 1 <= month <= 12 else None

    years = re.fullmatch(r"([一二三四五六七八九十]|\d+)年後", normalized)
    if years:
        chinese = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
                   "七": 7, "八": 8, "九": 9, "十": 10}
        count = chinese.get(years.group(1), int(years.group(1)) if years.group(1).isdigit() else 0)
        return str(base.add_months(count * 12))
    return None


def extract_date_text(text: str) -> str | None:
    patterns = [
        r"\d{4}年\d{1,2}月",
        r"今年\d{1,2}月",
        r"今年年底|今年年末|年底|年末",
        r"下下個月|兩個月後|2個月後",
        r"下個月|下月",
        r"明年\d{1,2}月",
        r"明年年初|明年",
        r"(?:[一二三四五六七八九十]|\d+)年後",
    ]
    match = re.search("|".join(f"(?:{item})" for item in patterns), text)
    return match.group(0) if match else None


def simulation_month_for_period(period: str, reference_date: date) -> int:
    base = YearMonth(reference_date.year, reference_date.month)
    difference = base.months_until(YearMonth.parse(period))
    return max(1, difference)


def period_for_simulation_month(month_index: int, reference_date: date) -> str:
    if month_index < 1:
        raise ValueError("simulation month must be positive")
    return str(YearMonth(reference_date.year, reference_date.month).add_months(month_index))
