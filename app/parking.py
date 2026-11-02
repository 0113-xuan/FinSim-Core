"""Offline parking snapshots and conservative monthly-rent text extraction."""
from functools import lru_cache
import json
from pathlib import Path
import re
from statistics import median
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
MONTHLY = re.compile(r'月租|月票|包月|定期票')
AMOUNT = re.compile(r'(?P<prefix>NT\s*\$|新臺幣|新台幣|\$)?\s*(?P<number>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<cents>\d{1,2}))?\s*(?P<unit>元|圓|TWD|NTD|/月)?', re.I)
NON_MONTHLY = re.compile(r'小時|分鐘|每日|每天|計時|計次|每次|每季|每年|季票|年票|每週|每周|日票|/時|/次|/季|/年')
ALTERNATIVE = re.compile(r'^\s*(?:全日|全天|日間|夜間|平日|假日|汽車|機車|小型車|大型車|每月|租金)')
ANCILLARY = re.compile(r'保證金|押金|手續費|工本費|製卡費|制卡費|遙控器|感應卡')


def parse_monthly_rent(text):
    """Return a price and its exact original clause, or nulls; never hourly rates.

    Full-day clauses win; otherwise choose the highest explicit monthly price.
    Normalisation is for matching only: the returned fragment stays unmodified.
    """
    candidates = []
    for sentence in re.split(r'[。；;\r\n]|<br\s*/?>', text or '', flags=re.I):
        monthly_context = False
        for original in re.split(r'、|(?<!\d)[，,]|[，,](?!\d)', sentence):
            normalized = unicodedata.normalize('NFKC', original)
            keyword = MONTHLY.search(normalized)
            if re.search(r'(?:無|不提供|不售|未提供)\s*(?:月租|月票|包月|定期票)', normalized):
                monthly_context = False
                continue
            if keyword:
                monthly_context = True
            elif not (monthly_context and ALTERNATIVE.search(normalized)):
                continue
            # A clause containing timed/quarterly prices is ambiguous. Prefer a
            # missed reference over presenting an hourly/annual rate as monthly.
            clean = re.sub(r'24\s*小時', '全日', normalized)
            if NON_MONTHLY.search(clean):
                monthly_context = False
                continue
            if any(int(months)>1 for months in re.findall(r'(\d+)\s*個月', normalized)):
                monthly_context = False
                continue
            previous_end = 0
            for match in AMOUNT.finditer(normalized):
                label = normalized[previous_end:match.start()]
                previous_end = match.end()
                # An explicit new rent label ends a preceding ancillary label.
                last_rent = list(MONTHLY.finditer(label))
                if last_rent:
                    label = label[last_rent[-1].end():]
                if ANCILLARY.search(label):
                    continue
                if normalized[:match.start()].rstrip().endswith(('-', '−')):
                    continue
                adjacent = keyword is not None and match.start() >= keyword.end() and normalized[keyword.end():match.start()].strip(' ：:費用金額為是NT$') == ''
                if not (match['prefix'] or match['unit'] or adjacent):
                    continue
                # Numbers that describe a duration, capacity or ticket count are not money.
                if re.match(r'\s*(?:小時|分鐘|日|天|個月|張|位|格|%)', normalized[match.end():]):
                    continue
                amount = float(match['number'].replace(',', '')+'.'+(match['cents'] or '0'))
                if amount < 0:
                    continue
                fragment = original.strip() if keyword else sentence.strip()
                candidates.append((bool(re.search(r'全日|全天|24\s*小時', normalized)), amount, fragment))
    if not candidates:
        return dict(monthly_rent_twd=None, monthly_rent_text=None)
    _, amount, fragment = max(candidates, key=lambda item:(item[0], item[1]))
    return dict(monthly_rent_twd=int(amount) if amount.is_integer() else amount, monthly_rent_text=fragment)


def normalize_tdx(payload):
    """Transform an original TDX response without estimating missing districts."""
    records = payload if isinstance(payload, list) else payload.get('CarParks', [])
    if not isinstance(records, list):
        raise ValueError('TDX 回應沒有有效的停車場清單')
    def name(value):
        return value.get('Zh_tw', '') if isinstance(value, dict) else value or ''
    lots = []
    for record in records:
        fare, offer = record.get('FareDescription') or '', record.get('SpecialOfferDescription') or ''
        position = record.get('CarParkPosition') or {}
        rent = parse_monthly_rent(fare+'；'+offer)
        lots.append(dict(id=str(record.get('CarParkID') or record.get('CarParkUID') or ''),
            name=name(record.get('CarParkName')), district=name(record.get('TownName')),
            address=record.get('Address') or '', lat=record.get('PositionLat', position.get('PositionLat')),
            lon=record.get('PositionLon', position.get('PositionLon')), fare_description=fare,
            special_offer_description=offer, **rent,
            source_updated_at=record.get('SrcUpdateTime') or record.get('UpdateTime') or (payload.get('UpdateTime') if isinstance(payload,dict) else None)))
    if not lots or any(not lot['id'] or not lot['name'] for lot in lots):
        raise ValueError('TDX 停車場資料不完整，未覆寫快照')
    return lots


@lru_cache(maxsize=1)
def load_regions():
    return json.loads((ROOT/'data/regions/tw_districts.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def load_parking_snapshot():
    return json.loads((ROOT/'data/parking/taichung_carparks.json').read_text(encoding='utf-8'))


def parking_reference(city, district, snapshot):
    source = snapshot['source']
    empty = dict(count=0, median=None, minimum=None, maximum=None)
    if city != '臺中市':
        return dict(supported=False,lots=[],monthly_rent_stats=empty,source=source,
                    message='目前只提供臺中市的停車場資料',data_available=False)
    if source['status'] != 'available':
        return dict(supported=True,lots=[],monthly_rent_stats=empty,source=source,data_available=False,
                    message='尚未下載 TDX 停車場快照，請管理者註冊 TDX 並執行下載腳本；目前請自行填寫停車費。')
    lots = [lot for lot in snapshot['lots'] if lot['district']==district]
    prices = [lot['monthly_rent_twd'] for lot in lots if lot['monthly_rent_twd'] is not None]
    stats = dict(count=len(prices),median=median(prices) if len(prices)>=3 else None,
                 minimum=min(prices,default=None),maximum=max(prices,default=None))
    return dict(supported=True,data_available=True,source=source,monthly_rent_stats=stats,
                lots=sorted(lots,key=lambda lot:(lot['monthly_rent_twd'] is None,lot['name']))[:30],
                message='' if lots else '這個行政區目前沒有停車場快照資料，請自行填寫停車費。')
