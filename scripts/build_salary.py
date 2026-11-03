"""Convert the official DGBAS table 16 XLSX offline, using only the standard library."""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import re
import sys
import unicodedata
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.occupations import INDUSTRIES

NS = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
SOURCE_URL = 'https://ws.dgbas.gov.tw/001/Upload/463/relfile/10980/236558/%E8%A1%A816.xlsx'


def xlsx_cells(path):
    """Read cached values and original strings; no spreadsheet recalculation."""
    with ZipFile(path) as archive:
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings = [''.join(node.itertext()) for node in
                       ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('x:si', NS)]
        sheet = ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
        cells = {}
        for cell in sheet.findall('.//x:sheetData/x:row/x:c', NS):
            value = cell.find('x:v', NS)
            if cell.get('t') == 's' and value is not None:
                cells[cell.get('r')] = strings[int(value.text)]
            elif cell.get('t') == 'inlineStr':
                cells[cell.get('r')] = ''.join(cell.find('x:is', NS).itertext())
            elif value is not None and value.text is not None:
                cells[cell.get('r')] = Decimal(value.text)
        return cells


def canonical(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', value)).replace('﹑', '、')


def build_snapshot(path):
    cells = xlsx_cells(path)
    if ('按行業別及僱用型態分' not in cells.get('A1', '')
            or cells.get('F3') != '本國籍全時受僱員工'
            or canonical(cells.get('H5', '')) != '每人每月經常性薪資平均數d'):
        raise ValueError('原始檔不是預期的表16本國籍全時員工經常性薪資欄位，未更新快照')
    periods = []
    for address, value in cells.items():
        if re.fullmatch(r'A\d+', address) and isinstance(value, str):
            # NFKC turns the source's circled provisional mark Ⓟ into P.
            match = re.fullmatch(r'(\d+)年1至(\d+)月P?', canonical(value))
            if match:
                periods.append((int(match[1]) + 1911, int(match[2]), int(address[1:])))
    year, month, start = max(periods)
    rows = []
    for code, name in INDUSTRIES:
        matches = [address for address, value in cells.items()
                   if re.fullmatch(r'A\d+', address) and int(address[1:]) > start
                   and isinstance(value, str) and canonical(value) == canonical(name)]
        if len(matches) != 1:
            raise ValueError(f'{name} 的官方資料缺漏或重複，未更新快照')
        source_cell = 'H' + matches[0][1:]
        salary = cells[source_cell]
        if not isinstance(salary, Decimal) or salary <= 0 or salary != salary.to_integral_value():
            raise ValueError(f'{name} 的薪資欄位無效，未更新快照')
        rows.append(dict(industry_code=code, name=name, average_regular_salary=int(salary),
                         median=None, source_cell=source_cell))
    return dict(period=f'{year}-01/{year}-{month:02}', source=dict(
        name='受僱員工薪資調查：按行業別及僱用型態分（表16）', publisher='行政院主計總處',
        url='https://www.stat.gov.tw/News_Content.aspx?n=2724&s=236558', data_url=SOURCE_URL,
        query_url='https://earnings.dgbas.gov.tw/query_payroll.aspx',
        population='本國籍全時受僱員工', unit='新臺幣元／月', statistic='平均經常性薪資（稅前）',
        period_label=f'{year} 年 1–{month} 月', published_date='2026-08-10', downloaded_date='2026-11-04',
        provisional=True, median_note='同期間、同行業及同僱用型態的中位數未在此表提供，故為 null。',
        license='政府資料開放授權條款－第1版', license_url='https://www.stat.gov.tw/cp.aspx?n=3164'),
        industries=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT/'data/salary/raw/table16_202606.xlsx')
    parser.add_argument('--output', type=Path, default=ROOT/'data/salary/tw_regular_salary.json')
    args = parser.parse_args()
    data = build_snapshot(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f"已轉換 {len(data['industries'])} 個行業；資料期間 {data['period']}，未連網。")


if __name__ == '__main__':
    main()
