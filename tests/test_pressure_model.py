"""Pressure model behaviour on the processed data."""
import numpy as np
import pandas as pd

from src import config as C
from src.pressure_model import _chase_features, _first_features


def test_pressure_scores_are_bounded_and_categorised(deliveries):
    for col in ("pressure_bat", "pressure_bowl"):
        assert deliveries[col].between(0, 100).all()
    assert set(deliveries["pcat_bat"].unique()) == set(C.PRESSURE_LABELS)
    share = deliveries.groupby("innings")["is_pressure_bat"].mean()
    assert np.allclose(share, 0.25, atol=0.01)


def test_decided_death_overs_are_not_pressure(deliveries):
    death = deliveries[deliveries["phase"] == "Death"]
    decided = death[(death["wp_before"] < 0.05) | (death["wp_before"] > 0.95)]
    assert len(decided) > 1000
    assert decided["is_pressure_bat"].mean() < 0.05
    assert death["is_pressure_bat"].mean() > 0.15


def test_pressure_tracks_close_games_and_leverage(deliveries):
    by = deliveries.groupby("pcat_bat")[["leverage", "close_match"]].mean()
    assert by.loc["Extreme", "leverage"] > by.loc["High", "leverage"] > by.loc["Low", "leverage"]
    assert by.loc["Extreme", "close_match"] > by.loc["Low", "close_match"]


def test_win_probability_is_monotone_in_chase(deliveries):
    s = deliveries[(deliveries["innings"] == 2) & deliveries["wp_before"].notna()]
    near = s[s["balls_left"].between(10, 14) & s["wkts_before"].between(3, 5)]
    lo = near[near["runs_needed"] <= 12]["wp_before"].mean()
    hi = near[near["runs_needed"] >= 30]["wp_before"].mean()
    assert lo > hi


def test_feature_builders_shapes():
    x = _chase_features([30], [18], [5], [1])
    assert x.shape == (1, 5) and x[0, 3] == 10.0      # required rate
    y = _first_features([100], [60], [8], [0])
    assert y.shape == (1, 4)


def test_current_ball_outcome_does_not_change_its_pressure(deliveries):
    """Pressure is computed from pre-ball state: flipping a ball's outcome must not move it."""
    from src.pressure_model import compute_pressure
    m = deliveries["match_id"].iloc[0]
    one = deliveries[deliveries["match_id"] == m].copy()
    base = compute_pressure(one)
    tweak = one.copy()
    i = tweak.index[10]
    tweak.loc[i, ["bat_runs", "total_runs", "wpa", "wp_after"]] = [6, 6, 0.3, 0.9]
    tweak.loc[i, "team_wicket"] = not bool(tweak.loc[i, "team_wicket"])
    out = compute_pressure(tweak)
    assert np.isclose(base.loc[i, "pressure_raw"], out.loc[i, "pressure_raw"])


def test_extreme_examples_are_live_contests(deliveries):
    top = deliveries.nlargest(200, "pressure_raw")
    assert top["wp_before"].between(0.2, 0.8).mean() > 0.9
    assert pd.Series(top["innings"]).eq(2).mean() > 0.5
