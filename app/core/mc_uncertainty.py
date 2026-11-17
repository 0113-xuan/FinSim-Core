import math


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0 or not 0 <= successes <= n:
        raise ValueError("successes must be between 0 and a positive n")
    p = successes / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def quantile_interval(values: list[float], q: float, z: float = 1.96) -> tuple[float, float]:
    if not values or not 0 <= q <= 1:
        raise ValueError("values must be nonempty and q must be between 0 and 1")
    ordered = sorted(values)
    n = len(ordered)
    margin = z * math.sqrt(n * q * (1 - q))
    j = max(0, min(n - 1, math.floor(n * q - margin)))
    k = max(0, min(n - 1, math.ceil(n * q + margin)))
    return ordered[j], ordered[k]
