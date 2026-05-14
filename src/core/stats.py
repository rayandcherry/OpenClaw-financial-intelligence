"""Wilson score confidence intervals for binomial proportions.

Used to honest-up per-ticker win rates with small sample sizes — a raw WR of
75% from 24 trades has a 95% lower bound around 55%, which prevents
small-sample lucky streaks from inflating signal quality scores.
"""
from __future__ import annotations

import math


def wilson_score_interval(wins: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Return Wilson score 95% CI as (low_pct, high_pct) on [0, 100].

    Falls back to (0, 0) when total <= 0. Otherwise the bounds are clamped
    to [0, 100] (Wilson can overshoot under floating-point error at the
    extremes wins==0 / wins==total).
    """
    if total <= 0:
        return (0.0, 0.0)
    p = wins / total
    z2 = z * z
    denom = 1.0 + z2 / total
    center = (p + z2 / (2 * total)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / total + z2 / (4 * total * total))
    low = max(0.0, center - half) * 100.0
    high = min(1.0, center + half) * 100.0
    return (round(low, 1), round(high, 1))


def wilson_lower_bound(wins: int, total: int, z: float = 1.96) -> float:
    """Convenience: just the lower bound. Mirrors wilson_score_interval[0]."""
    return wilson_score_interval(wins, total, z)[0]
