"""Compare block lengths and simulation counts using the regression scenarios."""
import runpy
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.core.monte_carlo import run_monte_carlo

CASES = runpy.run_path(str(ROOT / "tests/test_mc_regression.py"))["CASES"]
CASES["tight_shocks"] = dict(
    profile=dict(salary=40000, fixed_expense=18000, variable_expense=18000,
                 balance=10000, inflation_rate=.02, raise_rate=.01),
    months=12,
    random_shocks=[dict(name="維修", monthly_probability=.12, min_amount=5000,
                        max_amount=35000, distribution="uniform", duration_months=1, enabled=True)],
)
NAMES = ("simple", "investment", "car_loan", "advanced_shocks", "tight_shocks")


def run(name, count, seed, block=12):
    args = dict(CASES[name])
    args["base_events"] = args.pop("events", None)
    return run_monte_carlo(**args, simulations=count, seed=seed, block_months=block, sample_paths=0)


def change(value, base):
    return f"{(value / base - 1) * 100:+.2f}%" if base else ("0.00%" if value == 0 else "不適用")


def main():
    print("## 區塊長度敏感度（2000 次，seed=42）", flush=True)
    print("| 案例 | 月數 | 現金不足機率（95% 區間） | p5 | p50 | p95 | 相對 12 個月差異（機率 / p5 / p50 / p95） |", flush=True)
    print("| --- | ---: | ---: | ---: | ---: | ---: | --- |", flush=True)
    for name in NAMES:
        results = {block: run(name, 2000, 42, block) for block in (6, 12, 24)}
        base = results[12]
        for block, result in results.items():
            p = result["probability_cash_shortfall"]
            interval = result["probability_cash_shortfall_interval"]
            values = result["net_worth_percentiles"]
            diffs = [change(p, base["probability_cash_shortfall"])] + [change(values[k], base["net_worth_percentiles"][k]) for k in ("p5", "p50", "p95")]
            print(f"| {name} | {block} | {p:.4f} [{interval['low']:.4f}, {interval['high']:.4f}] | {values['p5']:.2f} | {values['p50']:.2f} | {values['p95']:.2f} | {' / '.join(diffs)} |", flush=True)
    print("\n## 收斂（8 個種子：0–7）", flush=True)
    print("| 案例 | 次數 | 現金不足機率平均 | 標準差 | 淨資產 p50 平均 | 標準差 |", flush=True)
    print("| --- | ---: | ---: | ---: | ---: | ---: |", flush=True)
    for name in NAMES:
        for count in (500, 2000):
            results = [run(name, count, seed) for seed in range(8)]
            probs = [r["probability_cash_shortfall"] for r in results]
            medians = [r["net_worth_percentiles"]["p50"] for r in results]
            print(f"| {name} | {count} | {statistics.mean(probs):.4f} | {statistics.stdev(probs):.4f} | {statistics.mean(medians):.2f} | {statistics.stdev(medians):.2f} |", flush=True)


if __name__ == "__main__":
    main()
