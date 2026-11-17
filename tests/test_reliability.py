"""Shrinkage and reliability maths on synthetic data with known answers."""
import numpy as np
import pandas as pd

from src.reliability import beta_shrink, cluster_bootstrap, estimate_beta_strength, estimate_k, reliability_score, shrink, to_index


def test_shrink_moves_small_samples_more():
    small = shrink(10.0, 10, k=100)
    big = shrink(1000.0, 1000, k=100)
    assert small < big and np.isclose(big, 1000 / 1100)
    assert shrink(5.0, 0, k=50, prior=0.2) == (5 + 50 * 0.2) / 50


def test_estimate_k_recovers_true_spread():
    rng = np.random.default_rng(0)
    n_players, n = 400, 400
    tau, sigma = 0.1, 1.0
    talent = rng.normal(0, tau, n_players)
    sums = pd.Series([rng.normal(t, sigma, n).sum() for t in talent])
    k = estimate_k(sums, pd.Series([float(n)] * n_players), sigma ** 2)
    assert 50 < k < 200          # true k = sigma^2 / tau^2 = 100


def test_estimate_k_caps_pure_noise():
    rng = np.random.default_rng(1)
    sums = pd.Series([rng.normal(0, 1, 300).sum() for _ in range(300)])
    assert estimate_k(sums, pd.Series([300.0] * 300), 1.0, k_max=3000) >= 1000


def test_beta_strength_and_shrink():
    rng = np.random.default_rng(2)
    p = rng.beta(30, 30, 500)
    trials = pd.Series(rng.integers(10, 40, 500)).astype(float)
    succ = pd.Series(rng.binomial(trials.astype(int), p)).astype(float)
    s = estimate_beta_strength(succ, trials)
    assert 20 < s < 200
    assert beta_shrink(10, 10, 0.5, strength=10) == 0.75


def test_index_and_reliability_ranges():
    assert list(to_index([0, 5, 10, 20], 0, 10)) == [0, 50, 100, 100]
    r = reliability_score([0, 100, 10000], k=100, matches=[0, 25, 100])
    assert r[0] == 0 and np.isclose(r[1], 50) and r[2] < 100


def test_cluster_bootstrap_shape():
    M = np.arange(20, dtype=float).reshape(10, 2)
    out = cluster_bootstrap(M, lambda T: T[:, 0] / T[:, 1].clip(1), 50, np.random.default_rng(0))
    assert out.shape == (50,)
