"""Run the full SupeRR Selector pipeline: who should Rajasthan Royals back at the IPL 2027 auction?

    python main.py            # full run (pipeline + validation + report)
    python main.py --no-report
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from src import config as C
from src.batter_ratings import rate_batters
from src.bowler_ratings import rate_bowlers
from src.auction import add_auction_flags
from src.data_loader import audit, load_raw
from src.expected import add_expected, wicket_run_value
from src.preprocessing import build_deliveries
from src.pressure_model import WinProbModel, compute_pressure
from src.rankings import competition_splits, finalize
from src.validation import (accounting_checks, manual_spot_check, pressure_face_validity, sensitivity,
                            temporal_stability)

DELIVERY_COLS = [
    "match_id", "match_date", "season_year", "competition", "comp_name", "comp_bucket", "comp_weight", "knock_out",
    "innings", "overid", "over_ball_num", "phase", "batting_team", "bowling_team", "striker_id", "striker_name",
    "non_striker_id", "bowler_id", "bowler_name", "pace_or_spin", "bowling_type", "batting_type", "bat_runs", "extra_runs", "total_runs", "bowler_runs",
    "extras_type", "is_legal", "ball_faced", "is_wide", "is_noball", "is_four", "is_six", "is_boundary",
    "is_dot_bat", "is_dot_bowl", "team_wicket", "striker_out", "bowler_wicket", "dismissal_type",
    "runs_before", "wkts_before", "legal_before", "balls_left", "target", "runs_needed", "rrr", "crr",
    "chase", "successful_chase", "close_match", "batting_team_won",
    "wp_before", "wp_after", "wp_if_four", "wp_if_wicket", "wpa", "leverage", "innings_balls", "match_progress",
    "recent_wkts", "bowler_runs_before", "bowler_balls_before", "c_leverage", "c_closeness", "c_stress", "c_spell",
    "pressure_raw", "pressure_bat", "pressure_bowl", "pcat_bat", "pcat_bowl", "is_pressure_bat", "is_pressure_bowl",
    "exp_bat_runs", "exp_bat_out", "exp_bowl_runs", "exp_bowl_wkt",
]


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def player_match_tables(d: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    bf = d[d["ball_faced"]].assign(p=lambda x: x["is_pressure_bat"])
    bat = bf.groupby(["striker_id", "match_id"]).agg(
        match_date=("match_date", "first"), season_year=("season_year", "first"), competition=("competition", "first"),
        team=("batting_team", "first"), opponent=("bowling_team", "first"), innings=("innings", "first"),
        balls=("ball_faced", "size"), runs=("bat_runs", "sum"), out=("striker_out", "max"),
        pressure_balls=("p", "sum"), mean_pressure=("pressure_bat", "mean"), wpa=("wpa", "sum"),
        exp_runs=("exp_bat_runs", "sum"), close_match=("close_match", "first"), won=("batting_team_won", "first"),
    ).reset_index().rename(columns={"striker_id": "player_id"})
    pr = bf[bf["p"]].groupby(["striker_id", "match_id"]).agg(pressure_runs=("bat_runs", "sum"),
                                                              pressure_exp_runs=("exp_bat_runs", "sum"),
                                                              pressure_outs=("striker_out", "sum"))
    bat = bat.merge(pr, left_on=["player_id", "match_id"], right_index=True, how="left").fillna(
        {"pressure_runs": 0, "pressure_exp_runs": 0, "pressure_outs": 0})

    bw = d.assign(p=lambda x: x["is_pressure_bowl"])
    bowl = bw.groupby(["bowler_id", "match_id"]).agg(
        match_date=("match_date", "first"), season_year=("season_year", "first"), competition=("competition", "first"),
        team=("bowling_team", "first"), opponent=("batting_team", "first"), innings=("innings", "first"),
        legal_balls=("is_legal", "sum"), runs=("bowler_runs", "sum"), wkts=("bowler_wicket", "sum"),
        mean_pressure=("pressure_bowl", "mean"), wpa=("wpa", "sum"), exp_runs=("exp_bowl_runs", "sum"),
        close_match=("close_match", "first"), won=("batting_team_won", "first"),
    ).reset_index().rename(columns={"bowler_id": "player_id"})
    bowl["wpa"] = -bowl["wpa"]
    bowl["won"] = 1 - bowl["won"]
    pb = bw[bw["p"]].groupby(["bowler_id", "match_id"]).agg(
        pressure_legal_balls=("is_legal", "sum"), pressure_runs=("bowler_runs", "sum"),
        pressure_wkts=("bowler_wicket", "sum"), pressure_exp_runs=("exp_bowl_runs", "sum"))
    bowl = bowl.merge(pb, left_on=["player_id", "match_id"], right_index=True, how="left").fillna(
        {"pressure_legal_balls": 0, "pressure_runs": 0, "pressure_wkts": 0, "pressure_exp_runs": 0})
    return bat, bowl


def main(make_report: bool = True) -> None:
    t0 = time.time()
    log = lambda msg: print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)  # noqa: E731
    C.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    C.FIG_DIR.mkdir(parents=True, exist_ok=True)

    raw = load_raw()
    aud = audit(raw)
    log("loaded raw data")
    d, matches = build_deliveries(raw)
    log(f"built {len(d):,} deliveries across {d.match_id.nunique()} matches")

    wp = WinProbModel().fit(d)
    d = wp.annotate(d)
    wp_eval = wp.evaluate(d)
    log("win-probability models fitted (cross-fitted)")
    d = compute_pressure(d)
    d = add_expected(d)
    d = add_auction_flags(d)
    n_ex = d.drop_duplicates("striker_id")["bat_exclusion"].notna().sum()
    log(f"auction pool: {n_ex} batters excluded (Pakistan / inactive)")
    lam = wicket_run_value(d)
    log(f"pressure + context baselines done (wicket = {lam:.2f} runs)")

    bat, mb = rate_batters(d, lam)
    bowl, mw = rate_bowlers(d, lam)
    res = finalize(d, bat, bowl)
    log("ratings + bootstrap done")

    splits = competition_splits(d, lam)
    checks = accounting_checks(d, matches)
    face = pressure_face_validity(d)
    stab = temporal_stability(d, lam)
    spot = manual_spot_check(d, res["batters"], res["bowlers"])
    log("validation done")
    sens = sensitivity(d, lam, res["batters"], res["bowlers"])
    log("sensitivity analysis done")

    # ---- persist ---------------------------------------------------------
    out = C.OUTPUT_DIR
    res["top_batters"].to_csv(out / "top_10_batters.csv", index=False)
    res["top_bowlers"].to_csv(out / "top_10_bowlers.csv", index=False)
    b = res["batters"].assign(role="batter")
    w = res["bowlers"].assign(role="bowler")
    for comp in ("IPL", "T20I"):
        b = b.merge(splits[f"{comp}_bat"][["player_id", "BPPI", "rank", "eligible"]].rename(
            columns={"BPPI": f"BPPI_{comp}", "rank": f"rank_{comp}", "eligible": f"eligible_{comp}"}), on="player_id", how="left")
        w = w.merge(splits[f"{comp}_bowl"][["player_id", "BoPPI", "rank", "eligible"]].rename(
            columns={"BoPPI": f"BoPPI_{comp}", "rank": f"rank_{comp}", "eligible": f"eligible_{comp}"}), on="player_id", how="left")
    allp = pd.concat([b, w], ignore_index=True, sort=False)
    allp.to_csv(out / "complete_player_ratings.csv", index=False)
    d[DELIVERY_COLS].to_csv(out / "pressure_delivery_analysis.csv", index=False)

    d[DELIVERY_COLS].to_parquet(C.PROCESSED_DIR / "deliveries.parquet", index=False)
    b.to_parquet(C.PROCESSED_DIR / "batters.parquet", index=False)
    w.to_parquet(C.PROCESSED_DIR / "bowlers.parquet", index=False)
    pmb, pmw = player_match_tables(d)
    pmb.to_parquet(C.PROCESSED_DIR / "batter_matches.parquet", index=False)
    pmw.to_parquet(C.PROCESSED_DIR / "bowler_matches.parquet", index=False)

    if C.DUCKDB_PATH.exists():
        C.DUCKDB_PATH.unlink()
    con = duckdb.connect(str(C.DUCKDB_PATH))
    for name in ("deliveries", "batters", "bowlers", "batter_matches", "bowler_matches"):
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM read_parquet('{(C.PROCESSED_DIR / (name + '.parquet')).as_posix()}')")
    con.close()

    metrics = {
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "audit": aud, "accounting_checks": checks, "win_probability": wp_eval,
        "pressure_validity": face, "temporal_stability": stab, "sensitivity": sens,
        "spot_check": spot, "batter_meta": mb, "bowler_meta": mw, "wicket_run_value": lam,
        # modelling settings only: skip filesystem paths (they would leak the local machine's layout)
        "config": {k: v for k in dir(C) if k.isupper() and not isinstance(v := getattr(C, k), Path)},
        "overview": {
            "matches": int(d.match_id.nunique()), "deliveries": int(len(d)),
            "ipl_matches": int(d[d.competition == "IPL"].match_id.nunique()),
            "t20i_matches": int(d[d.competition == "T20I"].match_id.nunique()),
            "batters": int(d.striker_id.nunique()), "bowlers": int(d.bowler_id.nunique()),
            "players": int(pd.concat([d.striker_id, d.non_striker_id, d.bowler_id]).nunique()),
            "pressure_deliveries": int(d.is_pressure_bat.sum()),
            "extreme_deliveries": int((d.pcat_bat == "Extreme").sum()),
            "high_deliveries": int((d.pcat_bat == "High").sum()),
            "eligible_batters": mb["eligible"], "eligible_bowlers": mw["eligible"],
            "seasons": sorted(int(s) for s in d.season_year.unique()),
        },
        "auction": {
            "team": C.AUCTION_TEAM,
            "ineligible_nations": sorted(C.IPL_INELIGIBLE_NATIONS),
            "min_last_season": int(d.season_year.max()) - C.AUCTION_MIN_LAST_SEASON + 1,
            # players who met the sample bar but were removed from the auction pool
            "excluded": {role: {
                "ineligible_nation": t.loc[t.sample_ok & t.exclusion.fillna("").str.startswith("Not IPL"), "name"].tolist(),
                "inactive": t.loc[t.sample_ok & t.exclusion.fillna("").str.startswith("Inactive"), "name"].tolist(),
            } for role, t in (("batters", res["batters"]), ("bowlers", res["bowlers"]))},
        },
    }
    (out / "metrics.json").write_text(json.dumps(_jsonable(metrics), indent=2, default=str))
    log("outputs written")

    if make_report:
        from src.report import build_report
        build_report()
        log("methodology report written")

    print(f"\nTOP 10 BATTERS FOR {C.AUCTION_TEAM.upper()} (IPL 2027 AUCTION POOL)")
    print(res["top_batters"][["rank", "name", "auction_status", "player_type", "p_balls", "p_sr", "n_sr", "BPPI", "reliability"]].round(1).to_string(index=False))
    print(f"\nTOP 10 BOWLERS FOR {C.AUCTION_TEAM.upper()} (IPL 2027 AUCTION POOL)")
    print(res["top_bowlers"][["rank", "name", "auction_status", "player_type", "p_legal_balls", "p_econ", "n_econ", "BoPPI", "reliability"]].round(2).to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-report", action="store_true")
    main(make_report=not ap.parse_args().no_report)
