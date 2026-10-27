"""Extract candidates only; sign review evidence, never run financial calculations."""
import asyncio
import base64
import hashlib
import hmac
import json
import logging
import re
import secrets
import time
from time import perf_counter

from pydantic import ValidationError
from app.car_needs_ai_schemas import AIExtractionMetadata, NeedsExtractionRequest, ParsedCarNeeds, UnclearNeed
from app.config import settings
from app.services.ai_provider import AIProviderError
from app.services.prompt_loader import load_prompt

logger = logging.getLogger(__name__)
_PROCESS_KEY = secrets.token_bytes(32)
TTL_SECONDS = 1800
LABELS = dict(sedan='轎車', hatchback='掀背車', suv='SUV／休旅車', mpv='多人座車',
              space='空間', comfort='乘坐舒適', energy_cost='節省油電費', maintenance_cost='低保養費', safety='安全配備',
              commute='日常通勤', family='家庭接送', work='工作用車', leisure='休閒出遊',
              client_transport='接送客戶', elderly_transport='接送長輩', ice='汽油', hev='油電', bev='純電')


def _key():
    configured = settings.car_needs_signing_key
    if configured and len(configured.encode()) < 32:
        raise ValueError('AI 候選簽章金鑰設定無效。')
    return configured.encode() if configured else _PROCESS_KEY


def _encode(value):
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


def _sign(payload):
    body = _encode(json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode())
    return body + '.' + _encode(hmac.new(_key(), body.encode(), hashlib.sha256).digest())


def _read(receipt):
    try:
        body, signature = receipt.split('.')
        expected = _encode(hmac.new(_key(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError()
        payload = json.loads(base64.urlsafe_b64decode(body + '=' * (-len(body) % 4)))
        if payload['version'] != 2 or not payload['issued_at'] <= time.time() <= payload['issued_at'] + TTL_SECONDS:
            raise ValueError()
        return payload
    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        raise ValueError('AI 候選已過期或無效，請重新分析或改用問卷。') from exc


def conflict_for(candidate, context):
    field, operation, value = candidate.field, candidate.operation, candidate.value
    opposite = {'body_types':'avoid_body_types', 'avoid_body_types':'body_types'}.get(field)
    if operation == 'add' and opposite and value in context[opposite]:
        return '與問卷的車型偏好／排除條件衝突；接受後會移除相反條件。'
    if field == 'ownership_years' and context[field] is not None and context[field] != value:
        return '與問卷持有年限不同；接受後會取代原答案。'
    if operation == 'remove' and value in context[field]:
        return '與問卷已選條件衝突；接受後會移除此項偏好。'
    return None


def apply_confirmed(context, candidate):
    field, operation, value = candidate['field'], candidate['operation'], candidate['value']
    if operation == 'set':
        context[field] = value
    else:
        context[field] = [v for v in context[field] if v != value]
        if operation == 'add':
            context[field].append(value)
            opposite = {'body_types':'avoid_body_types', 'avoid_body_types':'body_types'}.get(field)
            if opposite:
                context[opposite] = [v for v in context[opposite] if v != value]


async def extract_car_needs(request: NeedsExtractionRequest, provider, *, provider_name=None):
    started, success = perf_counter(), False
    name = provider_name or settings.ai_provider
    if provider is None or name not in ('gemini', 'openai'):
        raise AIProviderError('AI 尚未設定，仍可略過分析並使用問卷推薦。')
    try:
        result = await asyncio.wait_for(provider.generate_structured(
            system_prompt=load_prompt('car_needs_extraction.md'),
            user_prompt=json.dumps(dict(text=request.text, related_answers=request.related_answers.model_dump()), ensure_ascii=False),
            response_schema=ParsedCarNeeds), timeout=settings.ai_onboarding_timeout_seconds)
        parsed = ParsedCarNeeds.model_validate(result.model_dump() if hasattr(result, 'model_dump') else result)
        all_evidence = [c.evidence for c in parsed.candidates] + [u.evidence for u in parsed.unclear]
        if any(not e.strip() or e not in request.text for e in all_evidence):
            raise ValueError('AI 原文證據不符合輸入。')
        # A calendar plan is not evidence of a vehicle holding period.
        supported = []
        for candidate in parsed.candidates:
            if candidate.field == 'ownership_years' and (
                    not re.search(r'持有|換車|用車年限|ownership|holding|keep.{0,15}car|replace.{0,15}car', candidate.evidence, re.I)
                    or re.search(r'可能|也許|不確定|perhaps|maybe|might', candidate.evidence, re.I)):
                if not any(u.evidence == candidate.evidence for u in parsed.unclear):
                    parsed.unclear.append(UnclearNeed(evidence=candidate.evidence, reason='uncertain'))
            else:
                supported.append(candidate)
        parsed = ParsedCarNeeds(candidates=supported, unclear=parsed.unclear)
        identities = [(c.field, c.operation, c.value) for c in parsed.candidates]
        if len(set(identities)) != len(identities):
            raise ValueError('重複候選。')
        if sum(c.field == 'ownership_years' for c in parsed.candidates) > 1:
            raise ValueError('持有年限候選互相矛盾。')
        for c in parsed.candidates:
            if any(c.field == other.field and c.value == other.value and c.operation != other.operation for other in parsed.candidates):
                raise ValueError('AI 候選互相矛盾。')
            if c.field in ('body_types','avoid_body_types') and c.operation == 'add' and any(other.field != c.field and other.field in ('body_types','avoid_body_types') and other.operation == 'add' and other.value == c.value for other in parsed.candidates):
                raise ValueError('AI 車型條件互相矛盾。')
        context = request.related_answers.model_dump()
        candidates = []
        for index, candidate in enumerate(parsed.candidates):
            value_label = LABELS.get(candidate.value, str(candidate.value))
            label = f'持有 {value_label} 年' if candidate.field == 'ownership_years' else (
                ('移除：' if candidate.operation == 'remove' else '排除：' if candidate.field == 'avoid_body_types' else '加入：') + value_label)
            candidates.append(dict(**candidate.model_dump(), id=f'c{index}', label=label,
                                   conflict=conflict_for(candidate, context), source='ai_structured'))
        issued = int(time.time())
        payload = dict(version=2, issued_at=issued, nonce=secrets.token_hex(8), provider=name,
                       text_hash=hashlib.sha256(request.text.encode()).hexdigest(), revision=request.revision,
                       context=context, candidates=candidates, unclear=[u.model_dump() for u in parsed.unclear])
        response = AIExtractionMetadata(schema_version='2.0', provider=name, is_real_ai=True,
            status='candidates' if candidates else 'no_match', revision=request.revision,
            candidates=candidates, unclear=parsed.unclear, receipt=_sign(payload), expires_at=issued+TTL_SECONDS,
            accepted_ids=[], rejected_ids=[])
        success = True
        return response
    except TimeoutError as exc:
        raise AIProviderError('AI 分析逾時，需求仍保留，可重試或略過分析。') from exc
    except (ValidationError, ValueError, TypeError) as exc:
        raise AIProviderError('AI 回傳未通過安全驗證，未更改任何條件，可略過分析。') from exc
    finally:
        logger.info('car_needs_extraction provider=%s duration_ms=%.1f success=%s', name, (perf_counter()-started)*1000, success)


def validate_confirmed_ai(needs):
    metadata = needs.extraction
    payload = _read(metadata.receipt)
    if (payload['provider'] != metadata.provider or payload['revision'] != metadata.revision
            or needs.revision != metadata.revision + len(metadata.candidates)
            or payload['text_hash'] != hashlib.sha256(needs.free_text.encode()).hexdigest()
            or payload['candidates'] != [c.model_dump() for c in metadata.candidates]
            or payload['unclear'] != [u.model_dump() for u in metadata.unclear]
            or metadata.expires_at != payload['issued_at'] + TTL_SECONDS):
        raise ValueError('AI 候選與目前問卷不一致，請重新分析。')
    accepted, rejected = metadata.accepted_ids, metadata.rejected_ids
    ids = {c['id'] for c in payload['candidates']}
    if len(set(accepted)) != len(accepted) or len(set(rejected)) != len(rejected) or set(accepted) & set(rejected) or set(accepted) | set(rejected) != ids:
        raise ValueError('請逐項接受或拒絕全部 AI 候選。')
    expected = payload['context']
    for candidate_id in accepted:
        apply_confirmed(expected, next(c for c in payload['candidates'] if c['id'] == candidate_id))
    actual = dict(body_types=needs.preferences.body_types, avoid_body_types=needs.constraints.avoid_body_types,
                  priorities=needs.preferences.priorities, purposes=needs.usage.purposes,
                  powertrains=needs.preferences.powertrains, ownership_years=needs.usage.ownership_years)
    if any(set(expected[k]) != set(actual[k]) if isinstance(expected[k], list) else expected[k] != actual[k] for k in expected):
        raise ValueError('已確認的 AI 條件與問卷不一致，請重新確認。')
