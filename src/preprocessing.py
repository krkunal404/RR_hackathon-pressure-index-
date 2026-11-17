"""Build the clean, delivery-level analytical table.

Every match-state feature is computed from deliveries *before* the current one
(cumulative sums shifted by one ball) so that pressure is measured with only
the information available when the ball was bowled - no leakage from the
outcome of the delivery itself, later deliveries, or the match result.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .data_loader import classify_competition, parse_result


def _team_names(raw: dict[str, pd.DataFrame]) -> pd.Series:
    t = raw["teams"].drop_duplicates("team_id").set_index("team_id")["team_name"]
    return t


def build_deliveries(raw: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    comp = classify_competition(raw["competitions"])
    m = parse_result(raw["matches"]).merge(
        comp[["comp_id", "comp_name", "competition", "season_year"]], on="comp_id", how="left")
    m = m[m["competition"].isin(["IPL", "T20I"])].copy()

    b = raw["ball_by_ball"].copy()
    b = b[b["innings"].isin([1, 2])]                       # drop super overs
    b = b.merge(m[["match_id", "comp_id", "comp_name", "competition", "season_year", "match_date",
                   "knock_out", "stage", "win_team_id", "no_result", "tied", "is_dls",
                   "first_inn_revised_overs", "second_inn_revised_overs", "revised_target",
                   "margin_runs", "margin_wkts"]], on="match_id", how="inner")
    b = b.sort_values(["match_id", "innings", "overid", "over_ball_num"]).reset_index(drop=True)

    names = _team_names(raw)
    b["batting_team"] = b["batting_team_id"].map(names)
    b["bowling_team"] = b["bowling_team_id"].map(names)

    # ---- delivery accounting -------------------------------------------------
    et = b["extras_type"].fillna("none")
    b["extras_type"] = et
    b["is_wide"] = et.eq("wide")
    b["is_noball"] = et.isin(C.NO_BALL_EXTRAS)
    b["is_legal"] = ~et.isin(C.ILLEGAL_EXTRAS)
    b["ball_faced"] = ~b["is_wide"]                         # no-balls count as faced
    b["bat_runs"] = b["runs"].astype(int)
    # extras1_runs = recorded extra runs on the ball (wides incl. any run, byes, no-ball
    # penalty, 5 penalty runs). extras_2_runs = byes / leg-byes run off a no-ball.
    x1 = b["extras1_runs"].fillna(0).astype(int)
    x2 = b["extras_2_runs"].fillna(0).astype(int)
    b["extra_runs"] = x1 + np.where(b["is_noball"], x2, 0)
    b["total_runs"] = b["bat_runs"] + b["extra_runs"]
    # Wides and the no-ball penalty are charged to the bowler; byes off a no-ball are not.
    b["bowler_runs"] = b["bat_runs"] + np.where(et.isin(C.BOWLER_CHARGED_EXTRAS), x1, 0)
    b["is_dot_bat"] = b["ball_faced"] & b["bat_runs"].eq(0)
    b["is_dot_bowl"] = b["is_legal"] & b["bowler_runs"].eq(0)
    b["is_boundary"] = b["is_four"] | b["is_six"]
    dt = b["dismissal_type"]
    b["team_wicket"] = b["is_wicket"].astype(bool)
    b["striker_out"] = (b["team_wicket"] & b["dismissed_player_id"].eq(b["striker_id"])
                        & ~dt.isin(C.NON_BATTER_FAULT_DISMISSALS))
    b["nonstriker_out"] = (b["team_wicket"] & b["dismissed_player_id"].eq(b["non_striker_id"])
                           & ~dt.isin(C.NON_BATTER_FAULT_DISMISSALS))
    b["bowler_wicket"] = b["team_wicket"] & dt.isin(C.BOWLER_CREDITED_DISMISSALS)

    # ---- pre-delivery state ---------------------------------------------------
    g = b.groupby(["match_id", "innings"], sort=False)
    b["runs_before"] = g["total_runs"].cumsum() - b["total_runs"]
    b["wkts_before"] = g["team_wicket"].cumsum() - b["team_wicket"].astype(int)
    b["legal_before"] = g["is_legal"].cumsum() - b["is_legal"].astype(int)

    inn_balls = np.where(b["innings"].eq(1), b["first_inn_revised_overs"], b["second_inn_revised_overs"])
    b["innings_balls"] = pd.Series(inn_balls).fillna(120).clip(upper=120).astype(int).values
    b["balls_left"] = (b["innings_balls"] - b["legal_before"]).clip(lower=1)
    b["wkts_left"] = (10 - b["wkts_before"]).clip(lower=1)
    b["over_no"] = b["overid"]
    b["phase"] = pd.cut(b["overid"], [0, 6, 15, 20], labels=["Powerplay", "Middle", "Death"]).astype(str)
    b["crr"] = np.where(b["legal_before"] > 0, b["runs_before"] * 6 / b["legal_before"].clip(lower=1), np.nan)

    inn_tot = b.groupby(["match_id", "innings"])["total_runs"].sum().unstack()
    first_total = b["match_id"].map(inn_tot[1])
    target = np.where(b["revised_target"].notna(), b["revised_target"], first_total + 1)
    b["target"] = np.where(b["innings"].eq(2), target, np.nan)
    b["runs_needed"] = np.where(b["innings"].eq(2), (b["target"] - b["runs_before"]).clip(lower=1), np.nan)
    b["rrr"] = b["runs_needed"] * 6 / b["balls_left"]

    # ---- bowler spell state (before this ball, within match) ----------------
    gb = b.groupby(["match_id", "bowler_id"], sort=False)
    b["bowler_runs_before"] = gb["bowler_runs"].cumsum() - b["bowler_runs"]
    b["bowler_balls_before"] = gb["is_legal"].cumsum() - b["is_legal"].astype(int)
    b["bowler_wkts_before"] = gb["bowler_wicket"].cumsum() - b["bowler_wicket"].astype(int)

    # ---- outcome labels (used ONLY as model targets / evaluation, never as features)
    b["batting_team_won"] = np.where(b["no_result"] | b["tied"] | b["win_team_id"].isna(), np.nan,
                                     (b["win_team_id"] == b["batting_team_id"]).astype(float))

    # ---- match-level context flags ------------------------------------------
    legal2 = b[b.innings.eq(2)].groupby("match_id")["is_legal"].sum()
    inn2_max = b[b.innings.eq(2)].groupby("match_id")["innings_balls"].first()
    chase_balls_left_end = (inn2_max - legal2)
    close = (b["margin_runs"].le(10)
             | (b["margin_wkts"].notna() & b["match_id"].map(chase_balls_left_end).le(6))
             | b["tied"])
    b["close_match"] = close.fillna(False)
    b["chase"] = b["innings"].eq(2)
    b["successful_chase"] = b["chase"] & b["batting_team_won"].eq(1)

    # ---- competition weighting ----------------------------------------------
    assoc = ~(b["batting_team"].isin(C.FULL_MEMBERS) & b["bowling_team"].isin(C.FULL_MEMBERS))
    b["comp_bucket"] = np.where(b["competition"].eq("IPL"), "IPL",
                                np.where(assoc, "T20I_ASSOC", "T20I_FULL"))
    b["comp_weight"] = b["comp_bucket"].map(C.COMPETITION_WEIGHTS)
    b["is_ipl"] = b["competition"].eq("IPL").astype(int)

    return b, m
