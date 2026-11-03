"""Industry references from DGBAS; occupations never determine financial inputs."""
from functools import lru_cache
import json
from pathlib import Path

# industry_code is the salary survey query system's sIND_CODE, not a job title.
INDUSTRIES = (
    ('10', '礦業及土石採取業'), ('20', '製造業'), ('30', '電力及燃氣供應業'),
    ('40', '用水供應及污染整治業'), ('50', '營建工程業'), ('60', '批發及零售業'),
    ('70', '運輸及倉儲業'), ('80', '住宿及餐飲業'), ('90', '出版影音及資通訊業'),
    ('100', '金融及保險業'), ('110', '不動產業'), ('120', '專業、科學及技術服務業'),
    ('130', '支援服務業'), ('140', '教育業（不含小學以上各級公私立學校等）'),
    ('150', '醫療保健及社會工作服務業'), ('160', '藝術、娛樂及休閒服務業'), ('170', '其他服務業'),
)
NON_INDUSTRIES = (
    ('public_sector', '軍公教', '公部門薪資依俸給表計算，請自行填寫'),
    ('student', '學生', '學生沒有對應的官方行業薪資參考，請自行填寫新實領月薪。'),
    ('freelance', '自由業或接案', '受僱員工調查不代表自由業或接案收入，請自行填寫新實領月薪。'),
    ('other', '其他', '尚未對應官方行業薪資資料，請自行填寫新實領月薪。'),
)
SALARY_NOTE = '這是該行業所有受僱員工的平均，不分年資與職位；剛出社會的起薪通常較低。'


def occupations():
    return [dict(id=f'industry_{code}', name=name, industry_code=code, salary_reference=True)
            for code, name in INDUSTRIES] + [
        dict(id=id, name=name, industry_code=None, salary_reference=False)
        for id, name, _ in NON_INDUSTRIES]


@lru_cache(maxsize=1)
def load_salary_snapshot():
    path = Path(__file__).resolve().parents[1] / 'data/salary/tw_regular_salary.json'
    return json.loads(path.read_text(encoding='utf-8'))


def salary_reference(occupation, snapshot):
    item = next((item for item in occupations() if item['id'] == occupation), None)
    if item is None:
        raise ValueError('請選擇清單中的職業或行業')
    if not item['salary_reference']:
        note = next(note for id, _, note in NON_INDUSTRIES if id == occupation)
        return dict(available=False, occupation=occupation, average_regular_salary=None,
                    median=None, period=None, source=None, note=note)
    row = next(row for row in snapshot['industries'] if row['industry_code'] == item['industry_code'])
    return dict(available=True, occupation=occupation, average_regular_salary=row['average_regular_salary'],
                median=row['median'], period=snapshot['period'], source=snapshot['source'], note=SALARY_NOTE)
