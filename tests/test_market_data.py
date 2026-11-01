import csv
import importlib.util
import json
from pathlib import Path
import random

import pytest

from app.core.market_data import MARKET_DIR, block_bootstrap_indices, load_market_history, read_monthly_series


ROOT = Path(__file__).resolve().parents[1]


def _month_index(period):
    year, month = map(int, period.split('-'))
    return year * 12 + month - 1


@pytest.mark.parametrize('name,column', [('tw_cpi_monthly.csv', 'cpi'), ('twse_total_return_monthly.csv', 'close')])
def test_market_csv_is_continuous_and_positive(name, column):
    with (MARKET_DIR / name).open(newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    indices = [_month_index(row['period']) for row in rows]
    assert indices == list(range(indices[0], indices[0] + len(rows)))
    assert all(float(row[column]) > 0 for row in rows)


def test_common_history_covers_at_least_twenty_years():
    history = load_market_history()
    assert len(history.periods) >= 20 * 12
    assert len(history.inflation) == len(history.returns) == len(history.periods)
    assert {source['publisher'] for source in history.data_sources} == {'行政院主計總處', '臺灣證券交易所'}


def test_pairs_and_annual_rates_come_from_the_same_months():
    history = load_market_history()
    cpi = read_monthly_series(MARKET_DIR / 'tw_cpi_monthly.csv', 'cpi')
    closes = read_monthly_series(MARKET_DIR / 'twse_total_return_monthly.csv', 'close')
    month = history.periods[100]
    prior = history.periods[99]
    assert history.inflation[100] == pytest.approx(cpi[month] / cpi[prior] - 1)
    assert history.returns[100] == pytest.approx(closes[month] / closes[prior] - 1)
    growth = 1.0
    for rate in history.inflation:
        growth *= 1 + rate
    assert history.annual_inflation_rate == pytest.approx(growth ** (12 / len(history.inflation)) - 1)


def test_non_continuous_series_is_rejected(tmp_path):
    path = tmp_path / 'gap.csv'
    path.write_text('period,cpi\n2020-01,100\n2020-03,101\n', encoding='utf-8')
    with pytest.raises(ValueError, match='continuous'):
        read_monthly_series(path, 'cpi')


def test_block_bootstrap_uses_consecutive_twelve_month_runs_without_wrapping():
    rng = random.Random(7)
    indices = block_bootstrap_indices(rng, 30, 20)
    assert len(indices) == 30
    for start in range(0, 30, 12):
        block = indices[start:start + 12]
        assert block == list(range(block[0], block[0] + len(block)))
        assert block[0] <= 20 - 12
    assert block_bootstrap_indices(random.Random(7), 30, 20) == indices


def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cpi_build_reads_only_monthly_headline_rows(tmp_path):
    # Synthetic levels exercise the export format; these are not historical observations.
    raw = tmp_path / 'cpi.csv'
    raw.write_text('﻿,"消費者物價基本分類指數",\n,,"指數基期：民國110年=100"\n'
                   '"統計期","總指數","一.食物類"\n"92年",100,50\n"92年1月",101,51\n'
                   '"92年2月",99,49\n\n\n"註解："\n"最近3個月資料均可能修正。"\n', encoding='utf-8')
    assert _load_script('build_cpi').parse_cpi(raw) == [('2003-01', '101'), ('2003-02', '99')]


def test_cpi_csv_matches_raw_export():
    rows = _load_script('build_cpi').parse_cpi(MARKET_DIR / 'raw' / 'cpi_nstatdb.csv')
    built = read_monthly_series(MARKET_DIR / 'tw_cpi_monthly.csv', 'cpi')
    assert [(period, float(value)) for period, value in rows] == list(built.items())


def test_total_return_csv_matches_cached_last_trading_day():
    module = _load_script('fetch_twse_total_return')
    built = read_monthly_series(MARKET_DIR / 'twse_total_return_monthly.csv', 'close')
    for period in built:
        payload = json.loads((MARKET_DIR / 'raw' / 'twse_total_return' / f'{period}.json').read_text(encoding='utf-8-sig'))
        assert float(module.month_close(payload, period)) == built[period]
