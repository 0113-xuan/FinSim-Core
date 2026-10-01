from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4

from app.config import settings
from app.extraction_schemas import (
    ExtractionSource,
    FinancialExtractionResult,
    RiskPreference,
)
from app.services.financial_amount import find_financial_amounts
from app.schemas import (
    DebtDraft,
    DraftFieldValue,
    FinancialProfileDraft,
    ProfileValueSource,
    VariableExpenseAllocationDraft,
)


FIELD_LABELS = {
    "cash_and_deposits": "現金與存款",
    "investments": "投資",
    "other_assets": "其他資產",
    "monthly_salary": "每月薪資",
    "other_recurring_income": "其他固定收入",
    "fixed_expenses": "每月固定支出",
    "total_variable_expenses": "每月變動支出",
    "monthly_debt_payments": "每月債務付款",
    "emergency_fund": "緊急預備金",
    "simulation_months": "模擬期間",
    "risk_preference": "風險偏好",
}

REQUIRED_FIELDS = (
    "cash_and_deposits",
    "monthly_salary",
    "fixed_expenses",
    "total_variable_expenses",
    "simulation_months",
)

INTERVIEW_QUESTIONS = (
    {
        "field": "cash_and_deposits",
        "stage": "財務概況",
        "question": "現金與存款大約多少？",
    },
    {
        "field": "monthly_salary",
        "stage": "每月收入",
        "question": "每月實領薪資大約多少？",
    },
    {
        "field": "fixed_expenses",
        "stage": "固定支出",
        "question": "每月固定支出大約多少？",
    },
    {
        "field": "total_variable_expenses",
        "stage": "生活支出",
        "question": "每月生活支出大約多少？",
    },
    {
        "field": "simulation_months",
        "stage": "模擬期間",
        "question": "想模擬未來幾年？",
    },
)

DEFAULT_ALLOCATION = {
    "food": 0.30,
    "transportation": 0.15,
    "shopping": 0.12,
    "entertainment": 0.10,
    "medical": 0.08,
    "education": 0.08,
    "travel": 0.10,
    "other": 0.07,
}

AMOUNT_PATTERN = r"(?:約|大約|差不多|將近)?\s*([\d,.]+)\s*(萬|千|[kK]|元|塊)?"
STANDALONE_AMOUNT_PATTERN = rf"^\s*{AMOUNT_PATTERN}\s*$"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_field(default: Any = None, reason: str = "尚未提供") -> DraftFieldValue:
    return DraftFieldValue(
        value=default,
        source=ProfileValueSource.system_default,
        confidence=1 if default is not None else 0,
        confirmed=False,
        reason=reason,
    )


def create_draft() -> FinancialProfileDraft:
    now = _now()
    draft = FinancialProfileDraft(
        id=str(uuid4()),
        cash_and_deposits=_empty_field(),
        investments=_empty_field(0, "未提供時暫以 0 顯示，確認前不會儲存"),
        other_assets=_empty_field(0, "未提供時暫以 0 顯示，確認前不會儲存"),
        monthly_salary=_empty_field(),
        other_recurring_income=_empty_field(0, "未提供其他固定收入"),
        fixed_expenses=_empty_field(),
        total_variable_expenses=_empty_field(),
        monthly_debt_payments=_empty_field(0, "未提供債務付款"),
        emergency_fund=_empty_field(0, "未提供獨立緊急預備金"),
        simulation_months=_empty_field(60, "系統預設模擬 60 個月"),
        risk_preference=_empty_field("中性", "系統預設風險偏好"),
        created_at=now,
        updated_at=now,
    )
    return validate_draft(draft)


def _unresolved_debts(draft: FinancialProfileDraft) -> List[DebtDraft]:
    return [item for item in draft.debts if item.monthly_payment.value is None]


def _debt_field(
    value: Any,
    *,
    source: ProfileValueSource,
    confidence: float,
    confirmed: bool,
    reason: str,
    message_ref: str,
    original_value: str,
) -> DraftFieldValue:
    return DraftFieldValue(
        value=value,
        source=source,
        confidence=confidence,
        confirmed=confirmed,
        reason=reason,
        original_message_ref=message_ref,
        original_value=original_value,
    )


def _refresh_debt_total(draft: FinancialProfileDraft, changed: List[str]) -> None:
    unresolved = _unresolved_debts(draft)
    if unresolved:
        draft.monthly_debt_payments = _empty_field(None, "仍有債務尚未提供每月付款")
    elif draft.debts:
        total = sum(Decimal(str(item.monthly_payment.value)) for item in draft.debts)
        draft.monthly_debt_payments = DraftFieldValue(
            value=total.quantize(Decimal("0.01")),
            source=ProfileValueSource.backend_normalized,
            confidence=min(item.monthly_payment.confidence for item in draft.debts),
            confirmed=False,
            reason="由債務明細的每月付款在後端加總",
            normalized_from="後端加總債務明細",
            normalization_source="backend_calculation",
        )
    if "monthly_debt_payments" not in changed:
        changed.append("monthly_debt_payments")


def _apply_debt_payment_answer(
    draft: FinancialProfileDraft,
    text: str,
    message_ref: str,
) -> bool:
    unresolved = _unresolved_debts(draft)
    if not unresolved:
        return False
    standalone = re.fullmatch(STANDALONE_AMOUNT_PATTERN, text, re.IGNORECASE)
    explicit = re.search(
        rf"(?:每個月|每月|月)\s*(?:繳|付|付款)?\s*{AMOUNT_PATTERN}",
        text,
        re.IGNORECASE,
    )
    match = standalone or explicit
    if not match:
        return False
    value = _amount(match.group(1), match.group(2))
    debt = unresolved[0]
    debt.monthly_payment = _debt_field(
        value,
        source=ProfileValueSource.user_provided,
        confidence=0.98,
        confirmed=True,
        reason="使用者補充這筆債務的每月付款",
        message_ref=message_ref,
        original_value=text.strip(),
    )
    return True


def _amount(raw: str, unit: Optional[str]) -> float:
    value = float(raw.replace(",", ""))
    if unit == "萬":
        value *= 10_000
    elif unit in ("千", "k", "K"):
        value *= 1_000
    return round(value, 2)


def is_standalone_amount_answer(text: str) -> bool:
    """Return whether a guided-interview answer contains only one amount."""
    return bool(
        re.fullmatch(STANDALONE_AMOUNT_PATTERN, text, re.IGNORECASE)
        or re.fullmatch(r"\s*\d+\s*(?:年|個?月)\s*", text)
    )


def _find_amount(text: str, keywords: Iterable[str]) -> Optional[Tuple[float, str, bool]]:
    keyword_pattern = "|".join(re.escape(item) for item in keywords)
    patterns = [
        rf"(?:{keyword_pattern})[^\d]{{0,12}}{AMOUNT_PATTERN}",
        rf"{AMOUNT_PATTERN}[^\n，。；]{{0,8}}(?:{keyword_pattern})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw, unit = match.group(1), match.group(2)
            approximate = bool(re.search(r"(約|大約|差不多|將近)", match.group(0)))
            return _amount(raw, unit), match.group(0).strip(), approximate
    return None


def is_ambiguous_total_expense_message(text: str) -> bool:
    if not re.search(r"(?:每月)?(?:生活)?(?:開銷|總支出|支出總額)", text):
        return False
    if re.search(r"(?:固定支出|變動支出|房租|租金|保險|伙食|餐飲|交通)", text):
        return False
    return bool(find_financial_amounts(text))


def _pending_expense_reply(
    draft: FinancialProfileDraft,
    text: str,
    message_ref: str,
) -> List[str] | None:
    if is_ambiguous_total_expense_message(text):
        amount = find_financial_amounts(text)[0][2].value
        draft.pending_total_expense = DraftFieldValue(
            value=amount,
            source=ProfileValueSource.user_provided,
            confidence=0.98,
            confirmed=True,
            reason="使用者提供的是未分類的每月總支出，尚未拆分固定與變動支出",
            original_message_ref=message_ref,
            original_value=text.strip(),
        )
        draft.pending_total_expense_kind = "unclassified"
        return ["pending_total_expense"]
    pending = draft.pending_total_expense
    if pending is None:
        return None
    amounts = find_financial_amounts(text)
    fixed_amount = amounts[0][2].value if amounts else None
    says_combined = bool(re.search(r"(?:全部|總支出|合計|固定.*變動|包含.*生活)", text))
    says_fixed_only = bool(re.search(r"(?:只有|都是|算是)?\s*固定(?:支出)?", text))
    if fixed_amount is not None and (says_combined or "固定" in text):
        total = Decimal(str(pending.value))
        if fixed_amount > total:
            draft.conflicts.append("固定支出不能高於先前提供的每月總支出。")
            return []
        _set_field(draft, "fixed_expenses", fixed_amount, message_ref, text.strip())
        _set_field(
            draft, "total_variable_expenses", total - fixed_amount,
            message_ref, f"每月總支出 {total} 減固定支出 {fixed_amount}",
            normalized_from="由每月總支出扣除固定支出",
        )
        draft.pending_total_expense = None
        draft.pending_total_expense_kind = None
        return ["fixed_expenses", "total_variable_expenses"]
    if says_fixed_only:
        _set_field(
            draft, "fixed_expenses", pending.value, message_ref,
            str(pending.original_value or pending.value),
        )
        draft.pending_total_expense = None
        draft.pending_total_expense_kind = None
        return ["fixed_expenses"]
    if says_combined:
        draft.pending_total_expense_kind = "combined"
        return ["pending_total_expense"]
    if draft.pending_total_expense_kind == "combined" and fixed_amount is not None:
        total = Decimal(str(pending.value))
        if fixed_amount > total:
            draft.conflicts.append("固定支出不能高於先前提供的每月總支出。")
            return []
        _set_field(draft, "fixed_expenses", fixed_amount, message_ref, text.strip())
        _set_field(
            draft, "total_variable_expenses", total - fixed_amount,
            message_ref, f"每月總支出 {total} 減固定支出 {fixed_amount}",
            normalized_from="由每月總支出扣除固定支出",
        )
        draft.pending_total_expense = None
        draft.pending_total_expense_kind = None
        return ["fixed_expenses", "total_variable_expenses"]
    return []


def _frequency_normalized(text: str, amount: float, fragment: str) -> Tuple[float, Optional[str]]:
    nearby = fragment + " " + text[max(0, text.find(fragment) - 10): text.find(fragment) + len(fragment) + 10]
    if re.search(r"(每週|一週|weekly)", nearby, re.IGNORECASE):
        return round(amount * 52 / 12, 2), f"{fragment}，由每週金額換算為每月"
    if re.search(r"(每年|一年|年薪|annual|yearly)", nearby, re.IGNORECASE):
        return round(amount / 12, 2), f"{fragment}，由每年金額換算為每月"
    return amount, None


def _set_field(
    draft: FinancialProfileDraft,
    field_name: str,
    value: Any,
    message_ref: str,
    fragment: str,
    approximate: bool = False,
    normalized_from: Optional[str] = None,
) -> None:
    previous = getattr(draft, field_name)
    replaceable_default = not previous.confirmed and (
        previous.source == ProfileValueSource.system_default
        or previous.value in (None, 0, "")
    )
    if (
        not replaceable_default
        and previous.value not in (None, 0, "")
        and previous.value != value
    ):
        draft.conflicts.append(
            f"{FIELD_LABELS[field_name]}原為 {previous.value}，本次訊息為 {value}，請確認要採用哪一個。"
        )
        return
    source = ProfileValueSource.ai_extracted if approximate or normalized_from else ProfileValueSource.user_provided
    setattr(
        draft,
        field_name,
        DraftFieldValue(
            value=value,
            source=source,
            confidence=0.76 if approximate else (0.88 if normalized_from else 0.98),
            confirmed=not approximate and normalized_from is None,
            reason="依使用者訊息擷取" if not approximate else "使用者提供約略金額，需再次確認",
            original_message_ref=message_ref,
            original_value=fragment,
            normalized_from=normalized_from,
        ),
    )


def _propose_allocation(total: float) -> List[VariableExpenseAllocationDraft]:
    amounts: List[float] = []
    keys = list(DEFAULT_ALLOCATION)
    for ratio in list(DEFAULT_ALLOCATION.values())[:-1]:
        amounts.append(round(total * ratio))
    amounts.append(round(total - sum(amounts), 2))
    return [
        VariableExpenseAllocationDraft(
            category=category,
            amount=amounts[index],
            percentage=round((amounts[index] / total * 100) if total else 0, 2),
            source=ProfileValueSource.ai_estimated,
            confidence=0.55,
            confirmed=False,
            reason="依系統可調整的預設比例提出，尚未取得分類明細",
        )
        for index, category in enumerate(keys)
    ]


def extract_message(draft: FinancialProfileDraft, text: str) -> FinancialProfileDraft:
    updated = deepcopy(draft)
    updated.version += 1
    updated.updated_at = _now()
    message_ref = f"msg-{updated.version}"
    standalone = re.fullmatch(STANDALONE_AMOUNT_PATTERN, text, re.IGNORECASE)
    if standalone and any(
        _needs_interview_answer(getattr(updated, item["field"]))
        for item in INTERVIEW_QUESTIONS
    ):
        # A prior model misclassification must not trap a guided interview in a
        # conflict loop. The amount belongs to the first unanswered question.
        updated.conflicts = []
    original_snapshot = updated.model_dump()

    pending_changes = _pending_expense_reply(updated, text, message_ref)
    if pending_changes is not None:
        total = float(updated.total_variable_expenses.value or 0)
        if total > 0 and not updated.variable_expense_allocation:
            updated.variable_expense_allocation = _propose_allocation(total)
        updated.audit_trail.append({
            "version": updated.version,
            "action": "expense_classification",
            "message_ref": message_ref,
            "changed_fields": pending_changes,
            "ambiguous": updated.pending_total_expense is not None,
            "timestamp": updated.updated_at,
        })
        return validate_draft(updated)

    mappings = {
        "cash_and_deposits": ("存款", "現金", "銀行", "cash", "deposit"),
        "investments": ("投資", "股票", "基金", "investment"),
        "other_assets": ("其他資產", "房產", "不動產", "other asset"),
        "monthly_salary": ("月薪", "年薪", "薪水", "薪資", "收入", "salary"),
        "other_recurring_income": ("其他收入", "副業", "租金收入", "other income"),
        "fixed_expenses": ("固定支出", "房租", "保險", "fixed expense"),
        "total_variable_expenses": ("變動支出", "生活費", "伙食交通", "variable expense"),
        "monthly_debt_payments": ("每月貸款", "債務付款", "月繳", "loan payment"),
        "emergency_fund": ("緊急預備金", "預備金", "emergency fund"),
    }
    for field_name, keywords in mappings.items():
        found = _find_amount(text, keywords)
        if not found:
            continue
        value, fragment, approximate = found
        normalized_value, normalized_from = _frequency_normalized(text, value, fragment)
        _set_field(
            updated,
            field_name,
            normalized_value,
            message_ref,
            fragment,
            approximate,
            normalized_from,
        )

    duration = re.search(r"(?:模擬|規劃|看未來)?\s*(\d+)\s*(年|個?月)", text)
    if duration:
        value = int(duration.group(1)) * (12 if duration.group(2) == "年" else 1)
        _set_field(updated, "simulation_months", value, message_ref, duration.group(0))

    risk = re.search(r"(保守|穩健|中性|積極|高風險|低風險)", text)
    if risk:
        _set_field(updated, "risk_preference", risk.group(1), message_ref, risk.group(0))

    scalar_changed = any(
        getattr(updated, field_name).model_dump() != original_snapshot[field_name]
        for field_name in FIELD_LABELS
    )
    debt_payment_changed = False
    core_question_pending = any(
        _needs_interview_answer(getattr(updated, item["field"]))
        for item in INTERVIEW_QUESTIONS
    )
    if not scalar_changed and not core_question_pending:
        debt_payment_changed = _apply_debt_payment_answer(updated, text, message_ref)
        if debt_payment_changed:
            _refresh_debt_total(updated, [])
    if standalone and not scalar_changed:
        current_question = next(
            (
                item
                for item in INTERVIEW_QUESTIONS
                if _needs_interview_answer(getattr(updated, item["field"]))
            ),
            None,
        )
        if current_question:
            field_name = current_question["field"]
            if field_name == "simulation_months":
                value = int(float(standalone.group(1).replace(",", ""))) * 12
            else:
                value = _amount(standalone.group(1), standalone.group(2))
            _set_field(
                updated,
                field_name,
                value,
                message_ref,
                text.strip(),
                approximate=bool(re.search(r"(約|大約|差不多|將近)", text)),
            )

    if re.search(r"(買車|買房|搬家|旅行|旅遊|結婚|留學|轉職|退休)", text):
        if not any(item.original_value == text for item in updated.future_plans):
            updated.future_plans.append(
                DraftFieldValue(
                    value=text[:300],
                    source=ProfileValueSource.ai_extracted,
                    confidence=0.9,
                    confirmed=False,
                    reason="辨識為未來財務計畫，不列入一般每月支出",
                    original_message_ref=message_ref,
                    original_value=text[:300],
                )
            )

    total = float(updated.total_variable_expenses.value or 0)
    if total > 0 and not updated.variable_expense_allocation:
        updated.variable_expense_allocation = _propose_allocation(total)

    changed = []
    for field_name in FIELD_LABELS:
        if getattr(updated, field_name).model_dump() != original_snapshot[field_name]:
            changed.append(field_name)
    if debt_payment_changed and "monthly_debt_payments" not in changed:
        changed.append("monthly_debt_payments")
    updated.audit_trail.append({
        "version": updated.version,
        "action": "ai_extraction",
        "message_ref": message_ref,
        "changed_fields": changed,
        "ambiguous": not changed and bool(re.search(r"(看情況|不一定|不知道|很難說|depends)", text, re.IGNORECASE)),
        "timestamp": updated.updated_at,
    })
    return validate_draft(updated)


RISK_PREFERENCE_LABELS = {
    RiskPreference.conservative: "保守",
    RiskPreference.balanced: "中性",
    RiskPreference.growth: "積極",
    RiskPreference.aggressive: "高風險",
}


def merge_extraction_candidates(
    draft: FinancialProfileDraft,
    result: FinancialExtractionResult,
    text: str,
) -> FinancialProfileDraft:
    """Apply validated candidates without allowing the model to overwrite draft values."""
    updated = deepcopy(draft)
    updated.version += 1
    updated.updated_at = _now()
    message_ref = f"msg-{updated.version}"
    changed: List[str] = []

    for candidate in result.fields:
        field_name = candidate.field.value
        current = getattr(updated, field_name)
        value = (
            RISK_PREFERENCE_LABELS[candidate.value]
            if isinstance(candidate.value, RiskPreference)
            else Decimal(str(candidate.value))
            if candidate.normalized_frequency is not None
            else float(candidate.value)
        )
        current_is_default = not current.confirmed and (
            current.source == ProfileValueSource.system_default
            or current.value in (None, 0, "")
        )
        current_is_empty = current.value in (None, "")
        same_value = current.value == value
        if not current_is_empty and not current_is_default and not same_value:
            updated.conflicts.append(
                f"{FIELD_LABELS[field_name]}原為 {current.value}，本次訊息為 {value}，請確認要採用哪一個。"
            )
            continue
        if same_value and not current_is_default:
            continue

        normalized = candidate.normalized_frequency is not None
        approximate = candidate.value_range is not None or candidate.source != ExtractionSource.user_provided
        source = (
            ProfileValueSource.backend_normalized
            if normalized
            else ProfileValueSource.user_provided
            if not approximate and candidate.confidence >= 0.95
            else ProfileValueSource.ai_extracted
        )
        setattr(
            updated,
            field_name,
            DraftFieldValue(
                value=value,
                source=source,
                confidence=float(candidate.confidence),
                confirmed=source == ProfileValueSource.user_provided,
                reason=candidate.reason,
                original_message_ref=message_ref,
                original_value=candidate.original_value,
                normalized_from=candidate.normalized_from,
                original_amount=candidate.original_amount,
                original_frequency=(
                    candidate.original_frequency.value
                    if candidate.original_frequency is not None
                    else None
                ),
                normalization_source="backend_calculation" if normalized else None,
            ),
        )
        changed.append(field_name)

    if result.variable_expense_allocation and not updated.variable_expense_allocation:
        total = float(updated.total_variable_expenses.value or 0)
        amount_total = round(sum(item.amount for item in result.variable_expense_allocation), 2)
        if total > 0 and abs(total - amount_total) <= 0.01:
            allocations: List[VariableExpenseAllocationDraft] = []
            allocated_percentage = 0.0
            for index, item in enumerate(result.variable_expense_allocation):
                percentage = (
                    round(100 - allocated_percentage, 2)
                    if index == len(result.variable_expense_allocation) - 1
                    else round(item.amount / total * 100, 2)
                )
                allocated_percentage += percentage
                allocations.append(VariableExpenseAllocationDraft(
                    category=item.category.value,
                    amount=item.amount,
                    percentage=percentage,
                    source=ProfileValueSource.ai_estimated,
                    confidence=item.confidence,
                    confirmed=False,
                    reason=item.reason,
                ))
            updated.variable_expense_allocation = allocations

    for debt in result.debts:
        if debt.debt_type.value == "none":
            current = updated.monthly_debt_payments
            if current.source == ProfileValueSource.system_default and not current.confirmed:
                updated.monthly_debt_payments = DraftFieldValue(
                    value=0,
                    source=ProfileValueSource.user_provided,
                    confidence=debt.confidence,
                    confirmed=True,
                    reason=debt.reason,
                    original_message_ref=message_ref,
                    original_value=debt.original_value,
                )
                changed.append("monthly_debt_payments")
            continue
        if any(
            item.monthly_payment.original_value == debt.original_value
            or item.principal.original_value == debt.original_value
            for item in updated.debts
        ):
            continue
        payment = Decimal(str(debt.monthly_payment)) if debt.monthly_payment is not None else None
        debt_value_source = (
            ProfileValueSource.user_provided
            if debt.source.value == "user_provided" and debt.confidence >= 0.95
            else ProfileValueSource.ai_extracted
        )
        existing = next(
            (item for item in updated.debts if item.name == (debt.name or debt.debt_type.value)),
            None,
        )
        if existing is not None:
            if debt.remaining_balance is not None and existing.principal.value is None:
                existing.principal = _debt_field(
                    Decimal(str(debt.remaining_balance)), source=debt_value_source,
                    confidence=debt.confidence, confirmed=False, reason=debt.reason,
                    message_ref=message_ref, original_value=debt.original_value,
                )
            if payment is not None and existing.monthly_payment.value is None:
                existing.monthly_payment = _debt_field(
                    payment, source=debt_value_source, confidence=debt.confidence,
                    confirmed=debt_value_source == ProfileValueSource.user_provided,
                    reason=debt.reason, message_ref=message_ref,
                    original_value=debt.original_value,
                )
            elif payment is not None and Decimal(str(existing.monthly_payment.value)) != payment:
                updated.conflicts.append(
                    f"{existing.name}每月付款原為 {existing.monthly_payment.value}，本次為 {payment}，請確認要採用哪個數字。"
                )
            continue
        updated.debts.append(
            DebtDraft(
                name=debt.name or debt.debt_type.value,
                principal=DraftFieldValue(
                    value=(Decimal(str(debt.remaining_balance)) if debt.remaining_balance is not None else None),
                    source=(debt_value_source if debt.remaining_balance is not None else ProfileValueSource.system_default),
                    confidence=(debt.confidence if debt.remaining_balance is not None else 0),
                    confirmed=False,
                    reason=debt.reason,
                    original_message_ref=message_ref,
                    original_value=debt.original_value,
                ),
                monthly_payment=DraftFieldValue(
                    value=payment,
                    source=(debt_value_source if payment is not None else ProfileValueSource.system_default),
                    confidence=(debt.confidence if payment is not None else 0),
                    confirmed=(payment is not None and debt_value_source == ProfileValueSource.user_provided),
                    reason=(debt.reason if payment is not None else "使用者尚未提供每月付款"),
                    original_message_ref=message_ref,
                    original_value=debt.original_value,
                ),
                annual_interest_rate=(
                    DraftFieldValue(
                        value=debt.annual_interest_rate,
                        source=debt_value_source,
                        confidence=debt.confidence,
                        confirmed=False,
                        reason=debt.reason,
                    )
                    if debt.annual_interest_rate is not None
                    else None
                ),
                remaining_months=(
                    DraftFieldValue(
                        value=debt.remaining_months,
                        source=debt_value_source,
                        confidence=debt.confidence,
                        confirmed=debt_value_source == ProfileValueSource.user_provided,
                        reason=debt.reason,
                    )
                    if debt.remaining_months is not None
                    else None
                ),
            )
        )
    if any(item.debt_type.value != "none" for item in result.debts):
        _refresh_debt_total(updated, changed)

    for plan in result.future_plans:
        if any(item.original_value == plan.source_text for item in updated.future_plans):
            continue
        amount_note = ""
        if plan.estimated_cost is not None:
            amount_note = (
                f"；預估成本 {plan.currency.value if plan.currency else ''} "
                f"{plan.estimated_cost:g}"
            )
        if plan.down_payment is not None:
            amount_note += f"；頭期款 {plan.down_payment:g}"
        if plan.financing is not None and plan.financing.is_financed:
            amount_note += "；使用貸款"
            if plan.financing.loan_amount is not None:
                amount_note += f" {plan.financing.loan_amount:g}"
            if plan.financing.loan_term_months is not None:
                amount_note += f"、{plan.financing.loan_term_months} 期"
            rate = (
                plan.financing.annual_interest_rate
                if plan.financing.annual_interest_rate is not None
                else plan.financing.interest_rate_value
            )
            if rate is not None:
                amount_note += f"、利率 {rate:g}%"
        if plan.recurring_monthly_amount is not None:
            amount_note += (
                f"；每月預算 {plan.currency.value if plan.currency else ''} "
                f"{plan.recurring_monthly_amount:g}"
            )
        updated.future_plans.append(
            DraftFieldValue(
                value=f"{plan.title}：{plan.description}{amount_note}",
                source=ProfileValueSource.ai_extracted,
                confidence=plan.confidence,
                confirmed=False,
                reason="辨識為獨立未來計畫，不列入一般每月支出",
                original_message_ref=message_ref,
                original_value=plan.source_text,
            )
        )

    for conflict in result.future_plan_conflicts:
        message = (
            f"{conflict.field} 原為 {conflict.existing_value}，"
            f"本次候選值為 {conflict.candidate_value}，請確認要採用哪一個。"
        )
        if message not in updated.conflicts:
            updated.conflicts.append(message)

    for conflict in result.conflicts:
        current = getattr(updated, conflict.field.value)
        if not current.confirmed and (
            current.source == ProfileValueSource.system_default
            or current.value in (None, 0, "")
        ):
            continue
        message = (
            f"{FIELD_LABELS[conflict.field.value]}原為 {conflict.existing_value}，"
            f"本次候選值為 {conflict.candidate_value}，請確認要採用哪一個。"
        )
        if message not in updated.conflicts:
            updated.conflicts.append(message)

    total = float(updated.total_variable_expenses.value or 0)
    if total > 0 and not updated.variable_expense_allocation:
        updated.variable_expense_allocation = _propose_allocation(total)

    updated.audit_trail.append({
        "version": updated.version,
        "action": "ai_structured_extraction",
        "message_ref": message_ref,
        "changed_fields": changed,
        "ambiguous": bool(result.ambiguities),
        "ambiguities": [item.message for item in result.ambiguities],
        "timestamp": updated.updated_at,
    })
    return validate_draft(updated)


def validate_draft(draft: FinancialProfileDraft) -> FinancialProfileDraft:
    draft.validation_errors = []
    draft.missing_required = [
        FIELD_LABELS[name] for name in REQUIRED_FIELDS if getattr(draft, name).value is None
    ]
    if draft.pending_total_expense is not None:
        draft.validation_errors.append("每月總支出尚未拆分為固定與變動支出。")
    numeric_fields = (
        "cash_and_deposits",
        "investments",
        "other_assets",
        "monthly_salary",
        "other_recurring_income",
        "fixed_expenses",
        "total_variable_expenses",
        "monthly_debt_payments",
        "emergency_fund",
    )
    for name in numeric_fields:
        value = getattr(draft, name).value
        if value is not None and (not isinstance(value, (int, float, Decimal)) or value < 0):
            draft.validation_errors.append(f"{FIELD_LABELS[name]}必須是大於或等於 0 的金額。")

    total = float(draft.total_variable_expenses.value or 0)
    allocated = round(sum(item.amount for item in draft.variable_expense_allocation), 2)
    if draft.variable_expense_allocation and abs(total - allocated) > 0.01:
        draft.validation_errors.append(
            f"變動支出分類合計為 NT${allocated:,.0f}，必須與總額 NT${total:,.0f} 相同。"
        )
    unresolved_debts = _unresolved_debts(draft)
    for debt in unresolved_debts:
        draft.validation_errors.append(f"{debt.name}每月付款尚未提供。")
    debt_total = sum(float(item.monthly_payment.value or 0) for item in draft.debts)
    declared = float(draft.monthly_debt_payments.value or 0)
    if draft.debts and not unresolved_debts and abs(debt_total - declared) > 0.01:
        draft.validation_errors.append("債務明細的每月付款合計與每月債務付款不一致。")

    if draft.conflicts:
        draft.validation_errors.extend(draft.conflicts)
    draft.status = "review" if not draft.missing_required else "collecting"
    return draft


def next_questions(draft: FinancialProfileDraft) -> List[str]:
    if draft.conflicts:
        return [
            f"{draft.conflicts[-1]} 請回覆要採用哪個數字。"
        ]
    if draft.pending_total_expense is not None:
        total = float(draft.pending_total_expense.value or 0)
        if draft.pending_total_expense_kind == "combined":
            return ["其中房租、保險等固定支出大約多少？"]
        return [
            f"你提到每月開銷約 NT${total:,.0f}，這是只有固定支出，還是固定與變動支出的合計？"
        ]
    if draft.audit_trail and draft.audit_trail[-1].get("ambiguous"):
        question = next(
            (item for item in INTERVIEW_QUESTIONS if _needs_interview_answer(getattr(draft, item["field"]))),
            None,
        )
        if question:
            return [f"請提供大約金額或範圍：{question['question']}"]
    for item in INTERVIEW_QUESTIONS:
        if _needs_interview_answer(getattr(draft, item["field"])):
            return [item["question"]]
    unresolved = _unresolved_debts(draft)
    if unresolved:
        return [f"{unresolved[0].name}目前每月大約繳多少？"]
    return []


def _needs_interview_answer(field: DraftFieldValue) -> bool:
    return field.value is None or (
        field.source == ProfileValueSource.system_default and not field.confirmed
    )


def interview_progress(draft: FinancialProfileDraft) -> Dict[str, Any]:
    for index, item in enumerate(INTERVIEW_QUESTIONS, start=1):
        if _needs_interview_answer(getattr(draft, item["field"])):
            return {
                "current_step": index,
                "total_steps": len(INTERVIEW_QUESTIONS),
                "stage_label": item["stage"],
            }
    if _unresolved_debts(draft):
        return {
            "current_step": len(INTERVIEW_QUESTIONS),
            "total_steps": len(INTERVIEW_QUESTIONS),
            "stage_label": "債務付款",
        }
    return {
        "current_step": len(INTERVIEW_QUESTIONS),
        "total_steps": len(INTERVIEW_QUESTIONS),
        "stage_label": "完成審核",
    }


def assistant_reply(draft: FinancialProfileDraft) -> str:
    questions = next_questions(draft)
    if questions:
        return questions[0]
    return "資料已整理完成，請檢查並確認草稿。"


def update_draft(candidate: FinancialProfileDraft, previous: FinancialProfileDraft) -> FinancialProfileDraft:
    updated = deepcopy(candidate)
    updated.conflicts = []
    updated.validation_errors = []
    updated = validate_draft(updated)
    updated.id = previous.id
    updated.version = previous.version + 1
    updated.created_at = previous.created_at
    updated.updated_at = _now()
    updated.status = "review" if not updated.missing_required else "collecting"
    updated.audit_trail = previous.audit_trail + [{
        "version": updated.version,
        "action": "user_update",
        "timestamp": updated.updated_at,
    }]
    return updated


def confirm_draft(draft: FinancialProfileDraft) -> Tuple[FinancialProfileDraft, Dict[str, Any]]:
    validated = validate_draft(deepcopy(draft))
    if validated.missing_required or validated.validation_errors:
        raise ValueError("草稿仍有缺漏或驗證錯誤，請修正後再確認。")
    required_values = [getattr(validated, name) for name in REQUIRED_FIELDS]
    if any(not item.confirmed for item in required_values):
        raise ValueError("必要欄位仍有未確認項目。")
    if any(not item.confirmed for item in validated.variable_expense_allocation):
        raise ValueError("變動支出分配仍未全部確認。")

    validated.status = "confirmed"
    validated.confirmed_at = _now()
    validated.updated_at = validated.confirmed_at
    validated.audit_trail.append({
        "version": validated.version,
        "action": "explicit_confirmation",
        "timestamp": validated.confirmed_at,
    })
    categories = [
        {
            "category": item.category,
            "baseline": item.amount,
            "monthly_volatility": 0,
            "annual_inflation_rate": 0.02,
            "income_elasticity": 0,
            "seasonal_factors": [1.0] * 12,
            "enabled": True,
        }
        for item in validated.variable_expense_allocation
    ]
    profile = {
        "salary": float(validated.monthly_salary.value or 0)
        + float(validated.other_recurring_income.value or 0),
        "fixed_expense": float(validated.fixed_expenses.value or 0),
        "variable_expense": float(validated.total_variable_expenses.value or 0),
        "balance": float(validated.cash_and_deposits.value or 0)
        + float(validated.investments.value or 0)
        + float(validated.other_assets.value or 0),
        "raise_rate": 0.03,
        "inflation_rate": 0.02,
        "target_emergency_months": 3,
        "variable_expense_model": {
            "mode": "advanced" if categories else "quick",
            "total_variable_expense": float(validated.total_variable_expenses.value or 0),
            "categories": categories,
        },
    }
    return validated, profile


def provider_available() -> bool:
    return settings.ai_enabled and bool(settings.ai_api_key)
