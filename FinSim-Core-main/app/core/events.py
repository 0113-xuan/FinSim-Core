from typing import List, Dict, Any


def calculate_loan_payment(principal: float, apr: float, months: int) -> float:
    """
    等額本息月付金公式

    參數：
    - principal: 本金
    - apr: 年利率，例如 0.03
    - months: 期數

    若 apr <= 0，則退化為平均分攤本金。
    """
    if months <= 0:
        raise ValueError("months must be > 0")

    if principal < 0:
        raise ValueError("principal must be >= 0")

    if apr <= 0:
        return round(principal / months, 2)

    monthly_rate = apr / 12
    payment = (
        principal
        * monthly_rate
        * (1 + monthly_rate) ** months
        / ((1 + monthly_rate) ** months - 1)
    )
    return round(payment, 2)


def get_monthly_event_net(month: int, events: List[Dict[str, Any]]) -> float:
    """
    回傳某月事件造成的淨現金流影響
    正值 = 額外收入
    負值 = 額外支出

    支援事件型別：
    - one_time:
        {
            "type": "one_time",
            "month": 3,
            "amount": -20000
        }

    - range:
        {
            "type": "range",
            "start_month": 3,
            "end_month": 8,
            "amount": -5000
        }

    - salary_change:
        不直接列入 event net，由 salary 邏輯處理
    """
    total = 0.0

    for event in events:
        event_type = event.get("type")

        if event_type == "one_time":
            if event.get("month") == month:
                total += float(event.get("amount", 0))

        elif event_type == "range":
            start_month = event.get("start_month")
            end_month = event.get("end_month")
            if start_month is not None and end_month is not None:
                if start_month <= month <= end_month:
                    total += float(event.get("amount", 0))

    return round(total, 2)


def get_salary_for_month(month: int, base_salary: float, salary_events: List[Dict[str, Any]]) -> float:
    """
    取得某月薪資，若有 salary_change 事件則覆蓋
    取最後一個符合條件的 salary_change

    salary_change 格式：
    {
        "type": "salary_change",
        "start_month": 7,
        "new_salary": 32000
    }
    """
    salary = float(base_salary)

    applicable = [
        e for e in salary_events
        if e.get("type") == "salary_change"
        and e.get("start_month") is not None
        and e["start_month"] <= month
    ]

    if applicable:
        applicable.sort(key=lambda x: x["start_month"])
        salary = float(applicable[-1]["new_salary"])

    return round(salary, 2)


def get_debt_payment_for_month(month: int, loans: List[Dict[str, Any]]) -> float:
    """
    計算某月所有貸款總月付金

    loan 格式：
    {
        "principal": 600000,
        "apr": 0.03,
        "months": 60,
        "start_month": 1
    }
    """
    total = 0.0

    for loan in loans:
        start_month = int(loan["start_month"])
        loan_months = int(loan["months"])
        end_month = start_month + loan_months - 1

        if start_month <= month <= end_month:
            total += calculate_loan_payment(
                principal=float(loan["principal"]),
                apr=float(loan["apr"]),
                months=loan_months
            )

    return round(total, 2)