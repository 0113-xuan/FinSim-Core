from __future__ import annotations

from uuid import uuid4

from app.scenario_schemas import (
    ScenarioDraft,
    ScenarioDraftMessageRequest,
    ScenarioDraftMessageResponse,
    ScenarioDraftStatus,
    ScenarioRequest,
    ScenarioType,
)
from app.schemas import ScenarioParseRequest
from app.services.scenario_parser import parse_scenario


INTENT_TYPES = {
    "vehicle_purchase": ScenarioType.vehicle_purchase,
    "relocation": ScenarioType.housing_change,
}


def _contextualize_reply(previous: ScenarioDraft | None, message: str) -> str:
    """Attach the active question's subject to a short follow-up answer."""
    reply = message.strip()
    if not previous or not previous.next_question:
        return reply

    question = previous.next_question
    if "目前房租" in question and not any(term in reply for term in ("房租", "租金", "租屋費")):
        return f"目前房租{reply}"
    if "新房租" in question and not any(term in reply for term in ("房租", "租金", "租屋費")):
        return f"新房租{reply}"
    if any(term in question for term in ("押金", "仲介費", "搬家費")):
        if reply in {"不知道", "不清楚", "不確定", "未知", "還沒問", "尚未決定"}:
            return f"押金、仲介費和搬家費都{reply}"
        if reply in {"沒有", "不用", "不需要", "都沒有"}:
            return "沒有押金、仲介費或搬家費"
    if "通勤費" in question and not any(term in reply for term in ("通勤", "交通", "車資")):
        return f"通勤費{reply}"
    return reply


def continue_scenario_draft(
    request: ScenarioDraftMessageRequest,
    *,
    confirmed_profile: dict | None = None,
) -> ScenarioDraftMessageResponse:
    """Merge user-held conversation context and return one deterministic next question."""
    previous = request.draft
    if previous and previous.status != ScenarioDraftStatus.collecting:
        raise ValueError("此情境草稿已完成，請重新建立後再繼續對話。")
    contextualized_reply = _contextualize_reply(previous, request.message)
    messages = [*(previous.messages if previous else []), contextualized_reply]
    if len(messages) > 12 or sum(len(item) for item in messages) > 6000:
        raise ValueError("情境對話過長，請重新建立一個情境草稿。")

    parsed = parse_scenario(
        ScenarioParseRequest(
            text="\n".join(messages),
            months=request.months,
            reference_date=request.reference_date,
            timezone=request.timezone,
            profile_draft_id=request.profile_draft_id,
        ),
        confirmed_profile=confirmed_profile,
    )

    scenario_request = (
        ScenarioRequest.model_validate(parsed.typed_scenario_request)
        if parsed.typed_scenario_request
        else None
    )
    clarification = parsed.clarification
    next_question = clarification.questions[0] if clarification and clarification.questions else None
    if clarification and len(clarification.questions) > 1:
        parsed.clarification = clarification.model_copy(update={"questions": [next_question]})

    scenario_type = scenario_request.scenario_type if scenario_request else None
    if scenario_type is None and clarification:
        scenario_type = INTENT_TYPES.get(clarification.intent)
    if previous and previous.scenario_type and scenario_type and previous.scenario_type != scenario_type:
        raise ValueError("目前回答與既有情境類型衝突，請重新開始對話。")

    ready = scenario_request is not None
    draft = ScenarioDraft(
        draft_id=previous.draft_id if previous else f"scenario-{uuid4().hex}",
        status=ScenarioDraftStatus.ready_for_review if ready else ScenarioDraftStatus.collecting,
        messages=messages,
        scenario_type=scenario_type or (previous.scenario_type if previous else None),
        missing_fields=list(clarification.missing_fields) if clarification and not ready else [],
        next_question=None if ready else next_question,
        scenario_request=scenario_request,
    )
    return ScenarioDraftMessageResponse(
        draft=draft,
        parsed=parsed,
        ready_for_review=ready,
    )


def confirm_scenario_draft(draft: ScenarioDraft) -> ScenarioDraft:
    if (
        draft.status == ScenarioDraftStatus.confirmed
        and draft.scenario_request is not None
        and not draft.missing_fields
    ):
        return draft
    if draft.status != ScenarioDraftStatus.ready_for_review:
        raise ValueError("情境草稿尚未完成，不能加入模擬。")
    if draft.scenario_request is None or draft.missing_fields:
        raise ValueError("情境草稿仍有缺漏欄位，不能加入模擬。")
    return draft.model_copy(update={"status": ScenarioDraftStatus.confirmed})
