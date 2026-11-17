import asyncio
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from scripts import eval_jev as evaluator
from app.services.intent_router import CRITERIA, Decision


def decision(choice, confidence, probability):
    remaining = (1 - probability) / (len(CRITERIA) - 1)
    return Decision(type='choice', choice=choice, confidence=confidence,
                    probabilities={key: probability if key == choice else remaining for key in CRITERIA})


def test_fixture_content():
    data = json.loads((Path(__file__).parent / 'fixtures/jev_intent_set.json').read_text(encoding='utf-8-sig'))
    assert len(data['questions']) == 40
    counts = Counter(row['label'] for row in data['questions'])
    assert set(counts) == set(CRITERIA)
    assert all(count >= 6 for count in counts.values())


def test_metrics_with_failed_and_harmful_predictions():
    rows = [
        {'label':'knowledge', 'decision':decision('knowledge', .9, .8)},
        {'label':'knowledge', 'decision':decision('compare', .8, .8)},
        {'label':'simulation', 'decision':decision('stress', .8, .6)},
        {'label':'stress', 'decision':decision('stress', .6, .8)},
        {'label':'compare', 'decision':None},
    ]
    result = evaluator.summarize(rows, .7)
    assert result['matrix']['knowledge']['knowledge'] == 1
    assert result['matrix']['knowledge']['compare'] == 1
    assert result['matrix']['simulation']['stress'] == 1
    assert result['matrix']['stress']['stress'] == 1
    assert sum(sum(row.values()) for row in result['matrix'].values()) == 4
    assert result['accuracy'] == .5
    assert result['recall']['knowledge'] == .5
    assert result['recall']['simulation'] == 0
    assert result['recall']['stress'] == 1
    assert result['recall']['compare'] is None
    assert (result['coverage'], result['accepted_accuracy'], result['harmful']) == (.4, .5, 1)
    result = evaluator.summarize(rows, .6)
    assert (result['coverage'], result['accepted_accuracy'], result['harmful']) == (.8, .5, 2)
    result = evaluator.summarize(rows, .9)
    assert (result['coverage'], result['accepted_accuracy'], result['harmful']) == (0, None, 0)


def test_without_live_never_routes(monkeypatch, capsys):
    async def forbidden(_):
        pytest.fail('unexpected API call')
    monkeypatch.setattr(evaluator.intent_router, 'route_question', forbidden)
    evaluator.main([])
    assert 'usage:' in capsys.readouterr().out


def test_missing_key_does_not_route(monkeypatch, capsys):
    monkeypatch.setattr(evaluator, 'settings', replace(evaluator.settings, typesafe_api_key=''))
    async def forbidden(_):
        pytest.fail('unexpected API call')
    monkeypatch.setattr(evaluator.intent_router, 'route_question', forbidden)
    evaluator.main(['--live'])
    assert capsys.readouterr().out.strip() == '未設定金鑰'


def test_all_failures_diagnose_once_and_do_not_reveal_secrets(monkeypatch, capsys):
    monkeypatch.setattr(evaluator, 'settings', replace(evaluator.settings, typesafe_api_key='sk-test-secret'))
    calls = []
    async def fail(question):
        calls.append(question)
        return None
    delays = []
    async def sleep(seconds):
        delays.append(seconds)
    requests = []
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs):
            requests.append(1)
            return httpx.Response(401, text='Authorization: Bearer sk-test-secret')
    monkeypatch.setattr(evaluator.intent_router, 'route_question', fail)
    monkeypatch.setattr(evaluator.asyncio, 'sleep', sleep)
    monkeypatch.setattr(evaluator.httpx, 'AsyncClient', Client)
    evaluator.main(['--live'])
    out = capsys.readouterr().out
    assert len(calls) == 40 and delays == [.5] * 39
    assert len(requests) == 1
    assert out.count('診斷：HTTP 狀態碼 401') == 1
    assert 'sk-test-secret' not in out and 'Authorization' not in out
    assert '已隱藏敏感回應' in out
