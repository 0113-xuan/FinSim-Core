"""Offline parking snapshots and conservative monthly-rent text extraction."""
from functools import lru_cache
import json
from pathlib import Path
import re
from statistics import median
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
CITY_CODES = {
    'Taipei':'臺北市','NewTaipei':'新北市','Taoyuan':'桃園市','Taichung':'臺中市',
    'Tainan':'臺南市','Kaohsiung':'高雄市','Keelung':'基隆市','Hsinchu':'新竹市',
    'HsinchuCounty':'新竹縣','MiaoliCounty':'苗栗縣','ChanghuaCounty':'彰化縣',
    'NantouCounty':'南投縣','YunlinCounty':'雲林縣','ChiayiCounty':'嘉義縣',
    'Chiayi':'嘉義市','PingtungCounty':'屏東縣','YilanCounty':'宜蘭縣',
    'HualienCounty':'花蓮縣','TaitungCounty':'臺東縣','KinmenCounty':'金門縣',
    'PenghuCounty':'澎湖縣','LienchiangCounty':'連江縣',
}
MONTHLY = re.compile(r'月租|月票|月繳|每月|/月|／月|包月|定期票')
PREFIX_MONTHLY = re.compile(r'月租|月票|月繳|每月|包月|定期票')
AMOUNT = re.compile(r'(?P<prefix>NT\s*\$|新臺幣|新台幣|\$)?\s*(?P<number>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<cents>\d{1,2}))?\s*(?P<unit>元|圓|TWD|NTD)?', re.I)
RATE = re.compile(r'半年租|年租|季租|半年繳|季繳|年繳|每季|每年|季票|年票|一年|半年|每週|每周|'
                  r'月租|月票|月繳|每月|包月|定期票|計時|計次|臨停|小時|分鐘|每日|每天|當日|日票|/時|/次')
OTHER_PERIOD = re.compile(r'半年租|年租|季租|半年繳|季繳|年繳|每季|每年|季票|年票|一年|半年|每週|每周')
VEHICLE = re.compile(r'小型採購車|自用車|小型車|小客車|電動汽車|汽車|機車|公車|大型車|大客車|大貨車|小貨車|貨車|遊覽車|自行車')
CAR_TYPES = {'小型採購車','自用車','小型車','小客車','電動汽車','汽車'}
ALTERNATIVE = re.compile(r'^\s*(?:全日|全天|日間|夜間|平日|假日|汽車|機車|小型車|大型車|每月|租金|里民|身障|一般|住戶|學生|校外)')
ANCILLARY = re.compile(r'保證金|押金|手續費|工本費|製卡費|制卡費|遙控器|感應卡|罰款|違約金|充電|每度')


def _trailing_other_billing(following):
    """Distinguish a required trailing period from a separately priced option."""
    next_month = PREFIX_MONTHLY.search(following)
    if next_month:
        following = following[:next_month.start()]
    period = re.search(r'半年繳|季繳|年繳|[一1]季繳|[一1]年繳', following)
    if not period:
        return False
    before, after = following[:period.start()], following[period.end():]
    required = bool(re.search(r'需|須|必須|一律|僅|限|為$', before))
    if required:
        return True
    # E.g. 月租1200元季繳3000元: the latter has its own price, so it
    # does not turn the first monthly offer into quarterly-only billing.
    separate_price = AMOUNT.match(after.lstrip(' ：:繳納費付'))
    if separate_price and (separate_price['prefix'] or separate_price['unit']):
        return False
    if re.search(r'可|另有|另提供|亦可', before) or re.match(r'\s*(?:享|優惠|打|可)', after):
        return False
    return True


def parse_monthly_rent(text):
    """Read each amount with its preceding rate/vehicle labels and following unit.

    Timed prices before a monthly label cannot contaminate the monthly amount.
    Quarterly/annual billing remains excluded even when expressed per month.
    Returned text is the original sentence, retaining eligibility conditions.
    """
    candidates = []
    vehicle = None
    for sentence in re.split(r'[。；;\r\n]|<br\s*/?>', text or '', flags=re.I):
        rate, full_day, duration = None, False, False
        normalized_sentence = unicodedata.normalize('NFKC', sentence)
        search_start = 0
        for original in re.split(r'、|(?<!\d)[，,]|[，,](?!\d)', sentence):
            normalized = unicodedata.normalize('NFKC', original)
            clause_start = normalized_sentence.find(normalized, search_start)
            search_start = clause_start + len(normalized)
            if re.search(r'(?:無|不提供|不售|未提供)\s*(?:月租|月票|包月|定期票|月繳)', normalized):
                rate = None
                continue
            inherited = rate == 'monthly' and bool(ALTERNATIVE.search(normalized))
            previous_end = 0
            for match in AMOUNT.finditer(normalized):
                label = normalized[previous_end:match.start()]
                previous_end = match.end()
                kinds = list(VEHICLE.finditer(label))
                if kinds:
                    vehicle = kinds[-1].group()
                periods = list(RATE.finditer(label))
                if periods:
                    last = periods[-1]
                    rate = 'monthly' if PREFIX_MONTHLY.fullmatch(last.group()) else 'other' if OTHER_PERIOD.fullmatch(last.group()) else 'timed'
                    duration = False
                    label = label[last.end():]
                windows = re.findall(r'全日|全天|24\s*小時|日間|夜間|平日|假日', normalized[:match.start()])
                if windows:
                    full_day = bool(re.fullmatch(r'全日|全天|24\s*小時', windows[-1]))
                tail = normalized[match.end():]
                suffix_month = bool(re.match(r'\s*/\s*月(?!(?:租|繳|票)\s*[:：]?\s*(?:NT\s*\$|\$)?\s*\d)', tail, flags=re.I))
                suffix_other = bool(re.match(r'\s*/\s*(?:季|年|半年|一年)', tail))
                if re.match(r'\s*個月', tail) and int(match['number'].replace(',','')) > 1:
                    duration = True
                    rate = 'other'
                    continue
                if rate == 'other' or suffix_other or duration:
                    continue
                if _trailing_other_billing(normalized_sentence[clause_start+match.end():]):
                    continue
                if vehicle is not None and vehicle not in CAR_TYPES:
                    continue
                if not (rate == 'monthly' or suffix_month):
                    continue
                if not (periods or inherited or suffix_month):
                    continue
                if ANCILLARY.search(label):
                    continue
                if normalized[:match.start()].rstrip().endswith(('-', '−')):
                    continue
                adjacent = periods and periods[-1].group() != '每月' and label.strip(' ：:費用金額收為是NT$') == ''
                if not (match['prefix'] or match['unit'] or adjacent or suffix_month):
                    continue
                if re.match(r'\s*(?:小時|分鐘|日|天|個月|張|位|格|%|/時|/半?小時|/次|/天|/日)', tail):
                    continue
                amount = float(match['number'].replace(',', '')+'.'+(match['cents'] or '0'))
                candidates.append((full_day, amount, sentence.strip()))
            # A label-only clause can introduce alternatives in the same sentence.
            if not AMOUNT.search(normalized):
                periods = list(RATE.finditer(normalized))
                if periods:
                    rate = 'monthly' if PREFIX_MONTHLY.fullmatch(periods[-1].group()) else 'other'
    if not candidates:
        return dict(monthly_rent_twd=None, monthly_rent_text=None)
    _, amount, fragment = max(candidates, key=lambda item:(item[0], item[1]))
    return dict(monthly_rent_twd=int(amount) if amount.is_integer() else amount, monthly_rent_text=fragment)


def resolve_district(city, town_name, address, lot_name):
    """Match only official districts in this city; never use coordinates or guesses."""
    canonical = lambda value: unicodedata.normalize('NFKC', value or '').replace('台','臺')
    districts = next((row['districts'] for row in load_regions() if row['city']==city), [])
    valid = {canonical(d):d for d in districts}
    if canonical(town_name) in valid:
        return valid[canonical(town_name)], 'town_name'
    for text, source in [(address,'address'),(lot_name,'name')]:
        normalized = canonical(text)
        if source == 'address' and any(other!=city and canonical(other) in normalized for other in CITY_CODES.values()):
            continue
        matches = [original for key,original in valid.items() if key in normalized]
        if len(matches)==1:
            return matches[0], source
    return '', 'none'


def is_scooter_only(name):
    """Exclude scooter-only names, retaining mixed car/scooter lots and attractions."""
    return '機車' in name and not any(kind in name for kind in ('汽車', '汽機車', '小型車'))


def normalize_tdx(payload, city):
    """Transform original TDX rows and keep the first occurrence of each city ID."""
    records = payload if isinstance(payload, list) else payload.get('CarParks', [])
    if not isinstance(records, list):
        raise ValueError('TDX 回應沒有有效的停車場清單')
    def name(value):
        return value.get('Zh_tw', '') if isinstance(value, dict) else value or ''
    lots, seen = [], set()
    for record in records:
        id = str(record.get('CarParkID') or record.get('CarParkUID') or '')
        if id in seen:
            continue
        seen.add(id)
        fare, offer = record.get('FareDescription') or '', record.get('SpecialOfferDescription') or ''
        position = record.get('CarParkPosition') or {}
        rent = parse_monthly_rent(fare+'；'+offer)
        lot_name = name(record.get('CarParkName'))
        district, district_source = resolve_district(city,name(record.get('TownName')),record.get('Address'),lot_name)
        lots.append(dict(id=id,
            name=lot_name, district=district, district_source=district_source,
            address=record.get('Address') or '', lat=record.get('PositionLat', position.get('PositionLat')),
            lon=record.get('PositionLon', position.get('PositionLon')), fare_description=fare,
            special_offer_description=offer, **rent,
            source_updated_at=record.get('SrcUpdateTime') or record.get('UpdateTime') or (payload.get('SrcUpdateTime') or payload.get('UpdateTime') if isinstance(payload,dict) else None)))
    if any(not lot['id'] or not lot['name'] for lot in lots):
        raise ValueError('TDX 停車場資料不完整，未覆寫快照')
    return lots


@lru_cache(maxsize=1)
def load_regions():
    return json.loads((ROOT/'data/regions/tw_districts.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def load_parking_snapshot():
    return json.loads((ROOT/'data/parking/tw_carparks.json').read_text(encoding='utf-8'))


def parking_reference(city, district, snapshot):
    source = snapshot['source']
    empty = dict(count=0, median=None, minimum=None, maximum=None)
    entry = snapshot['cities'].get(city)
    if city in snapshot['unavailable'] or entry is None:
        return dict(supported=False,lots=[],monthly_rent_stats=empty,source=source,coverage=None,
                    message=f'TDX 目前沒有{city}的路外停車場資料，請自行填寫停車費。',data_available=False)
    lots = [lot for lot in entry['lots'] if lot['district']==district]
    prices = [lot['monthly_rent_twd'] for lot in lots if lot['monthly_rent_twd'] is not None]
    stats = dict(count=len(prices),median=median(prices) if len(prices)>=3 else None,
                 minimum=min(prices,default=None),maximum=max(prices,default=None))
    return dict(supported=True,data_available=True,source=source,tdx_city=entry['tdx_city'],coverage=entry['coverage'],monthly_rent_stats=stats,
                lots=sorted(lots,key=lambda lot:(lot['monthly_rent_twd'] is None,lot['name']))[:30],
                message='' if lots else f'{district}在 TDX 資料中沒有可對應的停車場，請自行填寫停車費。')
