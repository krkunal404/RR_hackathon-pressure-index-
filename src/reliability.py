"""Statistical reliability toolkit shared by batter and bowler ratings.

* Empirical-Bayes shrinkage of per-ball rates toward the population mean,
  with the prior strength k estimated by the method of moments.
* Beta-binomial shrinkage for match-level consistency.
* Cluster (match-level) bootstrap for rating confidence intervals.
* A reliability score that is reported *separately* from performance.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def estimate_k(sums: pd.Series, n: pd.Series, ball_var: float, min_n: float = 100,
               k_max: float = 3000.0) -> float:
    """Prior strength k = sigma^2_within / tau^2_between (weighted method of moments).

    tau^2 = weighted Var(player means) - sigma^2 * (#players / total balls).
    If tau^2 is not distinguishable from zero the metric is mostly noise and
    k is capped at k_max (very strong shrinkage).
    """
    m = n >= min_n
    means, w = sums[m] / n[m], n[m]
    wm = np.average(means, weights=w)
    tau2 = np.average((means - wm) ** 2, weights=w) - ball_var * m.sum() / w.sum()
    if tau2 <= 0:
        return k_max
    return float(min(ball_var / tau2, k_max))


def shrink(sums, n, k, prior=0.0):
    """Posterior mean of a per-ball rate: (sum + k*prior) / (n + k)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        return (np.asarray(sums, float) + k * prior) / (np.asarray(n, float) + k)


def estimate_beta_strength(successes: pd.Series, trials: pd.Series, min_trials: int = 10,
                           s_max: float = 200.0) -> float:
    """Beta-binomial prior strength (alpha+beta) by method of moments."""
    m = trials >= min_trials
    p_i, n_i = successes[m] / trials[m], trials[m]
    p = successes[m].sum() / n_i.sum()
    tau2 = p_i.var() - np.mean(p * (1 - p) / n_i)
    if tau2 <= 0:
        return s_max
    return float(min(p * (1 - p) / tau2 - 1, s_max))


def beta_shrink(successes, trials, prior_p, strength=6.0):
    with np.errstate(invalid="ignore", divide="ignore"):
        return (np.asarray(successes, float) + strength * prior_p) / (np.asarray(trials, float) + strength)


def to_index(z, lo: float, hi: float):
    """Min-max map of the composite onto 0-100 over the eligible pool.

    0 = weakest eligible player, 100 = strongest; spacing between players is
    preserved (a normal-CDF map saturates and hides gaps at the top).
    """
    return np.clip(100 * (np.asarray(z, float) - lo) / (hi - lo), 0, 100)


def reliability_score(n_balls, k, matches, full_matches: int = 25) -> np.ndarray:
    """0-100: share of observed signal the shrinkage trusts x match-coverage factor.

    This measures how *certain* a rating is, not how *good* the player is.
    """
    n_balls = np.asarray(n_balls, float)
    trust = n_balls / (n_balls + k)
    coverage = np.sqrt(np.clip(np.asarray(matches, float) / full_matches, 0, 1))
    return 100 * trust * coverage


def cluster_bootstrap(M: np.ndarray, scorer, reps: int, rng: np.random.Generator) -> np.ndarray:
    """Resample a player's matches (rows of M, per-match sums) with replacement.

    scorer maps a (reps, n_cols) array of resampled column totals to ratings.
    Returns the bootstrap distribution of the rating.
    """
    n = M.shape[0]
    idx = rng.integers(0, n, size=(reps, n))
    return scorer(M[idx].sum(axis=1))
