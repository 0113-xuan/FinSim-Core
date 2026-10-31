"""Download official TWSE total-return levels, retaining raw responses for audit.

This is an offline-data preparation command, never imported by the API runtime.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import time
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = 'https://www.twse.com.tw/rwd/zh/TAIEX/MFI94U'


def last_complete_period(today: date | None = None) -> str:
    today = today or datetime.now(ZoneInfo('Asia/Taipei')).date()
    index = today.year * 12 + today.month - 2
    return f'{index // 12:04d}-{index % 12 + 1:02d}'


def periods(start: str, end: str):
    start_year, start_month = map(int, start.split('-'))
    end_year, end_month = map(int, end.split('-'))
    for index in range(start_year * 12 + start_month - 1, end_year * 12 + end_month):
        yield f'{index // 12:04d}-{index % 12 + 1:02d}'


def month_close(payload: dict, period: str) -> str:
    if payload.get('stat') != 'OK' or not payload.get('data'):
        raise ValueError(f'TWSE returned no valid data for {period}: {payload.get("stat")}')
    rows = []
    for row in payload['data']:
        match = re.fullmatch(r'(\d{2,3})/(\d{2})/(\d{2})', str(row[0]).strip())
        if not match:
            raise ValueError(f'Unexpected ROC date format for {period}')
        year, month, day = map(int, match.groups())
        trading_date = date(year + 1911, month, day)
        if trading_date.strftime('%Y-%m') != period:
            raise ValueError(f'TWSE response month mismatch: {period}')
        try:
            value = Decimal(str(row[1]).replace(',', '').strip())
        except InvalidOperation as exc:
            raise ValueError(f'Invalid TWSE close for {period}') from exc
        if not value.is_finite() or value <= 0:
            raise ValueError(f'Non-positive TWSE close for {period}')
        rows.append((trading_date, value))
    if len({day for day, _ in rows}) != len(rows):
        raise ValueError(f'Duplicate trading dates for {period}')
    return str(max(rows, key=lambda row: row[0])[1])


def last_cached_period(raw_dir: Path) -> str:
    cached = sorted(path.stem for path in raw_dir.glob('*.json'))
    if not cached:
        raise ValueError(f'No cached TWSE responses in {raw_dir}')
    return cached[-1]


def fetch(end: str | None = None, *, output: Path | None = None, delay: float = 3, offline: bool = False) -> None:
    if delay < 3:
        raise ValueError('Requests must be at least 3 seconds apart')
    output = output or ROOT / 'data/market/twse_total_return_monthly.csv'
    raw_dir = output.parent / 'raw/twse_total_return'
    end = end or (last_cached_period(raw_dir) if offline else last_complete_period())
    if end > last_complete_period():
        raise ValueError('Only complete months may be downloaded')
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    last_response = None
    session = None
    try:
        for index, period in enumerate(periods('2003-01', end), 1):
            raw_path = raw_dir / f'{period}.json'
            if raw_path.exists():
                payload = json.loads(raw_path.read_text(encoding='utf-8-sig'))
            elif offline:
                raise ValueError(f'Missing cached TWSE response for {period}; rerun without --offline')
            else:
                if session is None:
                    import requests
                    session = requests.Session()
                if last_response is not None:
                    time.sleep(max(0, delay - (time.monotonic() - last_response)))
                response = session.get(ENDPOINT, params={'date': period.replace('-', '') + '01', 'response':'json'}, timeout=45)
                last_response = time.monotonic()
                response.raise_for_status()
                payload = response.json()
                # Validate before caching; a rejected or empty response is never treated as data.
                month_close(payload, period)
                raw_path.write_text(response.text, encoding='utf-8')
            rows.append((period, month_close(payload, period)))
            if index % 12 == 0:
                print(f'Validated {index} months through {period}', flush=True)
    finally:
        if session is not None:
            session.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.csv.tmp')
    with temporary.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['period', 'close'])
        writer.writerows(rows)
    temporary.replace(output)
    print(f'Wrote {len(rows)} monthly closes: {rows[0][0]} to {rows[-1][0]}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--end', help='Last complete YYYY-MM (default: previous Taipei month, or last cached month with --offline)')
    parser.add_argument('--offline', action='store_true', help='Rebuild the CSV from cached raw JSON only; never connect')
    args = parser.parse_args()
    fetch(args.end, offline=args.offline)
