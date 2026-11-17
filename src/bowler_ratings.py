"""Bowler Pressure Performance Index (BoPPI) and bowling descriptives.

Accounting rules (validated in the data audit):
* Bowler runs = batter runs + wides + no-balls. Byes, leg-byes and penalty runs
  are NOT charged to the bowler.
* Legal balls exclude wides and no-balls; economy = bowler runs per 6 legal balls.
* Bowler wickets = caught, bowled, LBW, stumped, hit wicket (run outs, retired
  out and obstructing the field are not credited to the bowler).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .rating_engine import RoleSpec, rate


def bowler_spec(d: pd.DataFrame, weights: dict | None = None, pressure_col: str = "pressure_bowl") -> RoleSpec:
    every = pd.Series(True, index=d.index)
    return RoleSpec(
        role="bowl", player_col="bowler_id", name_col="bowler_name",
        rows=every, count_col="is_legal", pressure_col=pressure_col,
        v_score=d["exp_bowl_runs"] - d["bowler_runs"],
        v_surv=d["bowler_wicket"].astype(float) - d["exp_bowl_wkt"],
        v_impact=-d["wpa"],
        comp_names=("economy", "wickets", "impact", "uplift", "consistency"),
        weights=weights or C.BOPPI_WEIGHTS, min_balls=C.MIN_PRESSURE_BALLS_BOWL,
    )


def _bowl_stats(x: pd.DataFrame, prefix: str) -> pd.DataFrame:
    g = x.groupby("bowler_id")
    legal = g["is_legal"].sum()
    runs = g["bowler_runs"].sum()
    wk = g["bowler_wicket"].sum()
    return pd.DataFrame({
        f"{prefix}legal_balls": legal, f"{prefix}runs": runs, f"{prefix}wkts": wk,
        f"{prefix}econ": 6 * runs / legal.replace(0, np.nan),
        f"{prefix}wkts_per_over": 6 * wk / legal.replace(0, np.nan),
        f"{prefix}bowl_avg": runs / wk.replace(0, np.nan),
        f"{prefix}bowl_sr": legal / wk.replace(0, np.nan),
        f"{prefix}dot_pct": 100 * g["is_dot_bowl"].sum() / legal.replace(0, np.nan),
        f"{prefix}boundary_pct": 100 * g["is_boundary"].sum() / legal.replace(0, np.nan),
        f"{prefix}extras": g["is_wide"].sum() + g["is_noball"].sum(),
        f"{prefix}exp_econ": 6 * g["exp_bowl_runs"].sum() / legal.replace(0, np.nan),
    })


def bowler_descriptives(d: pd.DataFrame, pressure_col: str = "pressure_bowl",
                        thr: float = C.PRESSURE_THRESHOLD) -> pd.DataFrame:
    p = d[pressure_col] >= thr
    out = _bowl_stats(d, "all_").join(_bowl_stats(d[p], "p_")).join(_bowl_stats(d[~p], "n_"))
    ctx = {
        "death_": d[p & d["phase"].eq("Death")],
        "close_": d[p & d["close_match"]],
        "high_rrr_": d[d["chase"] & d["rrr"].ge(10)],
        "extreme_": d[d["pcat_bowl"].eq("Extreme")],
    }
    for k, x in ctx.items():
        out = out.join(_bowl_stats(x, k)[[f"{k}legal_balls", f"{k}runs", f"{k}econ", f"{k}wkts"]])
    out["p_econ_vs_expected"] = out["p_econ"] - out["p_exp_econ"]
    out["n_econ_vs_expected"] = out["n_econ"] - out["n_exp_econ"]
    out["econ_change"] = out["p_econ"] - out["n_econ"]
    return out


def rate_bowlers(d: pd.DataFrame, lam: float, weights: dict | None = None, thr: float = C.PRESSURE_THRESHOLD,
                 bootstrap: bool = True, pressure_col: str = "pressure_bowl", min_balls: int | None = None,
                 min_matches: int | None = None) -> tuple[pd.DataFrame, dict]:
    spec = bowler_spec(d, weights, pressure_col)
    if min_balls is not None:
        spec.min_balls = min_balls
    pl, meta = rate(d, spec, lam, thr, bootstrap,
                    min_matches=C.MIN_PRESSURE_MATCHES if min_matches is None else min_matches)
    desc = bowler_descriptives(d, pressure_col, thr)
    pl = pl.merge(desc, left_on="player_id", right_index=True, how="left")
    pl = pl.rename(columns={"rating": "BoPPI", "rating_lo": "BoPPI_lo", "rating_hi": "BoPPI_hi"})
    return pl, meta
