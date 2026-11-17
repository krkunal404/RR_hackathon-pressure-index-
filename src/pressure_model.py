"""Pressure detection model.

Pressure on a delivery is defined as *how much the match outcome hinges on it*,
judged only from the pre-delivery state:

1. Win-probability (WP) models estimate P(batting side wins | state).
   * Innings 2 (chase): runs needed, balls left, wickets left, required rate.
   * Innings 1 (no target): runs so far, balls left, wickets left, scoring rate.
   Both are monotone-constrained gradient-boosted classifiers (a logistic
   regression is kept as a transparent benchmark), fitted with 5-fold cross-fitting
   grouped by match, so a match's own result never informs its own WP.
2. Components (each in [0, 1]):
   * leverage  - WP swing between the ball going well (a four) and badly
                 (a wicket). High when one ball can change the game.
   * closeness - (1 - |2*WP - 1|) x match progress. High when the contest
                 is 50/50 *and* little time remains to recover.
   * stress    - target difficulty (required rate above par) and a recent
                 collapse (wickets in the previous 24 deliveries).
3. raw = 0.55*leverage + 0.30*closeness + 0.15*stress, x1.15 in knockouts.
   The 0-100 score is the within-innings percentile of `raw`, so first-innings
   pressure is judged against first-innings norms rather than chases.

Because a dead-rubber death over has WP ~ 0 or 1, both leverage and closeness
collapse towards zero - final-over balls are *not* automatically "high".
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config as C

N_FOLDS = 5


# ---------------------------------------------------------------- features
# Raw state variables only; monotonic constraints encode cricket logic:
# chase WP falls with runs needed / required rate and rises with balls & wickets
# in hand; first-innings WP rises with runs, balls and wickets in hand.
CHASE_MONO = [-1, 1, 1, -1, 0]
FIRST_MONO = [1, 1, 1, 0]


def _chase_features(runs_needed, balls_left, wkts_left, is_ipl):
    rn = np.asarray(runs_needed, float)
    bl = np.clip(np.asarray(balls_left, float), 1, None)
    rrr = np.clip(rn * 6 / bl, 0, 36)
    return np.column_stack([rn, bl, np.asarray(wkts_left, float), rrr, np.asarray(is_ipl, float)])


def _first_features(runs_before, balls_left, wkts_left, is_ipl):
    return np.column_stack([np.asarray(runs_before, float), np.clip(np.asarray(balls_left, float), 0, 120),
                            np.asarray(wkts_left, float), np.asarray(is_ipl, float)])


def _model(inn: int):
    return HistGradientBoostingClassifier(
        monotonic_cst=CHASE_MONO if inn == 2 else FIRST_MONO, learning_rate=0.05, max_iter=300,
        max_leaf_nodes=31, min_samples_leaf=300, l2_regularization=1.0, random_state=C.SEED)


def _benchmark_model():
    """Transparent logistic benchmark reported alongside the main model."""
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))


def _fold(match_id: pd.Series) -> np.ndarray:
    return (match_id.values * 2654435761 % 2**32) % N_FOLDS


# ---------------------------------------------------------------- WP fitting
class WinProbModel:
    """Cross-fitted chase and first-innings WP models."""

    def __init__(self):
        self.models: dict[tuple[int, int], object] = {}
        self.benchmark: dict[int, object] = {}
        self.metrics: dict = {}

    def fit(self, d: pd.DataFrame) -> "WinProbModel":
        d = d[d["batting_team_won"].notna() & ~d["is_dls"]]
        folds = _fold(d["match_id"])
        for inn in (1, 2):
            mask_inn = (d["innings"] == inn).values
            X = self._X(d[mask_inn], inn)
            y = d.loc[mask_inn, "batting_team_won"].values
            f = folds[mask_inn]
            for k in range(N_FOLDS):
                self.models[(inn, k)] = _model(inn).fit(X[f != k], y[f != k])
            self.benchmark[inn] = _benchmark_model().fit(X, y)
        return self

    @staticmethod
    def _X(d, inn):
        if inn == 2:
            return _chase_features(d["runs_needed"], d["balls_left"], d["wkts_left"], d["is_ipl"])
        return _first_features(d["runs_before"], d["balls_left"], d["wkts_left"], d["is_ipl"])

    def _predict_state(self, inn, k, **s):
        feats = _chase_features if inn == 2 else _first_features
        keys = (["runs_needed", "balls_left", "wkts_left", "is_ipl"] if inn == 2
                else ["runs_before", "balls_left", "wkts_left", "is_ipl"])
        return self.models[(inn, k)].predict_proba(feats(*[s[x] for x in keys]))[:, 1]

    def annotate(self, d: pd.DataFrame) -> pd.DataFrame:
        """Add wp_before, wp_if_four, wp_if_wicket, wp_after for every delivery."""
        d = d.copy()
        out = {c: np.full(len(d), np.nan) for c in ["wp_before", "wp_if_four", "wp_if_wicket", "wp_after"]}
        folds = _fold(d["match_id"])
        for inn in (1, 2):
            for k in range(N_FOLDS):
                idx = np.where((d["innings"].values == inn) & (folds == k))[0]
                if not len(idx):
                    continue
                s = d.iloc[idx]
                bl, wl, ipl = s["balls_left"].values, s["wkts_left"].values, s["is_ipl"].values
                runs_after = s["runs_before"].values + s["total_runs"].values
                wl_after = wl - s["team_wicket"].values.astype(int)
                bl_after = bl - s["is_legal"].values.astype(int)
                if inn == 2:
                    rn = s["runs_needed"].values
                    p0 = self._predict_state(2, k, runs_needed=rn, balls_left=bl, wkts_left=wl, is_ipl=ipl)
                    p4 = self._predict_state(2, k, runs_needed=np.clip(rn - 4, 1, None), balls_left=np.clip(bl - 1, 1, None), wkts_left=wl, is_ipl=ipl)
                    p4 = np.where(rn <= 4, 1.0, np.where(bl - 1 <= 0, 0.0, p4))
                    pw = self._predict_state(2, k, runs_needed=rn, balls_left=np.clip(bl - 1, 1, None), wkts_left=np.clip(wl - 1, 1, None), is_ipl=ipl)
                    pw = np.where((wl - 1 <= 0) | (bl - 1 <= 0), 0.0, pw)
                    rn_after = s["target"].values - runs_after
                    pa = self._predict_state(2, k, runs_needed=np.clip(rn_after, 1, None), balls_left=np.clip(bl_after, 1, None), wkts_left=np.clip(wl_after, 1, None), is_ipl=ipl)
                    pa = np.where(rn_after <= 0, 1.0, np.where((wl_after <= 0) | (bl_after <= 0), 0.0, pa))
                else:
                    rb = s["runs_before"].values
                    p0 = self._predict_state(1, k, runs_before=rb, balls_left=bl, wkts_left=wl, is_ipl=ipl)
                    p4 = self._predict_state(1, k, runs_before=rb + 4, balls_left=bl - 1, wkts_left=wl, is_ipl=ipl)
                    # all out ends the innings: freeze the total (0 balls left, 1 "wicket" = no resource)
                    pw = self._predict_state(1, k, runs_before=rb, balls_left=np.where(wl - 1 <= 0, 0, bl - 1), wkts_left=np.clip(wl - 1, 0, None), is_ipl=ipl)
                    pa = self._predict_state(1, k, runs_before=runs_after, balls_left=np.where(wl_after <= 0, 0, bl_after), wkts_left=np.clip(wl_after, 0, None), is_ipl=ipl)
                out["wp_before"][idx], out["wp_if_four"][idx] = p0, p4
                out["wp_if_wicket"][idx], out["wp_after"][idx] = pw, pa
        for c, v in out.items():
            d[c] = v
        d["wpa"] = d["wp_after"] - d["wp_before"]           # batting-side win prob added
        return d

    def evaluate(self, d: pd.DataFrame) -> dict:
        """Out-of-fold discrimination & calibration, plus a season hold-out test."""
        res = {}
        e = d[d["batting_team_won"].notna() & ~d["is_dls"]]
        for inn in (1, 2):
            s = e[e["innings"] == inn]
            y, p = s["batting_team_won"].values, s["wp_before"].values
            bins = pd.cut(p, np.linspace(0, 1, 11), include_lowest=True)
            cal = pd.DataFrame({"p": p, "y": y}).groupby(bins, observed=True).agg(pred=("p", "mean"), obs=("y", "mean"), n=("y", "size"))
            res[f"innings_{inn}"] = {
                "auc": float(roc_auc_score(y, p)), "brier": float(brier_score_loss(y, p)),
                "log_loss": float(log_loss(y, p)), "n": int(len(s)),
                "calibration": cal.reset_index(drop=True).round(4).to_dict("records"),
            }
            # temporal hold-out: train <= 2024, test 2025-26
            tr, te = s[s["season_year"] <= 2024], s[s["season_year"] >= 2025]
            X = self._X
            mdl = _model(inn).fit(X(tr, inn), tr["batting_team_won"].values)
            pt = mdl.predict_proba(X(te, inn))[:, 1]
            res[f"innings_{inn}"]["holdout_2025_26_auc"] = float(roc_auc_score(te["batting_team_won"], pt))
            res[f"innings_{inn}"]["holdout_2025_26_brier"] = float(brier_score_loss(te["batting_team_won"], pt))
        for inn in (1, 2):
            s = e[e["innings"] == inn]
            pb = self.benchmark[inn].predict_proba(self._X(s, inn))[:, 1]
            res[f"innings_{inn}"]["logistic_benchmark_auc_in_sample"] = float(roc_auc_score(s["batting_team_won"], pb))
            res[f"innings_{inn}"]["logistic_benchmark_brier_in_sample"] = float(brier_score_loss(s["batting_team_won"], pb))
        return res


# ---------------------------------------------------------------- pressure index
def _pct_within(x: pd.Series, by: pd.Series) -> pd.Series:
    return x.groupby(by).rank(pct=True) * 100


def compute_pressure(d: pd.DataFrame, weights: dict | None = None,
                     knockout_mult: float = C.KNOCKOUT_MULTIPLIER) -> pd.DataFrame:
    w = weights or C.PRESSURE_WEIGHTS
    d = d.copy()
    lev = (d["wp_if_four"] - d["wp_if_wicket"]).clip(lower=0)
    p99 = lev.groupby(d["innings"]).transform(lambda s: s.quantile(0.99))
    d["leverage"] = lev
    d["c_leverage"] = (lev / p99).clip(0, 1)
    # a 50/50 contest only creates pressure once little time is left to recover:
    # weight closeness by the share of the match already played (0 -> 1).
    progress = ((d["legal_before"] / d["innings_balls"]).clip(0, 1) + (d["innings"] - 1)) / 2
    d["match_progress"] = progress
    d["c_closeness"] = (1 - (2 * d["wp_before"] - 1).abs()) * progress

    # recent collapse: wickets in the previous 24 deliveries of this innings
    g = d.groupby(["match_id", "innings"], sort=False)["team_wicket"]
    recent = g.transform(lambda s: s.astype(int).shift(1, fill_value=0).rolling(24, min_periods=1).sum())
    d["recent_wkts"] = recent
    collapse = (recent / 3).clip(0, 1)
    target_diff = ((d["rrr"] - 7.5) / 7.5).clip(0, 1).fillna(0)
    d["c_stress"] = np.maximum(collapse, target_diff)

    raw = w["leverage"] * d["c_leverage"] + w["closeness"] * d["c_closeness"] + w["stress"] * d["c_stress"]
    raw = raw * np.where(d["knock_out"].eq(1), knockout_mult, 1.0)
    d["pressure_raw"] = raw
    d["pressure_bat"] = _pct_within(raw, d["innings"])

    # bowling view: same match pressure + bowler-specific spell stress
    econ = np.where(d["bowler_balls_before"] >= 6,
                    d["bowler_runs_before"] * 6 / d["bowler_balls_before"].clip(lower=1), 7.5)
    d["c_spell"] = np.clip((econ - 7.5) / 6, 0, 1)
    sb = C.BOWLING_SPELL_WEIGHT
    raw_b = (1 - sb) * raw + sb * d["c_spell"]
    d["pressure_raw_bowl"] = raw_b
    d["pressure_bowl"] = _pct_within(raw_b, d["innings"])

    for col in ("bat", "bowl"):
        d[f"pcat_{col}"] = pd.cut(d[f"pressure_{col}"], C.PRESSURE_BINS, labels=C.PRESSURE_LABELS,
                                  right=False).astype(str)
        d[f"is_pressure_{col}"] = d[f"pressure_{col}"] >= C.PRESSURE_THRESHOLD
    return d
