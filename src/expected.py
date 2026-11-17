"""Context baselines: what an *average* player does in the same situation.

Comparing raw strike rates is unfair (death overs inflate scoring, T20Is vs
Associates inflate it further). Each delivery therefore gets an expected
outcome from a hierarchical cell model:

    competition x innings x over x wickets-lost bucket x pressure category
        -> shrunk toward competition x innings x over x wickets bucket
        -> shrunk toward competition x over

then an opposition-strength adjustment (shrunk mean residual of the opposing
team). Player value = actual - expected, so it is measured against
comparable situations and opposition.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

K_CELL = 100       # pseudo-balls pulling a sparse cell toward its parent
K_TEAM = 600       # pseudo-balls for opposition effects


def _wkt_bucket(w: pd.Series) -> pd.Series:
    return pd.cut(w, [-1, 1, 3, 5, 10], labels=["0-1", "2-3", "4-5", "6+"]).astype(str)


def _hier_mean(df: pd.DataFrame, y: str, levels: list[list[str]]) -> pd.Series:
    """Expected y from nested groupings; each level shrinks toward the previous."""
    est = pd.Series(df[y].mean(), index=df.index)
    for keys in levels:
        g = df.groupby(keys, observed=True)[y]
        s, n = g.transform("sum"), g.transform("size")
        est = (s + K_CELL * est) / (n + K_CELL)
    return est


def _opp_adjust(df: pd.DataFrame, y: str, exp: pd.Series, team_col: str) -> pd.Series:
    resid = df[y] - exp
    g = resid.groupby(df[team_col])
    eff = g.transform("sum") / (g.transform("size") + K_TEAM)
    return exp + eff


def add_expected(d: pd.DataFrame, pcat_bat: str = "pcat_bat", pcat_bowl: str = "pcat_bowl") -> pd.DataFrame:
    d = d.copy()
    d["wkt_bucket"] = _wkt_bucket(d["wkts_before"])
    base = [["competition", "over_no"], ["competition", "innings", "over_no", "wkt_bucket"]]

    # batting view: per ball faced
    bf = d[d["ball_faced"]].copy()
    bf["y_out"] = bf["striker_out"].astype(float)
    for y, col in (("bat_runs", "exp_bat_runs"), ("y_out", "exp_bat_out")):
        e = _hier_mean(bf, y, base + [base[-1] + [pcat_bat]])
        bf[col] = _opp_adjust(bf, y, e, "bowling_team_id")
    d["exp_bat_runs"] = bf["exp_bat_runs"]
    d["exp_bat_out"] = bf["exp_bat_out"]

    # bowling view: per delivery (wides/no-balls are the bowler's responsibility)
    bw = d.copy()
    bw["y_wkt"] = bw["bowler_wicket"].astype(float)
    for y, col in (("bowler_runs", "exp_bowl_runs"), ("y_wkt", "exp_bowl_wkt")):
        e = _hier_mean(bw, y, base + [base[-1] + [pcat_bowl]])
        bw[col] = _opp_adjust(bw, y, e, "batting_team_id")
    d["exp_bowl_runs"] = bw["exp_bowl_runs"]
    d["exp_bowl_wkt"] = bw["exp_bowl_wkt"]
    return d


def wicket_run_value(d: pd.DataFrame) -> float:
    """Runs-equivalent of a wicket, estimated from win-probability impact.

    Regress WPA on batter runs and wicket indicator; lambda = beta_wkt / beta_run
    converts a dismissal into the number of runs with the same effect on winning.
    """
    s = d[d["ball_faced"] & d["wpa"].notna()]
    X = np.column_stack([np.ones(len(s)), s["bat_runs"], s["team_wicket"].astype(float)])
    beta, *_ = np.linalg.lstsq(X, s["wpa"].values, rcond=None)
    return float(-beta[2] / beta[1])
