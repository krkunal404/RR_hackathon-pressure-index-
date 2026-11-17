"""Accounting rules: legal balls, bowler attribution, scope and leakage-free state."""
import numpy as np


def test_scope_excludes_super_overs_and_a_team_events(built):
    d, m = built
    assert set(d["innings"].unique()) <= {1, 2}
    assert set(d["competition"].unique()) == {"IPL", "T20I"}
    assert not d["comp_name"].str.contains("Emerging|Rising Stars").any()


def test_illegal_deliveries_not_legal(built):
    d, _ = built
    assert not (d["extras_type"].isin(["wide", "Overstep", "other"]) & d["is_legal"]).any()
    assert not (d["is_wide"] & d["ball_faced"]).any()
    legal_per_over = d[d["is_legal"]].groupby(["match_id", "innings", "overid"]).size()
    assert (legal_per_over <= 6).mean() > 0.999


def test_bowler_runs_exclude_byes_and_include_wides(built):
    d, _ = built
    byes = d[d["extras_type"].isin(["byes", "legbyes"])]
    assert (byes["bowler_runs"] == byes["bat_runs"]).all()
    wides = d[d["is_wide"]]
    assert (wides["bowler_runs"] == wides["bat_runs"] + wides["extras1_runs"]).all()
    assert (wides["extras1_runs"] >= 1).all()


def test_extra_runs_use_recorded_amounts(built):
    d, _ = built
    pen = d[d["extras_type"] == "Penalty"]
    assert (pen["extra_runs"] == 5).all() and (pen["bowler_runs"] == pen["bat_runs"]).all()
    assert (d.loc[d["is_wide"], "extra_runs"] > 1).any()   # multi-run wides are recorded
    nb = d[d["is_noball"]]
    assert (nb["extra_runs"] == nb["extras1_runs"] + nb["extras_2_runs"]).all()


def test_bowler_wicket_credit(built):
    d, _ = built
    assert not (d["dismissal_type"].eq("RunOut") & d["bowler_wicket"]).any()
    assert not (d["bowler_wicket"] & ~d["team_wicket"]).any()
    assert d.groupby(["match_id", "innings"])["team_wicket"].sum().max() <= 10


def test_pre_ball_state_uses_only_earlier_deliveries(built):
    d, _ = built
    g = d.groupby(["match_id", "innings"], sort=False)
    exp_runs = g["total_runs"].transform(lambda s: s.shift(1, fill_value=0).cumsum())
    exp_wkts = g["team_wicket"].transform(lambda s: s.astype(int).shift(1, fill_value=0).cumsum())
    assert (exp_runs == d["runs_before"]).all()
    assert (exp_wkts == d["wkts_before"]).all()
    first = d.groupby(["match_id", "innings"]).head(1)
    assert (first["runs_before"] == 0).all() and (first["wkts_before"] == 0).all()


def test_margin_reconstruction_is_unbiased(built):
    from src.validation import accounting_checks
    d, m = built
    mr = accounting_checks(d, m)["margin_reconstruction"]
    assert abs(mr["mean_error"]) < 1.0
    assert mr["within_7"] > 0.9


def test_competition_weights(built):
    d, _ = built
    assert np.allclose(d.loc[d["competition"] == "IPL", "comp_weight"], 1.0)
    assoc = d[d["comp_bucket"] == "T20I_ASSOC"]
    assert len(assoc) > 0 and np.allclose(assoc["comp_weight"], 0.6)
