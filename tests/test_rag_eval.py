"""Retrieval quality floors. Raise a floor when retrieval improves; never lower one to make a change pass."""
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location('eval_rag', Path(__file__).resolve().parents[1] / 'scripts' / 'eval_rag.py')
eval_rag = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(eval_rag)

# Measured 2026-11-17 after adding aliases and the coverage floor (before: unseen recall@3 .83, MRR .71, false accept .50).
# `heldout` was used to write the aliases, so only `unseen` is an honest measure; fold its failures
# into aliases only together with a fresh unseen set.
FLOORS = {
    'golden': dict(recall_at_3=1.0, mrr=0.98, answer_rate=1.0),
    'heldout': dict(recall_at_3=1.0, mrr=1.0, answer_rate=0.95),
    'unseen': dict(recall_at_3=1.0, mrr=29/30, answer_rate=33/35),
}
CEILINGS = {
    'golden': dict(misleading_rate=0.0, false_accept_rate=0.0),
    'heldout': dict(misleading_rate=0.0, false_accept_rate=0.14),
    'unseen': dict(misleading_rate=0.03, false_accept_rate=0.17),
}


@pytest.mark.parametrize('name', eval_rag.SETS)
def test_retrieval_metrics_hold_baseline(name):
    report = eval_rag.evaluate(eval_rag.load(name))
    for key, floor in FLOORS[name].items():
        assert report[key] >= floor, (name, key, report[key])
    for key, ceiling in CEILINGS[name].items():
        assert report[key] <= ceiling, (name, key, report[key])


def test_heldout_expected_ids_exist_and_questions_do_not_overlap_golden():
    from app.services.knowledge_base import load_knowledge
    ids = {entry['id'] for entry in load_knowledge()}
    heldout, golden = eval_rag.load('heldout'), eval_rag.load('golden')
    unseen = eval_rag.load('unseen')
    assert all(set(item['expected']) <= ids for data in (heldout, unseen) for item in data['answerable'])
    seen = {item['question'] for item in golden['answerable']} | set(golden['unanswerable'])
    for data in (heldout, unseen):
        assert not seen & ({item['question'] for item in data['answerable']} | set(data['unanswerable']))
        seen |= {item['question'] for item in data['answerable']} | set(data['unanswerable'])
