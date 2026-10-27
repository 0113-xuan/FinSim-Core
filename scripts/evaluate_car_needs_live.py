"""Opt-in live Gemini evaluation; never imported by the offline test suite."""
import argparse
import asyncio
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import httpx
from app.config import settings
from app.car_needs_ai_schemas import NeedsExtractionRequest, ParsedCarNeeds
from app.services.car_needs_extraction import extract_car_needs
from app.services.gemini_provider import GeminiProvider
from app.services.ai_provider import AIProviderError

CONTEXT = dict(body_types=['suv'],avoid_body_types=[],priorities=['comfort','maintenance_cost'],purposes=['commute'],powertrains=[],ownership_years=3)


def identity(candidate):
    return (candidate['field'],candidate['operation'],candidate['value'])


def compare(expected, actual):
    wanted = {identity(c) for c in expected['candidates']}
    got = {identity(c) for c in actual['candidates']}
    extras, missing = sorted(got-wanted), sorted(wanted-got)
    wanted_unclear = Counter(u['reason'] for u in expected['unclear'])
    got_unclear = Counter(u['reason'] for u in actual['unclear'])
    uncertainty_match = wanted_unclear == got_unclear
    category = '誤判及漏判' if extras and missing else '誤判' if extras else '漏判' if missing else '正確' if uncertainty_match else '無法確認'
    return dict(category=category,extra=extras,missing=missing,uncertainty_match=uncertainty_match)


def expected_conflict(candidate):
    field,op,value = identity(candidate)
    return bool((field == 'avoid_body_types' and op == 'add' and value == 'suv')
        or (field == 'priorities' and op == 'remove' and value in ('comfort','maintenance_cost'))
        or (field == 'ownership_years' and value != 3))


async def evaluate(output):
    if not settings.ai_enabled or settings.ai_provider != 'gemini' or not settings.gemini_api_key:
        raise SystemExit('未啟用可用的 Gemini；沒有發出付費請求。')
    fixtures_path = ROOT/'tests/fixtures/car_needs_p3_cases.json'
    fixtures = json.loads(fixtures_path.read_text(encoding='utf-8'))
    rows = []
    original_client = httpx.AsyncClient
    for case in fixtures:
        usage, models, statuses, raw_outputs, formats = [], [], [], [], []
        async def observe(response):
            await response.aread()
            statuses.append(response.status_code)
            try:
                payload = response.json()
                if 'usageMetadata' in payload:usage.append(payload['usageMetadata'])
                if 'modelVersion' in payload:models.append(payload['modelVersion'])
                if response.status_code == 200:
                    try:
                        raw = GeminiProvider._extract_text(payload)
                        raw_outputs.append(ParsedCarNeeds.model_validate_json(raw).model_dump())
                        formats.append(True)
                    except (ValueError,TypeError,KeyError,IndexError,AIProviderError):formats.append(False)
            except (ValueError,TypeError):pass
        def client_factory(*args,**kwargs):
            kwargs['event_hooks'] = {'response':[observe]}
            return original_client(*args,**kwargs)
        started = time.perf_counter()
        row = dict(id=case['id'],text=case['text'],expected=case['expected'])
        try:
            request = NeedsExtractionRequest(schema_version='2.0',text=case['text'],revision=0,related_answers=CONTEXT)
            with patch('app.services.gemini_provider.httpx.AsyncClient',client_factory):
                result = await extract_car_needs(request,GeminiProvider())
            actual = dict(candidates=[c.model_dump(include={'field','operation','value','evidence'}) for c in result.candidates],unclear=[u.model_dump() for u in result.unclear])
            row.update(actual=actual,**compare(case['expected'],actual),format_valid=True,
                evidence_valid=all(c['evidence'] in case['text'] for c in actual['candidates']+actual['unclear']),
                conflicts_valid=all(bool(c.conflict)==expected_conflict(c.model_dump()) for c in result.candidates))
        except AIProviderError as exc:
            # Exception messages and signed receipts are deliberately not persisted.
            chain=[]
            while exc is not None:
                chain.append(type(exc).__name__)
                exc=exc.__cause__
            row.update(category='服務失敗',format_valid=bool(formats and all(formats)),error_type='timeout' if 'TimeoutError' in chain else 'provider_or_validation')
        if raw_outputs:
            row['raw_model_output']=raw_outputs[-1]
            row['raw_comparison']=compare(case['expected'],raw_outputs[-1])
        row.update(latency_seconds=round(time.perf_counter()-started,3),http_statuses=statuses,usage=usage,model_versions=models)
        rows.append(row)
        report = dict(provider='gemini',configured_model=settings.gemini_model,context=CONTEXT,
            timeout_seconds=settings.ai_onboarding_timeout_seconds,max_retries=settings.ai_max_retries,
            fixture_sha256=hashlib.sha256(fixtures_path.read_bytes()).hexdigest(),
            prompt_sha256=hashlib.sha256((ROOT/'app/prompts/car_needs_extraction.md').read_bytes()).hexdigest(),
            created_at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),cases=rows)
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f"{row['id']}: {row['category']} {row['latency_seconds']}s",flush=True)
        await asyncio.sleep(1)
    report['summary'] = summarize(rows)
    save_report(output,report)
    print(json.dumps(report['summary'],ensure_ascii=False))


def summarize(rows):
    summary = dict(categories=dict(Counter(r['category'] for r in rows)),
        raw_categories=dict(Counter(r.get('raw_comparison',{}).get('category','無可用輸出') for r in rows)),
        total=len(rows),latency_mean=round(statistics.mean(r['latency_seconds'] for r in rows),3),
        latency_max=max(r['latency_seconds'] for r in rows),
        format_failures=sum(not r['format_valid'] and any(s==200 for s in r['http_statuses']) for r in rows),
        api_failures=sum(r['category']=='服務失敗' for r in rows))
    summary['timeouts'] = sum(r.get('error_type') == 'timeout' for r in rows)
    summary['observed_prompt_tokens'] = sum(u.get('promptTokenCount',0) for r in rows for u in r['usage'])
    summary['observed_output_tokens'] = sum(u.get('candidatesTokenCount',0)+u.get('thoughtsTokenCount',0) for r in rows for u in r['usage'])
    summary['billing_note'] = '僅為已收到 usage 的 token；逾時或取消請求可能仍有費用，無法由本機判定實際帳單。'
    summary['latency_p95'] = sorted(r['latency_seconds'] for r in rows)[max(0, int(len(rows)*.95+.999)-1)]
    summary['evidence_failures'] = sum(r.get('evidence_valid') is False for r in rows)
    summary['conflict_failures'] = sum(r.get('conflicts_valid') is False for r in rows)
    if {v for r in rows for v in r['model_versions']} == {'gemini-3.5-flash-lite'}:
        summary['observed_token_cost_usd_estimate'] = round((summary['observed_prompt_tokens']*.30+summary['observed_output_tokens']*2.50)/1000000,8)
        summary['pricing_source'] = 'https://ai.google.dev/gemini-api/docs/pricing'
        summary['pricing_note'] = 'Gemini 3.5 Flash-Lite Standard，輸入 US$0.30/M、輸出（含思考）US$2.50/M；查詢 2026-10-27。非實際帳單。'
    return summary


def save_report(output,report):
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    def short(items):
        return '<br>'.join(f"{c['field']} / {c['operation']} / {c['value']}" for c in items) or '無'
    models = ', '.join(sorted({v for r in report['cases'] for v in r['model_versions']})) or '未收到版本資訊'
    lines = ['# Gemini 28 筆真實模型評估','',f"- 模型設定：`{report['configured_model']}`；實際版本：`{models}`（見逐筆 JSON）。",
        '- 輸入均為人工標註的合成資料，不使用使用者財務資料。',
        '- 與預期比較時，候選 field/operation/value 必須一致；證據允許不同長度，但必須原文連續存在。',
        '- 無法確認：候選一致但 unclear 分類不一致；逾時不當成語意誤判，也不算正確。',
        '- 表格為後端安全檢查後結果；JSON 另留 raw_model_output/raw_comparison，避免把後端防線當模型本身能力。','',
        '## 統計','', '```json',json.dumps(report['summary'],ensure_ascii=False,indent=2),'```','',
        '## 逐筆結果','', '| 案例 | 原文 | 預期候選 | 實際候選 | 分類 | 秒 |','|---|---|---|---|---|---|']
    for row in report['cases']:
        actual = short(row['actual']['candidates']) if 'actual' in row else '未收到可用結果'
        lines.append(f"| {row['id']} | {row['text']} | {short(row['expected']['candidates'])} | {actual} | {row['category']} | {row['latency_seconds']} |")
    lines.extend(['','## 限制','', '- 此次只有一輪；不是統計上穩定的準確率估計，也不是完整自然語言能力評測。',
        '- 逾時案例沒有可用輸出，不能判斷其語意能力、格式或 token 費用。',
        '- 費用僅依回傳 usage 推算；免費額度、稅費、取消後仍計費及重試費用，須查 Google 帳務。',
        '- OpenAI 未進行真實 Structured Outputs 驗收，不列為已正式驗證。',
        '- 重跑：`python -B scripts/evaluate_car_needs_live.py --live --output docs/P4_GEMINI_LIVE_NEXT.json`；會使用 API 額度。'])
    output.with_suffix('.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='28 筆真實 Gemini 評估；會使用已設定 API 額度。')
    parser.add_argument('--live',action='store_true',help='明確授權這次 28 案例實際呼叫')
    parser.add_argument('--summarize',action='store_true',help='只重新統計已有 JSON，不呼叫 API')
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if args.summarize:
        report=json.loads(args.output.read_text(encoding='utf-8'))
        report['summary']=summarize(report['cases'])
        report.setdefault('timeout_seconds',settings.ai_onboarding_timeout_seconds)
        report.setdefault('max_retries',settings.ai_max_retries)
        save_report(args.output,report)
    else:
        if not args.live:parser.error('必須明確指定 --live；未發出請求。')
        asyncio.run(evaluate(args.output))
