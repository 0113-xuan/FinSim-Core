"""Evaluate the production intent router; live requests require explicit opt-in."""
import argparse
import asyncio
import json
import logging
import math
import re
import statistics
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import settings
from app.services import intent_router
import httpx

LABELS = tuple(intent_router.CRITERIA)
URL = 'https://api.typesafe.ai/v1/systemone'


def summarize(rows, threshold):
    matrix = {label: {choice: 0 for choice in LABELS} for label in LABELS}
    successful = [row for row in rows if row['decision'] is not None]
    accepted = []
    for row in successful:
        decision = row['decision']
        matrix[row['label']][decision.choice] += 1
        if decision.confidence >= threshold and decision.probabilities[decision.choice] >= threshold:
            accepted.append(row)
    correct = sum(row['label'] == row['decision'].choice for row in successful)
    accepted_correct = sum(row['label'] == row['decision'].choice for row in accepted)
    harmful = sum(row['label'] in ('knowledge', 'simulation') and row['decision'].choice in ('compare', 'stress') for row in accepted)
    recall = {label: (matrix[label][label] / sum(matrix[label].values()) if sum(matrix[label].values()) else None) for label in LABELS}
    return {'matrix': matrix, 'accuracy': correct / len(successful) if successful else None,
            'recall': recall, 'coverage': len(accepted) / len(rows) if rows else 0,
            'accepted_accuracy': accepted_correct / len(accepted) if accepted else None, 'harmful': harmful}


def percent(value):
    return '無資料' if value is None else f'{value * 100:.1f}%'


def percentile(values, q):
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    lower = math.floor(index)
    upper = math.ceil(index)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def safe_cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')


def print_report(rows):
    durations = [row['elapsed'] for row in rows]
    successful = sum(row['decision'] is not None for row in rows)
    result = summarize(rows, .7)
    print('## 總表')
    print('| 成功率 | 失敗題數 | 平均延遲（秒） | p50（秒） | p95（秒） | 最大延遲（秒） |')
    print('| --- | ---: | ---: | ---: | ---: | ---: |')
    print(f'| {percent(successful / len(rows) if rows else 0)} | {len(rows) - successful} | {statistics.fmean(durations) if durations else 0:.3f} | {percentile(durations, .5) if durations else 0:.3f} | {percentile(durations, .95) if durations else 0:.3f} | {max(durations, default=0):.3f} |')
    print('\n## 混淆矩陣（成功題，列為正確、欄為預測）')
    print('| 正確／預測 | ' + ' | '.join(LABELS) + ' |')
    print('| --- | ' + ' | '.join(['---:'] * len(LABELS)) + ' |')
    for label in LABELS:
        print('| ' + label + ' | ' + ' | '.join(str(result['matrix'][label][choice]) for choice in LABELS) + ' |')
    print('\n## 準確率與召回率（僅成功題）')
    print(f"準確率：{percent(result['accuracy'])}")
    print('| 類別 | 召回率 |\n| --- | ---: |')
    for label in LABELS:
        print(f"| {label} | {percent(result['recall'][label])} |")
    print('\n## 信心門檻掃描（涵蓋率以全部題目為分母）')
    print('| 門檻 | 涵蓋率 | 被採用題目準確率 | 有害誤判數 |\n| ---: | ---: | ---: | ---: |')
    for threshold in (.5, .6, .7, .8, .9):
        item = summarize(rows, threshold)
        print(f"| {threshold:.1f} | {percent(item['coverage'])} | {percent(item['accepted_accuracy'])} | {item['harmful']} |")
    print('\n## 逐題明細')
    print('| 題目 | 正確 | 預測 | 信心 | 前兩項機率 | 延遲（秒） | 0.7 採用 |\n| --- | --- | --- | ---: | --- | ---: | --- |')
    for row in rows:
        d = row['decision']
        if d is None:
            print(f"| {safe_cell(row['q'])} | {row['label']} | 失敗 | — | — | {row['elapsed']:.3f} | 否 |")
            continue
        top = ', '.join(f'{key} {value:.3f}' for key, value in sorted(d.probabilities.items(), key=lambda item: item[1], reverse=True)[:2])
        adopted = '否' if intent_router.needs_clarification(d) else '是'
        print(f"| {safe_cell(row['q'])} | {row['label']} | {d.choice} | {d.confidence:.3f} | {top} | {row['elapsed']:.3f} | {adopted} |")


async def diagnose():
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            response = await client.post(URL, headers={'Authorization': f'Bearer {settings.typesafe_api_key}'},
                json={'model': settings.jev_model, 'state': {'question': '測試'},
                      'questions': {'intent': {'type': 'choice', 'criteria': intent_router.CRITERIA}}})
        body = response.text[:200]
        # Provider errors can echo secrets or authorization headers.
        if settings.typesafe_api_key in body or re.search(r'(?i)(authorization|bearer|api[_ -]?key|secret|sk-[a-z0-9_-]+)', body):
            body = '[已隱藏敏感回應]'
        print(f"\n診斷：HTTP 狀態碼 {response.status_code}；回應：{safe_cell(body)}")
    except Exception:
        print('\n診斷：HTTP 狀態碼無；無法取得回應。')


async def evaluate(questions):
    rows = []
    for index, item in enumerate(questions):
        if index:
            await asyncio.sleep(.5)
        start = perf_counter()
        try:
            decision = await intent_router.route_question(item['q'])
        except Exception:
            decision = None
        rows.append({**item, 'decision': decision, 'elapsed': perf_counter() - start})
    print_report(rows)
    if rows and all(row['decision'] is None for row in rows):
        await diagnose()


def main(argv=None):
    parser = argparse.ArgumentParser(description='評估 Jev 意圖路由')
    parser.add_argument('--live', action='store_true', help='呼叫實際 API')
    args = parser.parse_args(argv)
    if not args.live:
        parser.print_usage()
        return
    if not settings.typesafe_api_key:
        print('未設定金鑰')
        return
    with (ROOT / 'tests/fixtures/jev_intent_set.json').open(encoding='utf-8-sig') as file:
        questions = json.load(file)['questions']
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        asyncio.run(evaluate(questions))
    finally:
        logging.disable(previous)


if __name__ == '__main__':
    main()
