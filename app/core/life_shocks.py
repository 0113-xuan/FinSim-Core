# 示範假設，不是統計。
LIFE_SHOCKS = (
    dict(id="medical", label="重大醫療支出", kind="expense", monthly_probability=0.005, min_amount=50000, max_amount=300000, duration_months=1, income_multiplier=None),
    dict(id="accident", label="車禍與車損自付", kind="expense", monthly_probability=0.004, min_amount=20000, max_amount=150000, duration_months=1, income_multiplier=None),
    dict(id="income_gap", label="收入中斷", kind="income_gap", monthly_probability=0.004, min_amount=0, max_amount=0, duration_months=6, income_multiplier=0),
)

DISCLAIMER = "機率與金額是示範假設，不是統計或預測；只用來看這份計畫撐不撐得住意外。"
