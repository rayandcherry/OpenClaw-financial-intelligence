import pytest
from src.core.stats import wilson_score_interval, wilson_lower_bound


def test_zero_total_returns_zero_zero():
    assert wilson_score_interval(0, 0) == (0.0, 0.0)
    assert wilson_lower_bound(0, 0) == 0.0


def test_zero_wins_lb_is_zero_ub_below_100():
    low, high = wilson_score_interval(0, 10)
    assert low == 0.0
    assert 0.0 < high < 100.0


def test_all_wins_lb_above_zero_ub_is_100():
    low, high = wilson_score_interval(10, 10)
    assert 0.0 < low < 100.0
    assert high == 100.0


def test_csco_like_18_of_24_lb_around_55():
    """CSCO Donchian sample: 18/24 = 75% raw. Wilson 95% LB should be ~55%."""
    low, high = wilson_score_interval(18, 24)
    assert 53.0 <= low <= 57.0
    assert 87.0 <= high <= 90.0


def test_wmb_like_23_of_25_lb_around_75():
    """WMB Donchian: 23/25 = 92%. Wilson LB ~75%."""
    low, _ = wilson_score_interval(23, 25)
    assert 73.0 <= low <= 77.0


def test_small_sample_penalized_more_than_large():
    """Same WR, smaller sample → wider CI, lower LB."""
    small_lb = wilson_lower_bound(15, 20)   # 75% on 20
    large_lb = wilson_lower_bound(75, 100)  # 75% on 100
    assert large_lb > small_lb
    assert large_lb - small_lb > 5  # at least 5pp gap


def test_half_split_centers_around_50():
    low, high = wilson_score_interval(50, 100)
    assert 39.0 <= low <= 41.0
    assert 59.0 <= high <= 61.0


def test_lb_monotonic_with_wins_at_fixed_n():
    n = 20
    lbs = [wilson_lower_bound(w, n) for w in range(0, n + 1)]
    assert lbs == sorted(lbs)
