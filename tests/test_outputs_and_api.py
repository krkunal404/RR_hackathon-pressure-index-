"""Final deliverables are consistent, and the API serves them."""
import json

import pandas as pd
import pytest

from src import config as C

OUT = C.OUTPUT_DIR


@pytest.fixture(scope="module")
def tops():
    if not (OUT / "top_10_batters.csv").exists():
        pytest.skip("run `python main.py` first")
    return pd.read_csv(OUT / "top_10_batters.csv"), pd.read_csv(OUT / "top_10_bowlers.csv")


def test_top10_lists_are_valid(tops):
    for t, col in zip(tops, ("BPPI", "BoPPI")):
        assert len(t) == 10
        assert t["player_id"].is_unique
        assert list(t["rank"]) == list(range(1, 11))
        assert t[col].is_monotonic_decreasing
        assert t[col].between(0, 100).all()
        assert (t["pressure_matches"] >= C.MIN_PRESSURE_MATCHES).all()


def test_top10_meets_sample_bars(tops):
    bat, bowl = tops
    assert (bat["p_balls"] >= C.MIN_PRESSURE_BALLS_BAT).all()
    assert (bowl["p_legal_balls"] >= C.MIN_PRESSURE_BALLS_BOWL).all()


def test_complete_ratings_match_top10(tops):
    allp = pd.read_csv(OUT / "complete_player_ratings.csv", low_memory=False)
    for t, role, col in ((tops[0], "batter", "BPPI"), (tops[1], "bowler", "BoPPI")):
        e = allp[(allp["role"] == role) & (allp["eligible"])].sort_values(col, ascending=False).head(10)
        assert list(e["player_id"]) == list(t["player_id"])


def test_reliability_is_separate_from_rating(tops):
    allp = pd.read_csv(OUT / "complete_player_ratings.csv", low_memory=False)
    e = allp[(allp["role"] == "batter") & allp["eligible"]]
    assert abs(e["BPPI"].corr(e["reliability"])) < 0.9


def test_metrics_json_has_validation():
    m = json.loads((OUT / "metrics.json").read_text())
    k = m["accounting_checks"]
    assert k["illegal_counted_legal"] == 0 and k["byes_charged_to_bowler"] == 0
    assert k["leakage_runs_before_mismatch"] == 0
    assert m["spot_check"]["top_batter"]["pipeline_runs"] == m["spot_check"]["top_batter"]["manual_runs"]
    assert len(m["sensitivity"]) >= 10


@pytest.fixture(scope="module")
def client():
    if not C.DUCKDB_PATH.exists():
        pytest.skip("run `python main.py` first")
    from fastapi.testclient import TestClient
    from backend.main import app
    return TestClient(app)


@pytest.mark.parametrize("url", [
    "/api/health", "/api/overview", "/api/filters", "/api/top10/batters", "/api/top10/bowlers",
    "/api/rankings/batters", "/api/rankings/bowlers?competition=IPL", "/api/pressure/summary?competition=T20I",
    "/api/pressure/moments", "/api/explorer/bowlers?pressure_category=Extreme&min_balls=30",
    "/api/competition/batters", "/api/methodology", "/api/validation", "/api/search?q=sharma",
])
def test_endpoints_ok(client, url):
    assert client.get(url).status_code == 200


def test_api_top10_matches_csv(client, tops):
    rows = client.get("/api/top10/batters").json()
    assert [r["player_id"] for r in rows] == list(tops[0]["player_id"])


def test_player_profile_and_404(client, tops):
    pid = int(tops[1]["player_id"].iloc[0])
    r = client.get(f"/api/players/bowlers/{pid}").json()
    assert r["player"]["player_id"] == pid and len(r["components"]) == 5
    assert client.get("/api/players/bowlers/999999999").status_code == 404


def test_explorer_filters_are_parameterised(client):
    r = client.get("/api/explorer/batters", params={"team": "India' OR 1=1 --", "min_balls": 1})
    assert r.status_code == 200 and r.json() == []
