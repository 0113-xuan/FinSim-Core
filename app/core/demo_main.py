from app.core.simulation import simulate_finance
from app.core.monte_carlo import run_monte_carlo
from app.core.advisor import compare_options, generate_advice


def main():
    profile = {
        "salary": 25000,
        "fixed_expense": 12000,
        "variable_expense": 6000,
        "balance": 50000,
        "raise_rate": 0.03,
        "inflation_rate": 0.02,
        "target_emergency_months": 3
    }

    buy_car_now_option = {
        "name": "buy_car_now",
        "events": [],
        "loans": [
            {
                "principal": 600000,
                "apr": 0.03,
                "months": 60,
                "start_month": 1
            }
        ]
    }

    delay_buy_car_option = {
        "name": "delay_6_months",
        "events": [],
        "loans": [
            {
                "principal": 600000,
                "apr": 0.03,
                "months": 60,
                "start_month": 7
            }
        ]
    }

    used_car_option = {
        "name": "buy_used_car",
        "events": [
            {
                "type": "one_time",
                "month": 1,
                "amount": -120000,
                "note": "buy_used_car"
            }
        ],
        "loans": []
    }

    # 基本模擬
    sim_result = simulate_finance(
        profile=profile,
        months=60,
        events=[],
        loans=[]
    )
    print("=== 基本模擬 summary ===")
    print(sim_result["summary"])

    # Monte Carlo
    mc_result = run_monte_carlo(
        profile=profile,
        base_events=[],
        loans=[],
        months=60,
        simulations=300
    )
    print("\n=== Monte Carlo ===")
    print(mc_result)

    # 方案比較
    compare_result = compare_options(
        profile=profile,
        options=[buy_car_now_option, delay_buy_car_option, used_car_option],
        months=60,
        mc_runs=200
    )
    print("\n=== 比較結果 ===")
    for item in compare_result["options"]:
        print(
            item["name"],
            item["score"],
            item["simulation_summary"],
            item["monte_carlo_summary"]
        )

    advice = generate_advice(compare_result)
    print("\n=== AI 建議 ===")
    print(advice)


if __name__ == "__main__":
    main()