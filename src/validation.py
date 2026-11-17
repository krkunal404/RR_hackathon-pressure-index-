"""Independent checks, temporal stability and ranking-sensitivity analysis."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from . import config as C
from .batter_ratings import rate_batters
from .bowler_ratings import rate_bowlers
from .expected import add_expected
from .pressure_model import compute_pressure


# ----------------------------------------------------------------- data checks
def accounting_checks(d: pd.DataFrame, m: pd.DataFrame) -> dict:
    out = {}
    inn = d.groupby(["match_id", "innings"])["total_runs"].sum().unstack()
    mm = m.set_index("match_id").join(inn)
    x = mm[mm["margin_runs"].notna() & ~mm["is_dls"] & mm[1].notna() & mm[2].notna()]
    err = (x[1] - x[2]) - x["margin_runs"]
    out["margin_reconstruction"] = {
        "matches": int(len(x)), "exact": float((err == 0).mean()), "within_3": float((err.abs() <= 3).mean()),
        "within_7": float((err.abs() <= 7).mean()), "mean_error": float(err.mean()), "median_abs_error": float(err.abs().median()),
    }
    legal_per_over = d[d["is_legal"]].groupby(["match_id", "innings", "overid"]).size()
    out["overs_with_more_than_6_legal"] = int((legal_per_over > 6).sum())
    out["overs_total"] = int(len(legal_per_over))
    out["share_overs_exactly_6_legal"] = float((legal_per_over == 6).mean())
    out["wides_counted_as_ball_faced"] = int((d["is_wide"] & d["ball_faced"]).sum())
    out["illegal_counted_legal"] = int((d["extras_type"].isin(C.ILLEGAL_EXTRAS) & d["is_legal"]).sum())
    out["byes_charged_to_bowler"] = int((d["extras_type"].isin(C.BYE_EXTRAS) & (d["bowler_runs"] > d["bat_runs"])).sum())
    out["runouts_credited_to_bowler"] = int((d["dismissal_type"].eq("RunOut") & d["bowler_wicket"]).sum())
    out["bowler_wkts_not_team_wkts"] = int((d["bowler_wicket"] & ~d["team_wicket"]).sum())
    out["wickets_per_innings_max"] = int(d.groupby(["match_id", "innings"])["team_wicket"].sum().max())
    # leakage: pre-ball state must equal cumulative totals of strictly earlier balls
    g = d.groupby(["match_id", "innings"], sort=False)
    out["leakage_runs_before_mismatch"] = int((g["total_runs"].transform(lambda s: s.shift(1, fill_value=0).cumsum()) != d["runs_before"]).sum())
    out["leakage_wkts_before_mismatch"] = int((g["team_wicket"].transform(lambda s: s.astype(int).shift(1, fill_value=0).cumsum()) != d["wkts_before"]).sum())
    out["deliveries"] = int(len(d))
    out["matches"] = int(d["match_id"].nunique())
    return out


def pressure_face_validity(d: pd.DataFrame) -> dict:
    """Does the score behave like pressure? Outcomes and context by category."""
    cat = d.groupby("pcat_bat").agg(
        deliveries=("match_id", "size"), runs_per_ball=("bat_runs", "mean"), wicket_rate=("team_wicket", "mean"),
        dot_rate=("is_dot_bat", "mean"), boundary_rate=("is_boundary", "mean"), mean_leverage=("leverage", "mean"),
        close_match_share=("close_match", "mean"), knockout_share=("knock_out", "mean"),
        mean_wp=("wp_before", "mean")).reindex(C.PRESSURE_LABELS)
    phase = d.groupby(["innings", "phase"])["is_pressure_bat"].mean().unstack().round(4)
    death = d[d["phase"] == "Death"]
    decided = death[(death["wp_before"] < 0.05) | (death["wp_before"] > 0.95)]
    examples = (d.sort_values("pressure_raw", ascending=False)
                .drop_duplicates("match_id").head(12)
                [["match_id", "match_date", "batting_team", "bowling_team", "innings", "overid", "over_ball_num",
                  "runs_before", "wkts_before", "target", "runs_needed", "balls_left", "rrr", "wp_before",
                  "leverage", "pressure_bat", "striker_name", "bowler_name", "bat_runs", "team_wicket"]])
    calm = (d[d["phase"].eq("Death") & d["innings"].eq(2)].sort_values("pressure_raw").drop_duplicates("match_id").head(6)
            [["match_id", "batting_team", "bowling_team", "overid", "runs_needed", "balls_left", "wkts_before", "wp_before", "pressure_bat"]])
    return {"by_category": cat.round(4).reset_index().to_dict("records"),
            "pressure_share_by_phase": {str(k): v for k, v in phase.to_dict("index").items()},
            "death_over_pressure_share": float(death["is_pressure_bat"].mean()),
            "decided_death_balls_pressure_share": float(decided["is_pressure_bat"].mean()),
            "decided_death_balls": int(len(decided)),
            "extreme_examples": examples.astype({"match_date": str}).round(3).to_dict("records"),
            "low_pressure_death_examples": calm.round(3).to_dict("records")}


# ----------------------------------------------------------------- stability
def _top_overlap(a: pd.DataFrame, b: pd.DataFrame, col: str, n: int = 10) -> int:
    ta = set(a[a["eligible"]].nlargest(n, col)["player_id"])
    tb = set(b[b["eligible"]].nlargest(n, col)["player_id"])
    return len(ta & tb)


def _compare(base: pd.DataFrame, alt: pd.DataFrame, col: str) -> dict:
    j = base[base["eligible"]][["player_id", col]].merge(alt[alt["eligible"]][["player_id", col]], on="player_id", suffixes=("", "_alt"))
    rho = spearmanr(j[col], j[f"{col}_alt"]).statistic if len(j) > 3 else np.nan
    top = base[base["eligible"]].nlargest(10, col)["player_id"].tolist()
    alt_rank = alt[alt["eligible"]].sort_values(col, ascending=False).reset_index(drop=True)
    alt_rank["r"] = np.arange(1, len(alt_rank) + 1)
    pos = alt_rank.set_index("player_id")["r"]
    return {"spearman": float(rho), "top10_overlap": _top_overlap(base, alt, col),
            "baseline_top10_ranks": [int(pos.get(p, -1)) for p in top]}


def sensitivity(d: pd.DataFrame, lam: float, bat0: pd.DataFrame, bowl0: pd.DataFrame) -> list[dict]:
    rows = []

    def run(label, group, dd=d, bw=None, ww=None, thr=C.PRESSURE_THRESHOLD, mb=None, mm=None):
        b, _ = rate_batters(dd, lam, weights=bw, thr=thr, bootstrap=False, min_balls=mb, min_matches=mm)
        w, _ = rate_bowlers(dd, lam, weights=ww, thr=thr, bootstrap=False, min_balls=mb, min_matches=mm)
        rows.append({"scenario": label, "group": group, "batters": _compare(bat0, b, "BPPI"),
                     "bowlers": _compare(bowl0, w, "BoPPI")})

    for thr in (65, 70, 80, 85):
        run(f"Pressure threshold >= {thr}", "Pressure threshold", thr=thr)
    eq_b = {k: 0.2 for k in C.BPPI_WEIGHTS}
    eq_w = {k: 0.2 for k in C.BOPPI_WEIGHTS}
    run("Equal component weights", "Rating weights", bw=eq_b, ww=eq_w)
    run("Performance-heavy (no uplift/consistency)", "Rating weights",
        bw={"scoring": 0.45, "survival": 0.3, "impact": 0.25, "uplift": 0, "consistency": 0},
        ww={"economy": 0.45, "wickets": 0.3, "impact": 0.25, "uplift": 0, "consistency": 0})
    run("Impact-heavy (WPA 40%)", "Rating weights",
        bw={"scoring": 0.2, "survival": 0.15, "impact": 0.4, "uplift": 0.1, "consistency": 0.15},
        ww={"economy": 0.2, "wickets": 0.15, "impact": 0.4, "uplift": 0.1, "consistency": 0.15})
    run("Stricter eligibility (200 balls, 20 matches)", "Eligibility", mb=200, mm=20)
    run("Looser eligibility (100 balls, 10 matches)", "Eligibility", mb=100, mm=10)

    for label, w in (("Leverage only", {"leverage": 1.0, "closeness": 0.0, "stress": 0.0}),
                     ("Balanced formula 0.4/0.4/0.2", {"leverage": 0.4, "closeness": 0.4, "stress": 0.2})):
        dd = add_expected(compute_pressure(d, weights=w))
        run(f"Pressure formula: {label}", "Pressure formula", dd=dd)

    for label, wt in (("Associate T20Is full weight", 1.0), ("Associate T20Is weight 0.3", 0.3)):
        dd = d.copy()
        dd.loc[dd["comp_bucket"] == "T20I_ASSOC", "comp_weight"] = wt
        run(label, "Competition weighting", dd=dd)
    return rows


def temporal_stability(d: pd.DataFrame, lam: float) -> dict:
    """Split-half test: rate players on 2022-2024 and 2025-2026 independently.

    Tests the model itself, so it uses every player (no auction-pool exclusions).
    """
    d = d.drop(columns=["bat_exclusion", "bowl_exclusion"], errors="ignore")
    early, late = d[d["season_year"] <= 2024], d[d["season_year"] >= 2025]
    out = {}
    for role, fn, col in (("batters", rate_batters, "BPPI"), ("bowlers", rate_bowlers, "BoPPI")):
        a, _ = fn(early, lam, bootstrap=False, min_balls=60, min_matches=6)
        b, _ = fn(late, lam, bootstrap=False, min_balls=60, min_matches=6)
        j = a[a["eligible"]].merge(b[b["eligible"]], on="player_id", suffixes=("_a", "_b"))
        comps = [c for c in a.columns if c.startswith("raw_")]
        out[role] = {
            "players_in_both": int(len(j)),
            "rating_spearman": float(spearmanr(j[f"{col}_a"], j[f"{col}_b"]).statistic),
            "component_spearman": {c.replace("raw_", ""): float(spearmanr(j[f"{c}_a"], j[f"{c}_b"]).statistic) for c in comps},
        }
    return out


def manual_spot_check(d: pd.DataFrame, bat: pd.DataFrame, bowl: pd.DataFrame) -> dict:
    """Recompute headline numbers for the #1 players with plain pandas filters."""
    out = {}
    b1 = bat[bat["eligible"]].nsmallest(1, "rank").iloc[0]
    x = d[(d["striker_id"] == b1.player_id) & (d["pressure_bat"] >= C.PRESSURE_THRESHOLD) & ~d["is_wide"]]
    out["top_batter"] = {"name": b1["name"], "pipeline_runs": int(b1.p_runs), "manual_runs": int(x["runs"].sum()),
                         "pipeline_balls": int(b1.p_balls), "manual_balls": int(len(x))}
    w1 = bowl[bowl["eligible"]].nsmallest(1, "rank").iloc[0]
    y = d[(d["bowler_id"] == w1.player_id) & (d["pressure_bowl"] >= C.PRESSURE_THRESHOLD)]
    legal = y[~y["extras_type"].isin(["wide", "Overstep", "other"])]
    runs = y["runs"].sum() + y.loc[y["extras_type"].isin(["wide", "Overstep", "other"]), "extras1_runs"].sum()
    wk = y["dismissal_type"].isin(["Caught", "Bowled", "LBW", "Stump", "Hit Wicket"]).sum()
    out["top_bowler"] = {"name": w1["name"], "pipeline_runs": int(w1.p_runs), "manual_runs": int(runs),
                         "pipeline_legal_balls": int(w1.p_legal_balls), "manual_legal_balls": int(len(legal)),
                         "pipeline_wkts": int(w1.p_wkts), "manual_wkts": int(wk)}
    return out
