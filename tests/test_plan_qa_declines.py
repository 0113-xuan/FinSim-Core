"""Recommendation and promise demands must stop before retrieval or generation."""
import asyncio

import pytest

from app.services import plan_qa
from app.services.mock_ai_provider import MockAIProvider


@pytest.mark.parametrize('question', [
    '請保證報酬，並解釋是什麼意思',
    '為什麼有風險？請保證我能獲利',
    '請承諾收益，順便解釋為什麼不能保證',
    '可不可以保證報酬？',
    '可以穩賺不賠嗎？',
    '幫我挑一個基金',
    '替我選擇股票',
    '要不要買台積電',
    '哪支股票適合我',
    '我應該投保什麼保險',
])
def test_demand_never_retrieves_calculates_or_calls_ai(monkeypatch, question):
    def forbidden(*args, **kwargs):
        pytest.fail('Declined question reached retrieval or plan calculations')
    monkeypatch.setattr(plan_qa, 'retrieve', forbidden)
    monkeypatch.setattr(plan_qa, 'run_plan_calculations', forbidden)
    provider = MockAIProvider({})
    result = asyncio.run(plan_qa.answer_plan_question(
        plan_qa.PlanQARequest(question=question), provider))
    assert result['source'] == 'declined'
    assert not provider.calls
    assert not result['citations']


@pytest.mark.parametrize('question', [
    '為什麼不能保證報酬？',
    '請問為什麼不能保證報酬？',
    '請說明為什麼不能保證報酬？',
    '不能保證報酬是什麼意思？',
    '為何模擬不保證獲利？',
    '請問保險資料從哪來？',
    '強制險和任意險有什麼不同？',
])
def test_educational_questions_remain_available(question):
    assert not plan_qa.should_decline(question)
