"""IPL 2027 auction filter: who Rajasthan Royals can actually buy.

The pressure model and context baselines use every delivery (a Pakistan bowler
still creates pressure for the batters he bowls to). Only the *ranking pool* is
restricted, so ratings, P(top-10) and ranks are relative to buyable players:

* Players who have represented an IPL-ineligible nation (Pakistan) are excluded.
* Players with no match in the last ``AUCTION_MIN_LAST_SEASON`` seasons are
  treated as retired / inactive and excluded.

Each delivery gets ``bat_exclusion`` / ``bowl_exclusion`` columns (None = in the
pool). They are attached once on the full dataset, so competition splits and
sensitivity runs on subsets inherit the same decisions.
"""
from __future__ import annotations

import pandas as pd

from . import config as C


def _appearances(d: pd.DataFrame) -> pd.DataFrame:
    """One row per (player, delivery role) with the team they played for."""
    parts = [
        d[["striker_id", "batting_team", "competition", "season_year", "match_date"]]
        .set_axis(["player_id", "team", "competition", "season_year", "match_date"], axis=1),
        d[["non_striker_id", "batting_team", "competition", "season_year", "match_date"]]
        .set_axis(["player_id", "team", "competition", "season_year", "match_date"], axis=1),
        d[["bowler_id", "bowling_team", "competition", "season_year", "match_date"]]
        .set_axis(["player_id", "team", "competition", "season_year", "match_date"], axis=1),
    ]
    return pd.concat(parts, ignore_index=True).dropna(subset=["player_id"])


def player_auction_info(d: pd.DataFrame) -> pd.DataFrame:
    """Per player: nationality, last season, latest IPL team, auction status and exclusion reason."""
    a = _appearances(d)
    t20i = a[a["competition"] == "T20I"]
    ipl = a[a["competition"] == "IPL"].sort_values("match_date")
    info = pd.DataFrame(index=pd.Index(a["player_id"].unique(), name="player_id"))
    info["nationality"] = t20i.groupby("player_id")["team"].agg(lambda s: s.mode().iat[0])
    info["last_season"] = a.groupby("player_id")["season_year"].max()
    info["last_ipl_team"] = ipl.groupby("player_id")["team"].last()
    info["last_ipl_season"] = ipl.groupby("player_id")["season_year"].max()

    banned = set(t20i.loc[t20i["team"].isin(C.IPL_INELIGIBLE_NATIONS), "player_id"])
    latest = int(a["season_year"].max())
    inactive = info["last_season"] < latest - C.AUCTION_MIN_LAST_SEASON + 1

    reason = pd.Series(None, index=info.index, dtype=object)
    reason[inactive] = "Inactive: last match " + info.loc[inactive, "last_season"].astype(int).astype(str)
    is_banned = info.index.isin(banned)
    reason[is_banned] = "Not IPL-eligible: " + info.loc[is_banned, "nationality"].fillna("Pakistan")
    info["auction_exclusion"] = reason

    info["player_type"] = info["nationality"].map(
        lambda n: "Indian" if n == "India" else ("No T20I since 2022" if pd.isna(n) else "Overseas"))
    in_squad = (info["last_ipl_team"] == C.AUCTION_TEAM) & (info["last_ipl_season"] == info["last_ipl_season"].max())
    info["auction_status"] = "Auction target"
    info.loc[in_squad, "auction_status"] = f"Current {C.AUCTION_TEAM} player (retain)"
    info.loc[info["auction_exclusion"].notna(), "auction_status"] = "Excluded"
    return info


def add_auction_flags(d: pd.DataFrame) -> pd.DataFrame:
    """Attach per-delivery exclusion reasons for the striker and the bowler."""
    reason = player_auction_info(d)["auction_exclusion"]
    d = d.copy()
    d["bat_exclusion"] = d["striker_id"].map(reason)
    d["bowl_exclusion"] = d["bowler_id"].map(reason)
    return d
