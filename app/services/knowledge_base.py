"""Offline, deterministic field-weighted BM25 over the project's Markdown notes."""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / 'data' / 'knowledge'
# Golden set: weakest full-length question > 7.8; incidental single-word overlaps ("今天", "現金") < 3.5.
RELEVANCE_THRESHOLD = 7.0
SHORT_QUERY_FLOOR = 3.5
BM25_K1 = 1.5
BM25_B = 0.75
TITLE_WEIGHT = 4
TAG_WEIGHT = 3
STOP_WORDS = ('請問', '請告訴我', '為什麼', '什麼意思', '是什麼', '怎麼', '如何',
              '這個', '這裡', '今天', '一下', '可以', '是否', '什麼', '的', '了', '嗎', '呢', '我', '是')


def normalize(text: str) -> str:
    return unicodedata.normalize('NFKC', text).casefold().strip()


def tokenize(text: str, *, question: bool = False) -> list[str]:
    value = normalize(text)
    if question:
        for word in STOP_WORDS:
            value = value.replace(word, ' ')
    terms = []
    for run in re.findall(r'[\u3400-\u9fff]+|[a-z0-9]+', value):
        if re.fullmatch(r'[a-z0-9]+', run):
            terms.append(run)
        else:
            terms.extend(run)
            terms.extend(run[i:i + 2] for i in range(len(run) - 1))
    return terms


@lru_cache(maxsize=4)
def load_knowledge(directory: Path = KNOWLEDGE_DIR) -> list[dict]:
    """Validate on demand, never during server startup. Errors name the local section."""
    entries, ids = [], set()
    for path in sorted(Path(directory).glob('*.md')):
        content = path.read_text(encoding='utf-8-sig')
        sections = re.split(r'^## ', content, flags=re.MULTILINE)[1:]
        for section in sections:
            title, _, rest = section.partition('\n')
            metadata, separator, text = rest.strip().partition('\n\n')
            fields = {}
            for line in metadata.splitlines():
                key, colon, value = line.partition(':')
                if not colon or key in fields:
                    raise ValueError(f'{path.name}: {title}: invalid metadata')
                fields[key] = value.strip()
            if not separator or not all(fields.get(key) for key in ('id', 'source', 'tags')) or not title.strip() or not text.strip():
                raise ValueError(f'{path.name}: {title}: missing field')
            if not re.fullmatch(r'[a-z][a-z0-9-]*', fields['id']):
                raise ValueError(f'{path.name}: {title}: invalid id')
            if fields['id'] in ids:
                raise ValueError(f'{path.name}: duplicate id {fields["id"]}')
            if len(text.strip()) > 600:
                raise ValueError(f'{path.name}: {title}: section exceeds 600 characters')
            ids.add(fields['id'])
            entries.append(dict(id=fields['id'], title=title.strip(), source=fields['source'],
                                tags=[tag.strip() for tag in fields['tags'].split(',') if tag.strip()],
                                text=text.strip(), file=path.name))
    if not entries:
        raise ValueError('knowledge base is empty')
    return entries


@lru_cache(maxsize=1)
def _index():
    entries = load_knowledge()
    documents = [Counter(tokenize(item['title']) * TITLE_WEIGHT
                         + tokenize(' '.join(item['tags'])) * TAG_WEIGHT
                         + tokenize(item['text'])) for item in entries]
    frequency = Counter(term for document in documents for term in document)
    lengths = [sum(document.values()) for document in documents]
    return entries, documents, frequency, lengths, sum(lengths) / len(lengths)


def retrieve(question: str, k: int = 4) -> list[dict]:
    terms = set(tokenize(question, question=True))
    # Single characters contribute a small score, but never establish relevance alone.
    meaningful = {term for term in terms if len(term) > 1}
    if not meaningful or k <= 0:
        return []
    entries, documents, frequency, lengths, average = _index()
    results = []
    count = len(entries)
    for item, document, length in zip(entries, documents, lengths):
        if not meaningful.intersection(document):
            continue
        score = 0.0
        for term in terms.intersection(document):
            inverse = math.log(1 + (count - frequency[term] + 0.5) / (frequency[term] + 0.5))
            tf = document[term]
            score += inverse * tf * (BM25_K1 + 1) / (tf + BM25_K1 * (1 - BM25_B + BM25_B * length / average)) * (0.15 if len(term) == 1 else 1)
        coverage = len(meaningful.intersection(document)) / len(meaningful)
        results.append({key: item[key] for key in ('id', 'title', 'source', 'text')}
                       | {'score': round(score, 6), 'coverage': round(coverage, 3)})
    return sorted(results, key=lambda item: (-item['score'], item['id']))[:k]


def is_relevant(results: list[dict]) -> bool:
    if not results:
        return False
    top = results[0]
    # A short term question ("抽樣是什麼") scores low on BM25 alone, so a note that contains every
    # meaningful term still counts, provided it clears a floor above incidental single-word hits.
    return top['score'] >= RELEVANCE_THRESHOLD or (top['coverage'] == 1 and top['score'] >= SHORT_QUERY_FLOOR)
