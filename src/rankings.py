"""Assemble the Rajasthan Royals IPL 2027 auction rankings, competition splits and justifications."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .auction import player_auction_info
from .batter_ratings import rate_batters
from .bowler_ratings import rate_bowlers


def player_info(d: pd.DataFrame, role: str) -> pd.DataFrame:
    pid, name, team = (("striker_id", "striker_name", "batting_team") if role == "bat"
                       else ("bowler_id", "bowler_name", "bowling_team"))
    x = d[[pid, name, team, "competition", "season_year", "match_date"]]
    last = x.sort_values("match_date").groupby(pid).tail(1).set_index(pid)
    latest_season = x[x["season_year"] == x[pid].map(last["season_year"])]
    team_mode = latest_season.groupby(pid)[team].agg(lambda s: s.mode().iat[0])
    intl = x[x["competition"] == "T20I"].groupby(pid)[team].agg(lambda s: s.mode().iat[0])
    ipl = x[x["competition"] == "IPL"].groupby(pid)[team].agg(lambda s: s.mode().iat[0])
    comps = x.groupby(pid)["competition"].agg(lambda s: " + ".join(sorted(set(s), key=["IPL", "T20I"].index)))
    seasons = x.groupby(pid)["season_year"].agg(lambda s: f"{s.min()}-{s.max()}")
    info = pd.DataFrame({"name": x.groupby(pid)[name].first(), "team": team_mode,
                         "national_team": intl, "ipl_team": ipl, "competition": comps,
                         "seasons": seasons}).rename_axis("player_id")
    style_col = "batting_type" if role == "bat" else "bowling_type"
    info["style"] = d.groupby(pid)[style_col].agg(lambda s: s.mode().iat[0])
    if role == "bowl":
        info["pace_or_spin"] = d.groupby(pid)["pace_or_spin"].agg(lambda s: s.mode().iat[0])
    return info


def _fmt(v, nd=1):
    return "n/a" if pd.isna(v) else f"{v:.{nd}f}"


def justify_batter(r: pd.Series) -> str:
    parts = [f"Under pressure: {int(r.p_runs)} runs off {int(r.p_balls)} balls at SR {_fmt(r.p_sr)} "
             f"({'+' if r.p_sr_vs_expected >= 0 else ''}{_fmt(r.p_sr_vs_expected)} vs context-expected SR {_fmt(r.p_exp_sr)})"]
    parts.append(f"dismissed every {_fmt(r.p_balls / max(r.p_outs, 1), 0)} balls (avg {_fmt(r.p_avg)})")
    parts.append(f"normal-situation SR {_fmt(r.n_sr)} -> change {('+' if r.sr_change >= 0 else '')}{_fmt(r.sr_change)}")
    parts.append(f"positive pressure value in {int(r.cons_ok)}/{int(r.cons_n)} qualifying matches")
    parts.append(f"P(top-10) {_fmt(100 * r.p_top10, 0)}%, 90% CI {_fmt(r.BPPI_lo, 0)}-{_fmt(r.BPPI_hi, 0)}")
    return "; ".join(parts) + "."


def justify_bowler(r: pd.Series) -> str:
    parts = [f"Under pressure: {int(r.p_wkts)} wkts in {int(r.p_legal_balls)} legal balls, economy {_fmt(r.p_econ, 2)} "
             f"({'+' if r.p_econ_vs_expected >= 0 else ''}{_fmt(r.p_econ_vs_expected, 2)} vs context-expected {_fmt(r.p_exp_econ, 2)})"]
    parts.append(f"dot% {_fmt(r.p_dot_pct)}, boundary% {_fmt(r.p_boundary_pct)}")
    parts.append(f"normal economy {_fmt(r.n_econ, 2)} -> change {('+' if r.econ_change >= 0 else '')}{_fmt(r.econ_change, 2)}")
    parts.append(f"value-positive in {int(r.cons_ok)}/{int(r.cons_n)} qualifying spells")
    parts.append(f"P(top-10) {_fmt(100 * r.p_top10, 0)}%, 90% CI {_fmt(r.BoPPI_lo, 0)}-{_fmt(r.BoPPI_hi, 0)}")
    return "; ".join(parts) + "."


BAT_OUT_COLS = ["rank", "player_id", "name", "auction_status", "player_type", "nationality", "last_ipl_team",
                "team", "competition", "matches", "pressure_matches",
                "p_balls", "p_runs", "p_sr", "p_avg", "p_boundary_pct", "p_dot_pct", "p_dismissal_rate",
                "n_sr", "n_avg", "sr_change", "p_sr_vs_expected", "BPPI", "BPPI_lo", "BPPI_hi",
                "reliability", "p_top10", "rank_lo", "rank_hi", "justification"]
BOWL_OUT_COLS = ["rank", "player_id", "name", "auction_status", "player_type", "nationality", "last_ipl_team",
                 "team", "pace_or_spin", "competition", "matches", "pressure_matches",
                 "p_legal_balls", "p_runs", "p_wkts", "p_econ", "p_wkts_per_over", "p_dot_pct",
                 "p_boundary_pct", "n_econ", "econ_change", "p_econ_vs_expected", "BoPPI", "BoPPI_lo",
                 "BoPPI_hi", "reliability", "p_top10", "rank_lo", "rank_hi", "justification"]


def finalize(d: pd.DataFrame, bat: pd.DataFrame, bowl: pd.DataFrame) -> dict[str, pd.DataFrame]:
    auc = player_auction_info(d)[["nationality", "player_type", "last_season", "last_ipl_team", "auction_status"]]
    bat = (bat.merge(player_info(d, "bat"), left_on="player_id", right_index=True, how="left")
              .merge(auc, left_on="player_id", right_index=True, how="left"))
    bowl = (bowl.merge(player_info(d, "bowl"), left_on="player_id", right_index=True, how="left")
                .merge(auc, left_on="player_id", right_index=True, how="left"))
    bat["justification"] = ""
    bowl["justification"] = ""
    eb, ew = bat["eligible"], bowl["eligible"]
    bat.loc[eb, "justification"] = bat[eb].apply(justify_batter, axis=1)
    bowl.loc[ew, "justification"] = bowl[ew].apply(justify_bowler, axis=1)
    top_bat = bat[eb].sort_values("rank").head(10)[BAT_OUT_COLS].reset_index(drop=True)
    top_bowl = bowl[ew].sort_values("rank").head(10)[BOWL_OUT_COLS].reset_index(drop=True)
    assert top_bat["player_id"].is_unique and top_bowl["player_id"].is_unique
    return {"batters": bat, "bowlers": bowl, "top_batters": top_bat, "top_bowlers": top_bowl}


def competition_splits(d: pd.DataFrame, lam: float) -> dict[str, pd.DataFrame]:
    """Ratings re-estimated inside IPL only and T20I only (lower sample bars)."""
    out = {}
    for comp in ("IPL", "T20I"):
        sub = d[d["competition"] == comp]
        b, _ = rate_batters(sub, lam, bootstrap=False, min_balls=100, min_matches=10)
        w, _ = rate_bowlers(sub, lam, bootstrap=False, min_balls=100, min_matches=10)
        out[f"{comp}_bat"] = b[["player_id", "BPPI", "rank", "eligible", "n", "p_sr", "n_sr", "reliability"]]
        out[f"{comp}_bowl"] = w[["player_id", "BoPPI", "rank", "eligible", "n", "p_econ", "n_econ", "reliability"]]
    return out
