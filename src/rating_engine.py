"""Generic pressure-rating engine used by both BPPI (batters) and BoPPI (bowlers).

Five components, each a context-adjusted per-ball rate on *pressure* deliveries
(competition-weighted, empirical-Bayes shrunk):

    scoring/economy  runs above (batter) or saved vs (bowler) expected
    survival/wickets dismissals avoided (batter) or wickets above expected (bowler)
    impact           win-probability added
    uplift           pressure value - the player's own normal-situation value
    consistency      share of pressure matches with non-negative value (beta-shrunk)

Shrunk components are centred on the eligible pool and scaled by the spread
of the *raw* metric (so noisy components self-discount), combined with transparent
weights, and mapped to 0-100 with the normal CDF. Players below the sample
thresholds, or outside the IPL auction pool (see auction.py), are reported but
never ranked.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config as C
from .reliability import beta_shrink, cluster_bootstrap, estimate_beta_strength, estimate_k, reliability_score, shrink, to_index


@dataclass
class RoleSpec:
    role: str                 # "bat" | "bowl"
    player_col: str
    name_col: str
    rows: pd.Series           # boolean mask of deliveries that count for the role
    count_col: str            # column counted as a "ball" for eligibility
    pressure_col: str
    v_score: pd.Series
    v_surv: pd.Series
    v_impact: pd.Series
    comp_names: tuple[str, str, str, str, str]
    weights: dict
    min_balls: int


COLS = ["n", "nw", "s_score", "s_surv", "s_imp", "nw_norm", "s_score_norm", "s_surv_norm"]


def _match_table(d: pd.DataFrame, spec: RoleSpec, thr: float) -> pd.DataFrame:
    x = d.loc[spec.rows].copy()
    w = x["comp_weight"]
    p = x[spec.pressure_col] >= thr
    x["_p"] = p
    x["n"] = (p & x[spec.count_col]).astype(int)
    x["nw"] = np.where(p, w, 0.0)
    x["s_score"] = np.where(p, w * spec.v_score.loc[x.index], 0.0)
    x["s_surv"] = np.where(p, w * spec.v_surv.loc[x.index], 0.0)
    x["s_imp"] = np.where(p, w * spec.v_impact.loc[x.index].fillna(0), 0.0)
    x["nw_norm"] = np.where(~p, w, 0.0)
    x["s_score_norm"] = np.where(~p, w * spec.v_score.loc[x.index], 0.0)
    x["s_surv_norm"] = np.where(~p, w * spec.v_surv.loc[x.index], 0.0)
    return x.groupby([spec.player_col, "match_id"])[COLS].sum().reset_index()


def rate(d: pd.DataFrame, spec: RoleSpec, lam: float, thr: float = C.PRESSURE_THRESHOLD,
         bootstrap: bool = True, min_matches: int = C.MIN_PRESSURE_MATCHES) -> tuple[pd.DataFrame, dict]:
    mt = _match_table(d, spec, thr)
    pl = mt.groupby(spec.player_col)[COLS].sum()
    pm = mt[mt["n"] > 0].groupby(spec.player_col).size()
    pl["pressure_matches"] = pm.reindex(pl.index).fillna(0).astype(int)
    pl["matches"] = mt.groupby(spec.player_col).size()

    # --- prior strengths ----------------------------------------------------
    # True-talent spread is estimated from ALL of a player's deliveries (larger,
    # more stable samples) and then applied to the pressure-only rates.
    x = d.loc[spec.rows]
    w = x["comp_weight"]
    val_ball = spec.v_score.loc[x.index] + lam * spec.v_surv.loc[x.index]
    series = {"score": spec.v_score.loc[x.index], "surv": spec.v_surv.loc[x.index],
              "imp": spec.v_impact.loc[x.index].fillna(0), "val": val_ball}
    ks = {}
    for key, v in series.items():
        g = pd.DataFrame({"s": v * w, "n": w, "p": x[spec.player_col]}).groupby("p").sum()
        ks[key] = estimate_k(g["s"], g["n"], float(np.average((v - np.average(v, weights=w)) ** 2, weights=w)))

    # --- consistency: per-match value >= 0 on matches with enough pressure balls
    mt["val"] = (mt.s_score + lam * mt.s_surv) / mt.nw.replace(0, np.nan)
    cm = mt[mt["n"] >= C.MIN_BALLS_IN_MATCH_FOR_CONSISTENCY]
    cons = cm.assign(ok=cm["val"] >= 0).groupby(spec.player_col)["ok"].agg(["sum", "size"])
    pl["cons_ok"] = cons["sum"].reindex(pl.index).fillna(0)
    pl["cons_n"] = cons["size"].reindex(pl.index).fillna(0)

    sample_ok = (pl["n"] >= spec.min_balls) & (pl["pressure_matches"] >= min_matches)
    excl_col = f"{spec.role}_exclusion"
    if excl_col in d:
        reason = d.loc[spec.rows].groupby(spec.player_col)[excl_col].first().reindex(pl.index)
    else:
        reason = pd.Series(None, index=pl.index, dtype=object)
    eligible = sample_ok & reason.isna()
    pl["sample_ok"] = sample_ok
    pl["exclusion"] = reason.where(reason.notna(), np.where(sample_ok, None, "Below sample bar"))

    # --- uplift reliability: "clutch" = pressure value - own normal value.
    # Shrink the raw difference by tau2 / (tau2 + sampling variance), with tau2
    # (true spread of clutch effects) estimated by method of moments.
    var_val = float(np.average((val_ball - np.average(val_ball, weights=w)) ** 2, weights=w))
    both = (pl.nw >= 100) & (pl.nw_norm >= 100)
    diff = (pl.s_score + lam * pl.s_surv) / pl.nw - (pl.s_score_norm + lam * pl.s_surv_norm) / pl.nw_norm
    samp = var_val * (1 / pl.nw + 1 / pl.nw_norm)
    tau2_up = max(float(diff[both].var() - samp[both].mean()), 1e-9)
    prior_cons = float(pl.loc[eligible, "cons_ok"].sum() / max(pl.loc[eligible, "cons_n"].sum(), 1))
    cons_strength = estimate_beta_strength(pl["cons_ok"], pl["cons_n"])

    def components(nw, s_score, s_surv, s_imp, nw_n, s_score_n, s_surv_n, c_ok, c_n, raw=False):
        f = 0.0 if raw else 1.0
        sc = shrink(s_score, nw, f * ks["score"])
        sv = shrink(s_surv, nw, f * ks["surv"])
        im = shrink(s_imp, nw, f * ks["imp"])
        nw_s, nwn_s = np.maximum(nw, 1e-9), np.maximum(nw_n, 1e-9)
        raw_up = np.where((nw > 0) & (nw_n > 0),
                          (s_score + lam * s_surv) / nw_s - (s_score_n + lam * s_surv_n) / nwn_s, 0.0)
        up = raw_up if raw else raw_up * tau2_up / (tau2_up + var_val * (1 / nw_s + 1 / nwn_s))
        co = beta_shrink(c_ok, c_n, prior_cons, strength=0.0 if raw else cons_strength)
        return np.stack([sc, sv, im, up, co], axis=-1)

    comp = components(pl.nw, pl.s_score, pl.s_surv, pl.s_imp, pl.nw_norm, pl.s_score_norm,
                      pl.s_surv_norm, pl.cons_ok, pl.cons_n)
    # Standardise shrunk components by the spread of the RAW metric, so a noisy
    # (heavily shrunk) component carries proportionally less weight.
    comp_raw = components(pl.nw, pl.s_score, pl.s_surv, pl.s_imp, pl.nw_norm, pl.s_score_norm,
                          pl.s_surv_norm, pl.cons_ok, pl.cons_n, raw=True)
    mu, sd = comp[eligible.values].mean(0), comp_raw[eligible.values].std(0)
    wv = np.array([spec.weights[c] for c in spec.weights])
    z = (comp - mu) / sd
    composite = z @ wv
    cmin, cmax = composite[eligible.values].min(), composite[eligible.values].max()
    pl["rating"] = to_index(composite, cmin, cmax)
    for i, name in enumerate(spec.comp_names):
        pl[f"c_{name}"] = comp[:, i]
        pl[f"z_{name}"] = z[:, i]
        pl[f"raw_{name}"] = comp_raw[:, i]
    pl["eligible"] = eligible
    pl["reliability"] = reliability_score(pl["n"], ks["val"], pl["pressure_matches"])

    # --- match-level cluster bootstrap for 90% intervals ---------------------
    pl["rating_lo"] = np.nan
    pl["rating_hi"] = np.nan
    if bootstrap:
        rng = np.random.default_rng(C.SEED)
        mt["ok"] = (mt["n"] >= C.MIN_BALLS_IN_MATCH_FOR_CONSISTENCY) & (mt["val"] >= 0)
        mt["cn"] = (mt["n"] >= C.MIN_BALLS_IN_MATCH_FOR_CONSISTENCY).astype(float)
        bcols = ["nw", "s_score", "s_surv", "s_imp", "nw_norm", "s_score_norm", "s_surv_norm", "ok", "cn"]

        def scorer(T):
            c = components(*[T[:, i] for i in range(T.shape[1])])
            return 100 * ((((c - mu) / sd) @ wv) - cmin) / (cmax - cmin)    # unclipped

        dists = {}
        for pid, g in mt[mt[spec.player_col].isin(pl.index[eligible])].groupby(spec.player_col):
            dist = cluster_bootstrap(g[bcols].astype(float).values, scorer, C.BOOTSTRAP_REPS, rng)
            dists[pid] = dist
            pl.loc[pid, ["rating_lo", "rating_hi"]] = np.percentile(dist, [5, 95])
        # probability of a top-10 finish across bootstrap worlds
        ids = list(dists)
        mat = np.vstack([dists[i] for i in ids])
        ranks = (-mat).argsort(0).argsort(0) + 1
        pl["p_top10"] = np.nan
        pl.loc[ids, "p_top10"] = (ranks <= 10).mean(1)
        pl.loc[ids, "rank_lo"] = np.percentile(ranks, 5, axis=1)
        pl.loc[ids, "rank_hi"] = np.percentile(ranks, 95, axis=1)

    pl["rank"] = np.nan
    order = pl[eligible].sort_values("rating", ascending=False).index
    pl.loc[order, "rank"] = np.arange(1, len(order) + 1)
    meta = {"k": ks, "lambda": lam, "uplift_tau2": tau2_up,
            "uplift_reliability_at_200_balls": tau2_up / (tau2_up + var_val * (1 / 200 + 1 / 400)), "prior_consistency": prior_cons, "consistency_prior_strength": cons_strength, "eligible": int(eligible.sum()),
            "pool": int(len(pl)), "component_mean": dict(zip(spec.comp_names, mu.round(5).tolist())),
            "component_sd_raw": dict(zip(spec.comp_names, sd.round(5).tolist())),
            "component_signal_share": dict(zip(spec.comp_names, (comp[eligible.values].std(0) / sd).round(3).tolist()))}
    return pl.reset_index().rename(columns={spec.player_col: "player_id"}), meta
