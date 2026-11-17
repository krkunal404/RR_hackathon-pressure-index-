"""FastAPI backend for the Pressure Analytics platform.

    uvicorn backend.main:app --reload --port 8000

Serves the official ratings (computed by `python main.py`) plus live,
filterable aggregates over the delivery-level DuckDB store. If the React
build exists at frontend/dist it is served at / as well.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .db import metrics, q, records, where
from .schemas import Filters, Overview, PlayerProfile, RankingResponse


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init()          # open the bundled DuckDB file before serving
    yield


app = FastAPI(title="SupeRR Pressure Analytics API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

Role = Literal["batters", "bowlers"]
RCOL = {"batters": "BPPI", "bowlers": "BoPPI"}
PCAT = {"batters": "pcat_bat", "bowlers": "pcat_bowl"}
PFLAG = {"batters": "is_pressure_bat", "bowlers": "is_pressure_bowl"}
CATS = ["Low", "Moderate", "High", "Extreme"]


def _num(v):
    return None if v is None else float(v)


@app.get("/api/health")
def health():
    return {"status": "ok", "source": db.source()}


@app.get("/api/overview", response_model=Overview)
def overview():
    m = metrics()
    return {**m["overview"], "generated_at": m["generated_at"]}


@app.get("/api/filters", response_model=Filters)
def filters():
    teams = q("SELECT DISTINCT batting_team AS t FROM deliveries WHERE batting_team IS NOT NULL ORDER BY 1")["t"].tolist()
    seasons = q("SELECT DISTINCT season_year AS s FROM deliveries ORDER BY 1")["s"].astype(int).tolist()
    return {"competitions": ["IPL", "T20I"], "seasons": seasons, "teams": teams,
            "pressure_categories": CATS, "phases": ["Powerplay", "Middle", "Death"]}


# ------------------------------------------------------------------ rankings
@app.get("/api/rankings/{role}", response_model=RankingResponse)
def rankings(role: Role, competition: str = "All", team: str | None = None, search: str | None = None,
             eligible_only: bool = True, limit: int = Query(200, le=1000)):
    col = RCOL[role]
    table = role
    if competition in ("IPL", "T20I"):
        rating, rank, elig = f"{col}_{competition}", f"rank_{competition}", f"eligible_{competition}"
    else:
        rating, rank, elig = col, "rank", "eligible"
    sql = f"SELECT *, {rating} AS rating, {rank} AS rank_sel, {elig} AS eligible_sel FROM {table} WHERE 1=1"
    params: list = []
    if eligible_only:
        sql += f" AND {elig}"
    if team:
        sql += " AND (team = ? OR national_team = ? OR ipl_team = ?)"
        params += [team, team, team]
    if search:
        sql += " AND lower(name) LIKE ?"
        params.append(f"%{search.lower()}%")
    sql += f" ORDER BY {rating} DESC NULLS LAST LIMIT {int(limit)}"
    df = q(sql, params)
    if "rank_sel" in df:
        df["rank"] = df["rank_sel"]
        df["eligible"] = df["eligible_sel"].fillna(False)
    df = df.drop(columns=[c for c in ("rank_sel", "eligible_sel") if c in df])
    return {"role": role, "competition": competition, "count": len(df), "rows": records(df)}


@app.get("/api/top10/{role}")
def top10(role: Role):
    df = q(f"SELECT * FROM {role} WHERE eligible ORDER BY rank LIMIT 10")
    return records(df)


# ------------------------------------------------------------------ players
def _split(role: Role, pid: int, group: str, extra: str = "", params: list | None = None):
    if role == "batters":
        sql = f"""SELECT {group} AS k, COUNT(*) AS balls, SUM(bat_runs) AS runs, SUM(CAST(striker_out AS INT)) AS outs,
                  100.0*SUM(bat_runs)/COUNT(*) AS sr, 100.0*SUM(exp_bat_runs)/COUNT(*) AS exp_sr,
                  100.0*AVG(CAST(is_dot_bat AS INT)) AS dot_pct, 100.0*AVG(CAST(is_boundary AS INT)) AS boundary_pct,
                  SUM(wpa) AS wpa
                  FROM deliveries WHERE ball_faced AND striker_id = ? {extra} GROUP BY 1 ORDER BY 1"""
    else:
        sql = f"""SELECT {group} AS k, SUM(CAST(is_legal AS INT)) AS balls, SUM(bowler_runs) AS runs,
                  SUM(CAST(bowler_wicket AS INT)) AS wkts,
                  6.0*SUM(bowler_runs)/NULLIF(SUM(CAST(is_legal AS INT)),0) AS econ,
                  6.0*SUM(exp_bowl_runs)/NULLIF(SUM(CAST(is_legal AS INT)),0) AS exp_econ,
                  100.0*SUM(CAST(is_dot_bowl AS INT))/NULLIF(SUM(CAST(is_legal AS INT)),0) AS dot_pct,
                  100.0*SUM(CAST(is_boundary AS INT))/NULLIF(SUM(CAST(is_legal AS INT)),0) AS boundary_pct,
                  -SUM(wpa) AS wpa
                  FROM deliveries WHERE bowler_id = ? {extra} GROUP BY 1 ORDER BY 1"""
    return records(q(sql, [pid] + (params or [])))


@app.get("/api/players/{role}/{player_id}", response_model=PlayerProfile)
def player(role: Role, player_id: int, competition: str = "All", season: int | None = None):
    row = q(f"SELECT * FROM {role} WHERE player_id = ?", [player_id])
    if row.empty:
        raise HTTPException(404, "player not found")
    p = records(row)[0]
    extra, params = "", []
    if competition in ("IPL", "T20I"):
        extra += " AND competition = ?"; params.append(competition)
    if season:
        extra += " AND season_year = ?"; params.append(season)
    names = (["scoring", "survival", "impact", "uplift", "consistency"] if role == "batters"
             else ["economy", "wickets", "impact", "uplift", "consistency"])
    meta = metrics()["batter_meta" if role == "batters" else "bowler_meta"]
    weights = metrics()["config"]["BPPI_WEIGHTS" if role == "batters" else "BOPPI_WEIGHTS"]
    comps = [{"component": n, "weight": weights[n], "z": p.get(f"z_{n}"), "shrunk": p.get(f"c_{n}"),
              "raw": p.get(f"raw_{n}"), "contribution": (p.get(f"z_{n}") or 0) * weights[n],
              "signal_share": meta["component_signal_share"][n]} for n in names]
    mt = "batter_matches" if role == "batters" else "bowler_matches"
    w, wp = where({"competition": competition if competition in ("IPL", "T20I") else None, "season_year": season})
    matches = q(f"SELECT * FROM {mt}{w}{' AND' if w else ' WHERE'} player_id = ? ORDER BY match_date", wp + [player_id])
    pcat = PCAT[role]
    flag = PFLAG[role]
    return {
        "role": role, "player": p, "components": comps, "matches": records(matches),
        "by_category": _split(role, player_id, pcat, extra, params),
        "by_phase": _split(role, player_id, f"phase || CASE WHEN {flag} THEN ' - pressure' ELSE ' - normal' END", extra, params),
        "by_chase": _split(role, player_id, """CASE WHEN innings = 1 THEN 'Setting target'
                           WHEN batting_team_won = 1 THEN 'Successful chase' WHEN batting_team_won = 0 THEN 'Failed chase'
                           ELSE 'No result' END""", extra, params),
        "by_season": _split(role, player_id, f"season_year || CASE WHEN {flag} THEN '|P' ELSE '|N' END", extra, params),
        "competition_split": _split(role, player_id, f"competition || CASE WHEN {flag} THEN '|P' ELSE '|N' END", "", []),
    }


@app.get("/api/players/{role}/{player_id}/distribution")
def player_distribution(role: Role, player_id: int):
    col, pc = ("striker_id", "pressure_bat") if role == "batters" else ("bowler_id", "pressure_bowl")
    df = q(f"""SELECT FLOOR({pc}/10)*10 AS bucket, COUNT(*) AS n FROM deliveries
               WHERE {col} = ? {'AND ball_faced' if role == 'batters' else ''} GROUP BY 1 ORDER BY 1""", [player_id])
    return records(df)


@app.get("/api/search")
def search(q_: str = Query("", alias="q"), limit: int = 12):
    if len(q_) < 2:
        return []
    df = q("""SELECT * FROM (
                SELECT player_id, name, team, 'batters' AS role, BPPI AS rating, eligible FROM batters
                UNION ALL SELECT player_id, name, team, 'bowlers', BoPPI, eligible FROM bowlers)
              WHERE lower(name) LIKE ? ORDER BY eligible DESC, rating DESC NULLS LAST LIMIT ?""", [f"%{q_.lower()}%", limit])
    return records(df)


# ------------------------------------------------------------------ explorer
@app.get("/api/explorer/{role}")
def explorer(role: Role, competition: str = "All", season: int | None = None, team: str | None = None,
             pressure_category: str = "High+Extreme", phase: str | None = None, min_balls: int = 60, limit: int = 50):
    """Live aggregates for any filter combination (descriptive, not the official rating)."""
    w, params = where({"competition": competition if competition in ("IPL", "T20I") else None,
                       "season_year": season, "phase": phase,
                       ("batting_team" if role == "batters" else "bowling_team"): team})
    pc = PCAT[role]
    if pressure_category == "High+Extreme":
        w += (" AND " if w else " WHERE ") + PFLAG[role]
    elif pressure_category in CATS:
        w += (" AND " if w else " WHERE ") + f"{pc} = ?"
        params.append(pressure_category)
    if role == "batters":
        sql = f"""SELECT striker_id AS player_id, ANY_VALUE(striker_name) AS name, COUNT(*) AS balls, SUM(bat_runs) AS runs,
                  SUM(CAST(striker_out AS INT)) AS outs, 100.0*SUM(bat_runs)/COUNT(*) AS sr,
                  100.0*SUM(exp_bat_runs)/COUNT(*) AS exp_sr, 100.0*(SUM(bat_runs)-SUM(exp_bat_runs))/COUNT(*) AS sr_vs_exp,
                  SUM(bat_runs)/NULLIF(SUM(CAST(striker_out AS INT)),0) AS avg, 100.0*AVG(CAST(is_boundary AS INT)) AS boundary_pct,
                  100.0*AVG(CAST(is_dot_bat AS INT)) AS dot_pct, SUM(wpa) AS wpa, COUNT(DISTINCT match_id) AS matches
                  FROM deliveries {w}{' AND' if w else ' WHERE'} ball_faced GROUP BY 1 HAVING COUNT(*) >= ? ORDER BY sr_vs_exp DESC LIMIT ?"""
    else:
        sql = f"""SELECT bowler_id AS player_id, ANY_VALUE(bowler_name) AS name, SUM(CAST(is_legal AS INT)) AS balls,
                  SUM(bowler_runs) AS runs, SUM(CAST(bowler_wicket AS INT)) AS wkts,
                  6.0*SUM(bowler_runs)/NULLIF(SUM(CAST(is_legal AS INT)),0) AS econ,
                  6.0*SUM(exp_bowl_runs)/NULLIF(SUM(CAST(is_legal AS INT)),0) AS exp_econ,
                  6.0*(SUM(exp_bowl_runs)-SUM(bowler_runs))/NULLIF(SUM(CAST(is_legal AS INT)),0) AS econ_saved,
                  100.0*SUM(CAST(is_dot_bowl AS INT))/NULLIF(SUM(CAST(is_legal AS INT)),0) AS dot_pct,
                  100.0*SUM(CAST(is_boundary AS INT))/NULLIF(SUM(CAST(is_legal AS INT)),0) AS boundary_pct,
                  -SUM(wpa) AS wpa, COUNT(DISTINCT match_id) AS matches
                  FROM deliveries {w} GROUP BY 1 HAVING SUM(CAST(is_legal AS INT)) >= ? ORDER BY econ_saved DESC LIMIT ?"""
    return records(q(sql, params + [min_balls, limit]))


# ------------------------------------------------------------------ pressure
@app.get("/api/pressure/summary")
def pressure_summary(competition: str = "All", season: int | None = None):
    w, params = where({"competition": competition if competition in ("IPL", "T20I") else None, "season_year": season})
    cats = q(f"""SELECT pcat_bat AS category, COUNT(*) AS deliveries, AVG(bat_runs) AS runs_per_ball,
                 100*AVG(CAST(team_wicket AS INT)) AS wicket_pct, 100*AVG(CAST(is_dot_bat AS INT)) AS dot_pct,
                 100*AVG(CAST(is_boundary AS INT)) AS boundary_pct, AVG(leverage) AS leverage,
                 100*AVG(CAST(close_match AS INT)) AS close_pct
                 FROM deliveries{w} GROUP BY 1""", params)
    cats["o"] = cats["category"].map({c: i for i, c in enumerate(CATS)})
    phase = q(f"""SELECT innings, phase, pcat_bat AS category, COUNT(*) AS n FROM deliveries{w} GROUP BY 1,2,3""", params)
    hist = q(f"""SELECT innings, FLOOR(pressure_bat/5)*5 AS bucket, COUNT(*) AS n,
                 AVG(bat_runs) AS runs_per_ball, 100*AVG(CAST(team_wicket AS INT)) AS wicket_pct
                 FROM deliveries{w} GROUP BY 1,2 ORDER BY 1,2""", params)
    overs = q(f"""SELECT innings, overid AS over, AVG(pressure_bat) AS mean_pressure, AVG(leverage) AS leverage,
                  100*AVG(CAST(is_pressure_bat AS INT)) AS pressure_share FROM deliveries{w} GROUP BY 1,2 ORDER BY 1,2""", params)
    chase = q(f"""SELECT CASE WHEN batting_team_won = 1 THEN 'Successful chase' WHEN batting_team_won = 0 THEN 'Failed chase' END AS outcome,
                  pcat_bat AS category, COUNT(*) AS n, AVG(bat_runs) AS runs_per_ball, 100*AVG(CAST(team_wicket AS INT)) AS wicket_pct
                  FROM deliveries{w}{' AND' if w else ' WHERE'} innings = 2 AND batting_team_won IS NOT NULL GROUP BY 1,2""", params)
    return {"categories": records(cats.sort_values("o").drop(columns="o")), "phase_mix": records(phase),
            "histogram": records(hist), "by_over": records(overs), "chase": records(chase)}


@app.get("/api/pressure/moments")
def pressure_moments(competition: str = "All", season: int | None = None, limit: int = 15):
    w, params = where({"competition": competition if competition in ("IPL", "T20I") else None, "season_year": season})
    df = q(f"""SELECT * FROM (
                 SELECT match_id, match_date, competition, comp_name, batting_team, bowling_team, innings, overid, over_ball_num,
                        runs_needed, balls_left, wkts_before, wp_before, leverage, pressure_raw, striker_name, bowler_name,
                        bat_runs, team_wicket, wpa,
                        ROW_NUMBER() OVER (PARTITION BY match_id ORDER BY pressure_raw DESC) AS rn
                 FROM deliveries{w}) WHERE rn = 1 ORDER BY pressure_raw DESC LIMIT ?""", params + [limit])
    return records(df)


@app.get("/api/matches/{match_id}")
def match_curve(match_id: int):
    df = q("""SELECT innings, overid, over_ball_num, batting_team, bowling_team, striker_name, bowler_name, runs_before,
                     wkts_before, target, runs_needed, balls_left, wp_before, wp_after, wpa, leverage, pressure_bat,
                     pcat_bat, bat_runs, total_runs, team_wicket, match_date, comp_name
              FROM deliveries WHERE match_id = ? ORDER BY innings, overid, over_ball_num""", [match_id])
    if df.empty:
        raise HTTPException(404, "match not found")
    return records(df)


# ------------------------------------------------------------------ comparison / methodology
@app.get("/api/competition/{role}")
def competition_compare(role: Role):
    col = RCOL[role]
    df = q(f"""SELECT player_id, name, team, {col} AS rating, {col}_IPL AS ipl, {col}_T20I AS t20i,
                      rank, rank_IPL, rank_T20I, eligible_IPL, eligible_T20I, reliability
               FROM {role} WHERE eligible_IPL AND eligible_T20I ORDER BY rating DESC NULLS LAST""")
    agg = q(f"""SELECT competition, {PCAT[role]} AS category, COUNT(*) AS n,
                       {'100.0*SUM(bat_runs)/COUNT(*)' if role == 'batters' else '6.0*SUM(bowler_runs)/NULLIF(SUM(CAST(is_legal AS INT)),0)'} AS value,
                       100*AVG(CAST(team_wicket AS INT)) AS wicket_pct
                FROM deliveries {'WHERE ball_faced' if role == 'batters' else ''} GROUP BY 1,2""")
    return {"players": records(df), "by_category": records(agg)}


@app.get("/api/methodology")
def methodology():
    m = metrics()
    keys = ["win_probability", "batter_meta", "bowler_meta", "wicket_run_value", "config", "audit"]
    return {k: m[k] for k in keys}


@app.get("/api/validation")
def validation():
    m = metrics()
    return {k: m[k] for k in ("accounting_checks", "pressure_validity", "temporal_stability", "sensitivity", "spot_check")}


# ------------------------------------------------------------------ static frontend
DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        f = DIST / full_path
        return FileResponse(f if f.is_file() else DIST / "index.html")
