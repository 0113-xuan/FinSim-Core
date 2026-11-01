"""Taiwan monthly CPI and TWSE total-return history read from bundled CSV files.

Runtime code only reads ``data/market``; the files are prepared offline by
``scripts/build_cpi.py`` and ``scripts/fetch_twse_total_return.py``.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
import math
from pathlib import Path
import random
from typing import Dict, List, Tuple


MARKET_DIR = Path(__file__).resolve().parents[2] / 'data' / 'market'
CPI_FILE = 'tw_cpi_monthly.csv'
TOTAL_RETURN_FILE = 'twse_total_return_monthly.csv'
BLOCK_MONTHS = 12

SOURCES = (
    {
        'key': 'cpi',
        'name': '消費者物價指數（總指數，民國110年=100）',
        'publisher': '行政院主計總處',
        'url': 'https://nstatdb.dgbas.gov.tw/dgbasall/webMain.aspx?k=dgmain',
        'downloaded': '2026-10-31',
        'file': CPI_FILE,
        'column': 'cpi',
    },
    {
        'key': 'total_return',
        'name': '發行量加權股價報酬指數（含股利再投入，月底收盤）',
        'publisher': '臺灣證券交易所',
        'url': 'https://www.twse.com.tw/rwd/zh/TAIEX/MFI94U',
        'downloaded': '2026-11-01',
        'file': TOTAL_RETURN_FILE,
        'column': 'close',
    },
)


@dataclass(frozen=True)
class MarketHistory:
    periods: Tuple[str, ...]
    inflation: Tuple[float, ...]
    returns: Tuple[float, ...]
    annual_inflation_rate: float
    annual_return_rate: float
    data_sources: Tuple[Dict[str, str], ...]

    @property
    def start_period(self) -> str:
        return self.periods[0]

    @property
    def end_period(self) -> str:
        return self.periods[-1]


def _month_index(period: str) -> int:
    year, month = map(int, period.split('-'))
    if not 1 <= month <= 12:
        raise ValueError(f'invalid month {period}')
    return year * 12 + month - 1


def read_monthly_series(path: Path, column: str) -> Dict[str, float]:
    with path.open(newline='', encoding='utf-8-sig') as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f'{path.name} has no rows')
    series: Dict[str, float] = {}
    previous = None
    for row in rows:
        period = row['period']
        value = float(row[column])
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f'{path.name} {period} must be positive')
        index = _month_index(period)
        if previous is not None and index != previous + 1:
            raise ValueError(f'{path.name} is not a continuous monthly series at {period}')
        previous = index
        series[period] = value
    return series


def _annualized(levels: List[float]) -> float:
    return (levels[-1] / levels[0]) ** (12 / (len(levels) - 1)) - 1


@lru_cache(maxsize=None)
def load_market_history(directory: Path = MARKET_DIR) -> MarketHistory:
    cpi = read_monthly_series(directory / CPI_FILE, 'cpi')
    closes = read_monthly_series(directory / TOTAL_RETURN_FILE, 'close')
    common = sorted(cpi.keys() & closes.keys(), key=_month_index)
    if len(common) < BLOCK_MONTHS + 1:
        raise ValueError('CPI and total-return history overlap too little for block sampling')
    # Both inputs are continuous, so their overlap is one continuous range.
    pairs = list(zip(common, common[1:]))
    sources = []
    for source in SOURCES:
        series = cpi if source['key'] == 'cpi' else closes
        sources.append({key: source[key] for key in ('name', 'publisher', 'url', 'downloaded')}
                       | {'period_start': min(series, key=_month_index), 'period_end': max(series, key=_month_index)})
    return MarketHistory(
        periods=tuple(month for _, month in pairs),
        inflation=tuple(cpi[month] / cpi[prior] - 1 for prior, month in pairs),
        returns=tuple(closes[month] / closes[prior] - 1 for prior, month in pairs),
        annual_inflation_rate=_annualized([cpi[month] for month in common]),
        annual_return_rate=_annualized([closes[month] for month in common]),
        data_sources=tuple(sources),
    )


def block_bootstrap_indices(rng: random.Random, months: int, count: int, block: int = BLOCK_MONTHS) -> List[int]:
    """Concatenate consecutive ``block``-month runs; starts are 0..count-block, never wrapping."""
    if count < block:
        raise ValueError('history is shorter than one block')
    indices: List[int] = []
    while len(indices) < months:
        start = rng.randint(0, count - block)
        indices.extend(range(start, start + block))
    return indices[:months]
