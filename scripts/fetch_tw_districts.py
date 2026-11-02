"""Build the region snapshot from Ministry of the Interior NLSC XML services."""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import time
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://api.nlsc.gov.tw/other/'


def build(offline=False):
    folder = ROOT/'data/regions'
    raw = folder/'raw'
    raw.mkdir(parents=True, exist_ok=True)

    def xml(endpoint, filename):
        path = raw/filename
        if not offline:
            content = urllib.request.urlopen(BASE+endpoint, timeout=30).read()
            ET.fromstring(content)  # Validate before replacing a good snapshot.
            path.write_bytes(content)
            time.sleep(.25)
        return ET.fromstring(path.read_bytes())

    counties = xml('ListCounty', 'counties.xml')
    regions = []
    for county in counties.findall('countyItem'):
        code = county.findtext('countycode')
        towns = xml(f'ListTown1/{code}', f'towns-{code}.xml')
        regions.append(dict(city=county.findtext('countyname'),
                            districts=[town.findtext('townname') for town in towns.findall('townItem')]))
    assert len(regions) == 22 and sum(len(r['districts']) for r in regions) == 368
    assert len(next(r for r in regions if r['city']=='臺中市')['districts']) == 29
    (folder/'tw_districts.json').write_text(json.dumps(regions, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f"行政區快照：{len(regions)} 縣市、368 鄉鎮市區；日期 {datetime.now(timezone(timedelta(hours=8))).date()}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='只從已下載的 raw XML 重建')
    build(parser.parse_args().offline)
