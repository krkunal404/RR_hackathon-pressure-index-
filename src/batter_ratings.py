"""Batter Pressure Performance Index (BPPI) and batting descriptives."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .rating_engine import RoleSpec, rate


def batter_spec(d: pd.DataFrame, weights: dict | None = None, pressure_col: str = "pressure_bat") -> RoleSpec:
    return RoleSpec(
        role="bat", player_col="striker_id", name_col="striker_name",
        rows=d["ball_faced"], count_col="ball_faced", pressure_col=pressure_col,
        v_score=d["bat_runs"] - d["exp_bat_runs"],
        v_surv=d["exp_bat_out"] - d["striker_out"].astype(float),
        v_impact=d["wpa"],
        comp_names=("scoring", "survival", "impact", "uplift", "consistency"),
        weights=weights or C.BPPI_WEIGHTS, min_balls=C.MIN_PRESSURE_BALLS_BAT,
    )


def _bat_stats(x: pd.DataFrame, prefix: str) -> pd.DataFrame:
    g = x.groupby("striker_id")
    balls = g["ball_faced"].sum()
    runs = g["bat_runs"].sum()
    outs = g["striker_out"].sum()
    out = pd.DataFrame({
        f"{prefix}balls": balls, f"{prefix}runs": runs, f"{prefix}outs": outs,
        f"{prefix}sr": 100 * runs / balls.replace(0, np.nan),
        f"{prefix}avg": runs / outs.replace(0, np.nan),
        f"{prefix}boundary_pct": 100 * g["is_boundary"].sum() / balls.replace(0, np.nan),
        f"{prefix}dot_pct": 100 * g["is_dot_bat"].sum() / balls.replace(0, np.nan),
        f"{prefix}dismissal_rate": 100 * outs / balls.replace(0, np.nan),
        f"{prefix}exp_sr": 100 * g["exp_bat_runs"].sum() / balls.replace(0, np.nan),
    })
    return out


def batter_descriptives(d: pd.DataFrame, pressure_col: str = "pressure_bat",
                        thr: float = C.PRESSURE_THRESHOLD) -> pd.DataFrame:
    bf = d[d["ball_faced"]]
    p = bf[pressure_col] >= thr
    out = _bat_stats(bf, "all_").join(_bat_stats(bf[p], "p_")).join(_bat_stats(bf[~p], "n_"))
    ctx = {
        "death_": bf[p & bf["phase"].eq("Death")],
        "chase_won_": bf[p & bf["successful_chase"]],
        "close_": bf[p & bf["close_match"]],
        "extreme_": bf[bf["pcat_bat"].eq("Extreme")],
    }
    for k, x in ctx.items():
        out = out.join(_bat_stats(x, k)[[f"{k}balls", f"{k}runs", f"{k}sr", f"{k}outs"]])
    # non-striker run-outs count against the batter's average
    ns = d[d["nonstriker_out"]].groupby("non_striker_id").size()
    out["all_outs_incl_nonstriker"] = out["all_outs"].add(ns.reindex(out.index).fillna(0))
    out["p_sr_vs_expected"] = out["p_sr"] - out["p_exp_sr"]
    out["n_sr_vs_expected"] = out["n_sr"] - out["n_exp_sr"]
    out["sr_change"] = out["p_sr"] - out["n_sr"]
    return out


def rate_batters(d: pd.DataFrame, lam: float, weights: dict | None = None, thr: float = C.PRESSURE_THRESHOLD,
                 bootstrap: bool = True, pressure_col: str = "pressure_bat", min_balls: int | None = None,
                 min_matches: int | None = None) -> tuple[pd.DataFrame, dict]:
    spec = batter_spec(d, weights, pressure_col)
    if min_balls is not None:
        spec.min_balls = min_balls
    pl, meta = rate(d, spec, lam, thr, bootstrap,
                    min_matches=C.MIN_PRESSURE_MATCHES if min_matches is None else min_matches)
    desc = batter_descriptives(d, pressure_col, thr)
    pl = pl.merge(desc, left_on="player_id", right_index=True, how="left")
    pl = pl.rename(columns={"rating": "BPPI", "rating_lo": "BPPI_lo", "rating_hi": "BPPI_hi"})
    return pl, meta
