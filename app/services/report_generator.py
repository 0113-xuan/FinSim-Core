from __future__ import annotations

from typing import Any, Dict


def generate_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    simulation = payload.get("simulation_result", {})
    summary = simulation.get("summary", {})
    monte_carlo = payload.get("monte_carlo_result") or {}
    sections = [
        {
            "title": "目前財務狀況",
            "body": f"第 60 月預估資產為 {summary.get('final_balance', 'N/A')}，期間最低資產為 {summary.get('min_balance', 'N/A')}。",
        },
        {
            "title": "主要風險因素",
            "body": f"最高 FSI 為 {summary.get('max_fsi', 'N/A')}；Monte Carlo 破產機率為 {monte_carlo.get('bankrupt_probability', 'N/A')}。",
        },
        {
            "title": "可行改善",
            "body": "優先檢查固定支出、貸款付款與高波動支出類別，並保留足夠緊急備用金。",
        },
        {
            "title": "限制與聲明",
            "body": "本報告只根據後端模擬資料產生，不構成受監管的投資或財務建議。",
        },
    ]
    return {"title": "FinSim Core 財務風險報告", "sections": sections, "traceable_metrics": summary}
