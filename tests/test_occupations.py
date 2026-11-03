from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient
import pytest

from app.occupations import load_salary_snapshot
from main import app
from scripts.build_salary import build_snapshot

ROOT = Path(__file__).resolve().parents[1]
CLIENT = TestClient(app)


def test_occupation_list_matches_all_official_snapshot_industries():
    response = CLIENT.get('/occupations')
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 21 and len({item['id'] for item in items}) == 21
    official = {row['industry_code']: row for row in load_salary_snapshot()['industries']}
    assert {item['industry_code'] for item in items if item['salary_reference']} == set(official)
    for item in items:
        if item['salary_reference']:
            assert official[item['industry_code']]['name'] == item['name']
        else:
            assert item['industry_code'] is None
    assert {item['name'] for item in items if not item['salary_reference']} == {'軍公教', '學生', '自由業或接案', '其他'}


@pytest.mark.parametrize('code,expected', [('20', 51476), ('80', 38743), ('90', 72533), ('140', 34110)])
def test_salary_reference_uses_national_full_time_regular_salary_column(code, expected):
    response = CLIENT.get('/salary-reference', params={'occupation': f'industry_{code}'})
    assert response.status_code == 200
    result = response.json()
    assert result['available'] is True and result['average_regular_salary'] == expected
    assert result['median'] is None
    assert result['period'] == '2026-01/2026-06'
    assert result['source']['population'] == '本國籍全時受僱員工'
    assert result['source']['downloaded_date'] == '2026-11-04'
    assert result['note'] == '這是該行業所有受僱員工的平均，不分年資與職位；剛出社會的起薪通常較低。'


@pytest.mark.parametrize('occupation', ['public_sector', 'student', 'freelance', 'other'])
def test_unavailable_occupations_never_substitute_another_population(occupation):
    result = CLIENT.get('/salary-reference', params={'occupation': occupation}).json()
    assert result['available'] is False
    assert result['average_regular_salary'] is result['median'] is result['period'] is None
    if occupation == 'public_sector':
        assert result['note'] == '公部門薪資依俸給表計算，請自行填寫'


@pytest.mark.parametrize('value', ['', 'missing', '../industry_20'])
def test_unknown_occupation_is_422(value):
    assert CLIENT.get('/salary-reference', params={'occupation': value}).status_code == 422


def test_offline_salary_conversion_reproduces_snapshot_without_modifying_raw():
    path = ROOT/'data/salary/raw/table16_202606.xlsx'
    before = path.read_bytes()
    snapshot = deepcopy(load_salary_snapshot())
    assert build_snapshot(path) == snapshot
    assert path.read_bytes() == before
    assert len(snapshot['industries']) == 17
    assert all(row['average_regular_salary'] > 0 and row['source_cell'].startswith('H') for row in snapshot['industries'])


def test_converter_rejects_a_different_employee_population(tmp_path):
    original = ROOT/'data/salary/raw/table16_202606.xlsx'
    invalid = tmp_path/'wrong-population.xlsx'
    with ZipFile(original) as source, ZipFile(invalid, 'w') as target:
        for name in source.namelist():
            contents = source.read(name)
            if name == 'xl/sharedStrings.xml':
                contents = contents.replace('本國籍全時受僱員工'.encode(), '全體受僱員工'.encode())
            target.writestr(name, contents)
    with pytest.raises(ValueError, match='本國籍全時員工'):
        build_snapshot(invalid)
