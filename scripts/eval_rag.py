"""Retrieval metrics for the offline knowledge base. Run from the repository root:
python scripts/eval_rag.py [--verbose]   (no AI, no network)

`golden` is the set the relevance threshold was tuned on; `heldout` was written afterwards in
colloquial wording and never used for tuning. Judge changes by `heldout`.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.knowledge_base import is_relevant, retrieve

FIXTURES = Path(__file__).resolve().parents[1] / 'tests' / 'fixtures'
SETS = {'golden': 'rag_golden.json', 'heldout': 'rag_heldout.json', 'unseen': 'rag_heldout2.json'}


def evaluate(data: dict) -> dict:
    rows, reciprocal, top1, top3, answered, misleading = [], [], 0, 0, 0, 0
    for item in data['answerable']:
        results = retrieve(item['question'], k=10)
        ids = [hit['id'] for hit in results]
        rank = next((i for i, found in enumerate(ids, 1) if found in item['expected']), None)
        accepted = is_relevant(results)
        reciprocal.append(1 / rank if rank else 0)
        top1 += rank == 1
        top3 += bool(rank and rank <= 3)
        answered += accepted
        # Accepted, but none of the top 3 notes is right: the user would get a confident wrong answer.
        misleading += accepted and not (rank and rank <= 3)
        rows.append(dict(question=item['question'], expected=item['expected'], got=ids[:3], rank=rank, accepted=accepted))
    wrongly_accepted = [q for q in data['unanswerable'] if is_relevant(retrieve(q))]
    total = len(data['answerable'])
    return dict(
        answerable=total, unanswerable=len(data['unanswerable']),
        recall_at_1=top1 / total, recall_at_3=top3 / total, mrr=sum(reciprocal) / total,
        answer_rate=answered / total, misleading_rate=misleading / total,
        false_accept_rate=len(wrongly_accepted) / len(data['unanswerable']),
        failures=[row for row in rows if not row['rank'] or row['rank'] > 3 or not row['accepted']],
        wrongly_accepted=wrongly_accepted,
    )


def load(name: str) -> dict:
    return json.loads((FIXTURES / SETS[name]).read_text(encoding='utf-8'))


if __name__ == '__main__':
    verbose = '--verbose' in sys.argv
    reports = {name: evaluate(load(name)) for name in SETS}
    print('| 指標 | ' + ' | '.join(f'{name}（可答 {r["answerable"]}／不可答 {r["unanswerable"]}）' for name, r in reports.items()) + ' |')
    print('| --- | ' + ' | '.join('---' for _ in reports) + ' |')
    for key, label in (('recall_at_1', 'recall@1'), ('recall_at_3', 'recall@3'), ('mrr', 'MRR'),
                       ('answer_rate', '可答題被接受（越高越好）'), ('misleading_rate', '接受但前三筆都錯（越低越好）'),
                       ('false_accept_rate', '不可答題被接受（越低越好）')):
        print(f'| {label} | ' + ' | '.join(f'{r[key]:.3f}' for r in reports.values()) + ' |')
    if verbose:
        for name, report in reports.items():
            print(f'\n## {name} 失敗題')
            for row in report['failures']:
                print(f'- {row["question"]}｜期望 {row["expected"]}｜前三 {row["got"]}｜名次 {row["rank"]}｜接受 {row["accepted"]}')
            for question in report['wrongly_accepted']:
                print(f'- 不可答卻被接受：{question}')
