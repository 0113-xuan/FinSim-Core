"""Measure the same 2,000-run plan with three repetitions per horizon."""
import argparse
import statistics
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.monte_carlo import run_monte_carlo

PROFILE = {'salary': 60000, 'fixed_expense': 20000, 'variable_expense': 12000,
           'balance': 900000, 'inflation_rate': .02, 'raise_rate': .03}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--months', nargs='+', type=int, default=[60, 120, 240])
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    for months in args.months:
        times = []
        for _ in range(args.repeats):
            start = perf_counter()
            run_monte_carlo(PROFILE, months=months, simulations=2000, seed=42)
            times.append(perf_counter() - start)
            print(f'{months} months: {times[-1]:.3f} s', flush=True)
        print(f'{months} months median: {statistics.median(times):.3f} s', flush=True)


if __name__ == '__main__':
    main()
