"""Convert the DGBAS NStatDB CPI export into monthly headline CPI levels.

This is an offline-data preparation command, never imported by the API runtime.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/market/raw/cpi_nstatdb.csv'
OUTPUT = ROOT / 'data/market/tw_cpi_monthly.csv'
MONTH_PERIOD = re.compile(r'(\d{2,3})年(\d{1,2})月')
YEAR_PERIOD = re.compile(r'\d{2,3}年')


def parse_cpi(raw_path: Path) -> list[tuple[str, str]]:
    with raw_path.open(newline='', encoding='utf-8-sig') as handle:
        lines = list(csv.reader(handle))
    header_index = next((index for index, row in enumerate(lines) if row[:2] == ['統計期', '總指數']), None)
    if header_index is None:
        raise ValueError('CPI export has no 統計期/總指數 header row')
    if not any('民國110年=100' in cell for row in lines[:header_index] for cell in row):
        raise ValueError('CPI export base period is not 民國110年=100')
    rows = []
    for row in lines[header_index + 1:]:
        period = row[0].strip() if row else ''
        if not period:
            # The data block ends at the first blank line; notes follow it.
            break
        if YEAR_PERIOD.fullmatch(period):
            continue
        match = MONTH_PERIOD.fullmatch(period)
        if not match:
            raise ValueError(f'Unexpected CPI period: {period}')
        year, month = int(match.group(1)) + 1911, int(match.group(2))
        if not 1 <= month <= 12:
            raise ValueError(f'Invalid CPI month: {period}')
        try:
            value = Decimal(row[1].strip())
        except (IndexError, InvalidOperation) as exc:
            raise ValueError(f'Invalid CPI value for {period}') from exc
        if not value.is_finite() or value <= 0:
            raise ValueError(f'Non-positive CPI value for {period}')
        rows.append((f'{year:04d}-{month:02d}', str(value)))
    if not rows:
        raise ValueError('CPI export contains no monthly rows')
    if len({period for period, _ in rows}) != len(rows) or [p for p, _ in rows] != sorted(p for p, _ in rows):
        raise ValueError('CPI monthly rows must be unique and in ascending order')
    return rows


def build(raw_path: Path = RAW, output: Path = OUTPUT) -> None:
    rows = parse_cpi(raw_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.csv.tmp')
    with temporary.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['period', 'cpi'])
        writer.writerows(rows)
    temporary.replace(output)
    print(f'Wrote {len(rows)} monthly CPI levels: {rows[0][0]} to {rows[-1][0]}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, default=RAW)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    build(args.raw, args.output)
