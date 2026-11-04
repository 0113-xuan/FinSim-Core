import json
import re
from pathlib import Path

import pytest

from app.decision_assumptions import ASSUMPTIONS, VEHICLE_DEPRECIATION
from app.core.market_data import BLOCK_MONTHS
from app.services.knowledge_base import (
    RELEVANCE_THRESHOLD, is_relevant, load_knowledge, normalize, retrieve,
)
from app.services.plan_explanation import MONTE_CARLO_SEED, MONTE_CARLO_SIMULATIONS, SIMULATE_SEED
from app.vehicle_fees import annual_vehicle_tax

GOLDEN = json.loads((Path(__file__).parent / 'fixtures/rag_golden.json').read_text(encoding='utf-8'))


def texts():
    return {item['id']: item['text'] for item in load_knowledge()}


def test_knowledge_has_complete_unique_bounded_sections():
    entries = load_knowledge()
    assert len(entries) >= 25
    assert len({entry['id'] for entry in entries}) == len(entries)
    assert len({entry['file'] for entry in entries}) == 6
    assert all(entry['source'] and entry['tags'] and entry['title'] and 80 <= len(entry['text']) <= 400 for entry in entries)
    assert load_knowledge() is entries
    root = Path(__file__).resolve().parents[1]
    for entry in entries:
        for source in re.findall(r'(?:app|static|data|scripts)/[\w/.-]+', entry['source']):
            assert (root / source).is_file(), (entry['id'], source)


@pytest.mark.parametrize('replacement', [
    'id: duplicate\nsource: code\ntags: test\n\nbody\n\n## Duplicate\nid: duplicate\nsource: code\ntags: test\n\nbody',
    'id: missing-source\ntags: test\n\nbody',
    'id: long\nsource: code\ntags: test\n\n' + '文' * 601,
    'id: no-body\nsource: code\ntags: test',
])
def test_malformed_knowledge_fails_explicit_check(tmp_path, replacement):
    (tmp_path / 'broken.md').write_text('## Section\n' + replacement, encoding='utf-8')
    with pytest.raises(ValueError):
        load_knowledge(tmp_path)


def test_count_matches_plan_and_explanation():
    assert f'{MONTE_CARLO_SIMULATIONS}' in texts()['simulation-count']
    script = Path('static/plan-page.js').read_text(encoding='utf-8')
    assert int(re.search(r'simulations:(\d+)', script)[1]) == MONTE_CARLO_SIMULATIONS


def test_seed_matches_plan_and_explanation():
    assert SIMULATE_SEED == MONTE_CARLO_SEED
    assert str(MONTE_CARLO_SEED) in texts()['fixed-seed']
    assert f'seed:{MONTE_CARLO_SEED}' in Path('static/plan-page.js').read_text(encoding='utf-8')


def test_depreciation_matches_actual_default():
    assert f'{VEHICLE_DEPRECIATION["value"] * 100:g}%' in texts()['depreciation-default']


def test_maintenance_matches_actual_default():
    assert str(ASSUMPTIONS['annual_maintenance_budget']['value']) in texts()['running-cost-defaults']


def test_fuel_matches_actual_default():
    assert str(ASSUMPTIONS['monthly_fuel_or_energy']['value']) in texts()['running-cost-defaults']


def test_ev_expiry_matches_actual_tax_note():
    date = re.search(r'\d{4}-\d{2}-\d{2}', annual_vehicle_tax(0, 'ev')['notes'][0])[0]
    assert date in texts()['ev-exemption']
    assert '不會自動按免徵到期切換' in texts()['ev-exemption']


def test_block_size_and_parking_match_defaults():
    assert str(BLOCK_MONTHS) in texts()['historical-sampling']
    assert str(ASSUMPTIONS['monthly_parking']['value']) in texts()['parking-budget']


def test_golden_top_three_hit_rate_and_supported_relevance():
    assert len(GOLDEN['answerable']) >= 20
    hits = []
    for row in GOLDEN['answerable']:
        results = retrieve(row['question'])
        assert is_relevant(results), row
        hits.append(bool(set(row['expected']) & {item['id'] for item in results[:3]}))
        assert [item['score'] for item in results] == sorted([item['score'] for item in results], reverse=True)
    assert sum(hits) / len(hits) >= .9
    assert RELEVANCE_THRESHOLD > 0


@pytest.mark.parametrize('question', GOLDEN['unanswerable'] + ['？！…', '請問這個是什麼意思嗎', '的了嗎呢', '   '])
def test_no_answer_and_stopwords_are_irrelevant(question):
    assert not is_relevant(retrieve(question))


def test_normalization_is_deterministic_and_has_no_network():
    assert normalize(' Ｍｏｎｔｅ ＣＡＲＬＯ ') == 'monte carlo'
    assert retrieve('Ｍｏｎｔｅ Ｃａｒｌｏ') == retrieve('monte carlo')
    assert retrieve('淨資產', k=0) == []
