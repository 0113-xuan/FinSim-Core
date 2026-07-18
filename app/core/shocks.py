from __future__ import annotations

import random
from typing import Any, Dict, List, Optional


def generate_shocks_for_month(
    *,
    month: int,
    random_shocks: List[Dict[str, Any]],
    rng: random.Random,
    include_details: bool = False,
) -> Dict[str, Any]:
    total = 0.0
    details = []
    for shock in random_shocks:
        if not shock.get("enabled", True):
            continue
        if rng.random() > float(shock["monthly_probability"]):
            continue
        if shock.get("distribution") == "normal":
            mean = (float(shock["min_amount"]) + float(shock["max_amount"])) / 2
            stdev = max(1.0, (float(shock["max_amount"]) - float(shock["min_amount"])) / 6)
            amount = min(float(shock["max_amount"]), max(float(shock["min_amount"]), rng.normalvariate(mean, stdev)))
        else:
            amount = rng.uniform(float(shock["min_amount"]), float(shock["max_amount"]))
        amount = round(amount, 2)
        total += amount
        if include_details:
            details.append(
                {
                    "month": month,
                    "name": shock["name"],
                    "target_category": shock.get("target_category"),
                    "amount": amount,
                    "duration_months": int(shock.get("duration_months", 1)),
                }
            )
    return {"total": round(total, 2), "details": details}
