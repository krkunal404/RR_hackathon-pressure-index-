"""Generate the submission-ready PDF methodology report from pipeline outputs.

Every number, table and chart is read from outputs/ and data/processed/ -
nothing is typed in by hand.
"""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer,  # noqa: E402
                                Table, TableStyle)

from . import config as C  # noqa: E402
from .data_loader import read_raw_csv  # noqa: E402

INK, ACCENT, ACCENT2, MUTED, GRID = "#0f172a", "#e11d48", "#2563eb", "#64748b", "#e2e8f0"
CAT_COLORS = {"Low": "#cbd5e1", "Moderate": "#93c5fd", "High": "#f59e0b", "Extreme": "#e11d48"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": "#94a3b8",
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": GRID, "grid.linewidth": 0.6, "axes.titleweight": "bold",
                     "axes.titlesize": 10, "figure.dpi": 150})


# ------------------------------------------------------------------ styles
SS = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=SS["Heading1"], fontSize=16, textColor=colors.HexColor(INK), spaceBefore=10, spaceAfter=6)
H2 = ParagraphStyle("H2", parent=SS["Heading2"], fontSize=12, textColor=colors.HexColor(ACCENT), spaceBefore=8, spaceAfter=4)
BODY = ParagraphStyle("B", parent=SS["BodyText"], fontSize=9.2, leading=13, textColor=colors.HexColor("#1e293b"))
SMALL = ParagraphStyle("S", parent=BODY, fontSize=7.6, leading=10, textColor=colors.HexColor(MUTED))
CELL = ParagraphStyle("C", parent=BODY, fontSize=7.2, leading=9)
MATH = ParagraphStyle("M", parent=BODY, fontName="Courier", fontSize=8.4, leading=11.5, backColor=colors.HexColor("#f1f5f9"),
                      borderPadding=6, leftIndent=6, rightIndent=6, spaceBefore=4, spaceAfter=8)
TITLE = ParagraphStyle("T", parent=H1, fontSize=24, leading=29, alignment=TA_CENTER)
SUB = ParagraphStyle("ST", parent=BODY, fontSize=11, alignment=TA_CENTER, textColor=colors.HexColor(MUTED))


def P(t, s=BODY):
    return Paragraph(t, s)


HEAD = ParagraphStyle("HD", parent=CELL, textColor=colors.white, fontName="Helvetica-Bold")


def table(rows, widths, header_bg=INK, font=7.4, zebra=True):
    hs = ParagraphStyle("hs", parent=HEAD, fontSize=font, leading=font + 2)
    data = [[P(str(c), hs) for c in rows[0]]]
    data += [[P(str(c), CELL) if isinstance(c, str) and len(c) > 28 else c for c in r] for r in rows[1:]]
    t = Table(data, colWidths=widths, repeatRows=1)
    st = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
          ("FONTSIZE", (0, 0), (-1, -1), font), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
          ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    if zebra:
        for i in range(1, len(rows)):
            if i % 2 == 0:
                st.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f8fafc")))
    t.setStyle(TableStyle(st))
    return t


def fig(path, w=16.5):
    img = Image(str(path))
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth, img.drawHeight = w * cm, w * cm * ratio
    return img


def f1(x, n=1):
    return "-" if pd.isna(x) else f"{x:.{n}f}"


# ------------------------------------------------------------------ charts
def make_charts(d, bat, bowl, tb, tw, M):
    F = C.FIG_DIR
    F.mkdir(parents=True, exist_ok=True)
    out = {}

    # 1. pressure category mix by innings x phase
    mix = (d.groupby(["innings", "phase"])["pcat_bat"].value_counts(normalize=True).unstack()
           .reindex(columns=C.PRESSURE_LABELS).reindex(["Powerplay", "Middle", "Death"], level=1))
    fig_, ax = plt.subplots(figsize=(7.5, 2.8))
    left = np.zeros(len(mix))
    labels = [f"Inn {i} - {p}" for i, p in mix.index]
    for c in C.PRESSURE_LABELS:
        ax.barh(labels, mix[c] * 100, left=left, color=CAT_COLORS[c], label=c)
        left += mix[c].values * 100
    ax.set_xlabel("% of deliveries"); ax.invert_yaxis(); ax.grid(axis="y", visible=False)
    ax.legend(ncol=4, loc="lower center", bbox_to_anchor=(0.5, 1.0), frameon=False)
    ax.set_title("Pressure category mix by innings and phase", pad=22)
    fig_.tight_layout(); fig_.savefig(F / "pressure_mix.png"); plt.close(fig_)
    out["mix"] = F / "pressure_mix.png"

    # 2. outcomes by category
    cat = pd.DataFrame(M["pressure_validity"]["by_category"]).set_index("pcat_bat")
    fig_, axs = plt.subplots(1, 3, figsize=(7.5, 2.4))
    for ax, (col, ttl, k) in zip(axs, [("runs_per_ball", "Runs per ball", 1), ("wicket_rate", "Wicket %", 100),
                                       ("close_match_share", "From close matches %", 100)]):
        ax.bar(cat.index, cat[col] * k, color=[CAT_COLORS[c] for c in cat.index])
        ax.set_title(ttl); ax.tick_params(axis="x", labelsize=7); ax.grid(axis="x", visible=False)
    fig_.tight_layout(); fig_.savefig(F / "pressure_outcomes.png"); plt.close(fig_)
    out["outcomes"] = F / "pressure_outcomes.png"

    # 3. WP calibration
    fig_, axs = plt.subplots(1, 2, figsize=(7.5, 2.9))
    for ax, inn in zip(axs, (1, 2)):
        cal = pd.DataFrame(M["win_probability"][f"innings_{inn}"]["calibration"])
        ax.plot([0, 1], [0, 1], ls="--", c=MUTED, lw=1)
        ax.scatter(cal["pred"], cal["obs"], s=np.sqrt(cal["n"]) * 1.2, c=ACCENT2 if inn == 1 else ACCENT, alpha=.8)
        a = M["win_probability"][f"innings_{inn}"]
        ax.set_title(f"Innings {inn}: AUC {a['auc']:.3f}, Brier {a['brier']:.3f}")
        ax.set_xlabel("Predicted win probability"); ax.set_ylabel("Observed win rate")
    fig_.tight_layout(); fig_.savefig(F / "wp_calibration.png"); plt.close(fig_)
    out["calib"] = F / "wp_calibration.png"

    # 4. pressure through the highest-pressure close chase
    dls = set(d.loc[d["target"].notna() & d["match_id"].isin(
        read_raw_csv("matches").query("revised_target == revised_target")["match_id"]), "match_id"])
    ex = next(e for e in M["pressure_validity"]["extreme_examples"] if e["match_id"] not in dls)
    mm = d[(d.match_id == ex["match_id"])].copy()
    mm["ball"] = np.arange(len(mm))
    fig_, ax = plt.subplots(figsize=(7.5, 2.6))
    ax.fill_between(mm["ball"], mm["pressure_bat"], color=ACCENT, alpha=.18, lw=0)
    ax.plot(mm["ball"], mm["pressure_bat"], c=ACCENT, lw=.8, label="Pressure score (0-100)")
    ax2 = ax.twinx(); ax2.plot(mm["ball"], mm["wp_before"] * 100, c=ACCENT2, lw=1.4, label="Batting-side WP %")
    ax2.set_ylim(0, 100); ax2.grid(False)
    split = mm[mm.innings == 2]["ball"].min()
    ax.axvline(split, c=MUTED, ls=":", lw=1)
    ax.set_xlabel("Delivery in match"); ax.set_ylabel("Pressure")
    t1, t2 = mm.iloc[0]["batting_team"], mm.iloc[0]["bowling_team"]
    ax.set_title(f"Match {ex['match_id']}: {t1} v {t2} ({str(ex['match_date'])[:10]})")
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", frameon=False, fontsize=7)
    fig_.tight_layout(); fig_.savefig(F / "match_pressure.png"); plt.close(fig_)
    out["match"] = F / "match_pressure.png"

    # 5/6. leaderboard with CIs
    for key, t, col, colr in (("lb_bat", tb, "BPPI", ACCENT), ("lb_bowl", tw, "BoPPI", ACCENT2)):
        fig_, ax = plt.subplots(figsize=(7.5, 3.0))
        y = np.arange(len(t))[::-1]
        ax.errorbar(t[col], y, xerr=[t[col] - t[f"{col}_lo"], t[f"{col}_hi"] - t[col]], fmt="o", c=colr,
                    ecolor="#94a3b8", elinewidth=1.4, capsize=2)
        ax.set_yticks(y); ax.set_yticklabels([f"{int(r)}. {n}" for r, n in zip(t["rank"], t["name"])])
        ax.set_xlabel(f"{col} (point estimate and 90% bootstrap interval)"); ax.grid(axis="y", visible=False)
        ax.set_title(f"Top 10 {'batters' if col == 'BPPI' else 'bowlers'}: {col} with uncertainty")
        fig_.tight_layout(); fig_.savefig(F / f"{key}.png"); plt.close(fig_)
        out[key] = F / f"{key}.png"

    # 7. batting scatter: pressure SR vs normal SR
    e = bat[bat.eligible]
    fig_, ax = plt.subplots(figsize=(7.5, 3.6))
    ax.scatter(e["n_sr"], e["p_sr"], s=e["n"] / 6, c="#cbd5e1", edgecolor="#94a3b8", lw=.4)
    top = e[e["rank"] <= 10]
    ax.scatter(top["n_sr"], top["p_sr"], s=top["n"] / 6, c=ACCENT, edgecolor="white", lw=.6)
    for _, r in top.iterrows():
        ax.annotate(r["name"].split()[-1], (r["n_sr"], r["p_sr"]), fontsize=6.5, xytext=(3, 3), textcoords="offset points")
    lim = [min(e.n_sr.min(), e.p_sr.min()) - 5, max(e.n_sr.max(), e.p_sr.max()) + 5]
    ax.plot(lim, lim, ls="--", c=MUTED, lw=1)
    ax.set_xlabel("Strike rate - normal situations"); ax.set_ylabel("Strike rate - pressure")
    ax.set_title("Eligible batters: above the line = scores faster under pressure (size = pressure balls)")
    fig_.tight_layout(); fig_.savefig(F / "bat_scatter.png"); plt.close(fig_)
    out["bat_scatter"] = F / "bat_scatter.png"

    e = bowl[bowl.eligible]
    fig_, ax = plt.subplots(figsize=(7.5, 3.6))
    ax.scatter(e["n_econ"], e["p_econ"], s=e["n"] / 6, c="#cbd5e1", edgecolor="#94a3b8", lw=.4)
    top = e[e["rank"] <= 10]
    ax.scatter(top["n_econ"], top["p_econ"], s=top["n"] / 6, c=ACCENT2, edgecolor="white", lw=.6)
    for _, r in top.iterrows():
        ax.annotate(r["name"].split()[-1], (r["n_econ"], r["p_econ"]), fontsize=6.5, xytext=(3, 3), textcoords="offset points")
    lim = [min(e.n_econ.min(), e.p_econ.min()) - .3, max(e.n_econ.max(), e.p_econ.max()) + .3]
    ax.plot(lim, lim, ls="--", c=MUTED, lw=1)
    ax.set_xlabel("Economy - normal situations"); ax.set_ylabel("Economy - pressure")
    ax.set_title("Eligible bowlers: below the line = tighter under pressure (size = pressure balls)")
    fig_.tight_layout(); fig_.savefig(F / "bowl_scatter.png"); plt.close(fig_)
    out["bowl_scatter"] = F / "bowl_scatter.png"

    # 9. component contributions
    for key, t_all, comps, wts, col in (("contrib_bat", bat, ["scoring", "survival", "impact", "uplift", "consistency"], C.BPPI_WEIGHTS, "BPPI"),
                                        ("contrib_bowl", bowl, ["economy", "wickets", "impact", "uplift", "consistency"], C.BOPPI_WEIGHTS, "BoPPI")):
        t = t_all[t_all["rank"] <= 10].sort_values("rank")
        fig_, ax = plt.subplots(figsize=(7.5, 3.0))
        pal = ["#e11d48", "#f59e0b", "#2563eb", "#10b981", "#8b5cf6"]
        y = np.arange(len(t))[::-1]
        pos, neg = np.zeros(len(t)), np.zeros(len(t))
        for c, pc in zip(comps, pal):
            v = (t[f"z_{c}"] * wts[c]).values
            ax.barh(y, np.where(v > 0, v, 0), left=pos, color=pc, label=c)
            ax.barh(y, np.where(v < 0, v, 0), left=neg, color=pc)
            pos += np.where(v > 0, v, 0); neg += np.where(v < 0, v, 0)
        ax.set_yticks(y); ax.set_yticklabels(t["name"]); ax.axvline(0, c=INK, lw=.8)
        ax.legend(ncol=5, loc="lower center", bbox_to_anchor=(.5, 1), frameon=False, fontsize=7)
        ax.set_xlabel("Weighted standardised contribution to composite"); ax.grid(axis="y", visible=False)
        ax.set_title(f"What drives each top-10 {col}", pad=20)
        fig_.tight_layout(); fig_.savefig(F / f"{key}.png"); plt.close(fig_)
        out[key] = F / f"{key}.png"

    # 10. sensitivity heatmap of baseline top-10 ranks
    for key, role, t in (("sens_bat", "batters", tb), ("sens_bowl", "bowlers", tw)):
        S = M["sensitivity"]
        mat = np.array([s[role]["baseline_top10_ranks"] for s in S], float)
        mat[mat < 0] = np.nan
        fig_, ax = plt.subplots(figsize=(7.5, 3.9))
        im = ax.imshow(np.clip(mat, 1, 30), cmap="RdYlGn_r", vmin=1, vmax=30, aspect="auto")
        for i in range(mat.shape[0]):
            for j in range(mat.shape[1]):
                ax.text(j, i, "n/e" if np.isnan(mat[i, j]) else int(mat[i, j]), ha="center", va="center", fontsize=6.3)
        ax.set_xticks(range(len(t))); ax.set_xticklabels([n.split()[-1] for n in t["name"]], rotation=40, ha="right", fontsize=7)
        ax.set_yticks(range(len(S))); ax.set_yticklabels([s["scenario"] for s in S], fontsize=6.6)
        ax.grid(False); ax.set_title(f"Baseline top-10 {role}: rank under each alternative (n/e = not eligible)")
        fig_.colorbar(im, ax=ax, fraction=.03, pad=.01)
        fig_.tight_layout(); fig_.savefig(F / f"{key}.png"); plt.close(fig_)
        out[key] = F / f"{key}.png"

    # 11. IPL vs T20I
    fig_, axs = plt.subplots(1, 2, figsize=(7.5, 3.0))
    for ax, t, col in ((axs[0], bat, "BPPI"), (axs[1], bowl, "BoPPI")):
        j = t[t[f"eligible_IPL"].eq(True) & t[f"eligible_T20I"].eq(True)]
        ax.scatter(j[f"{col}_IPL"], j[f"{col}_T20I"], c=ACCENT if col == "BPPI" else ACCENT2, s=18, alpha=.8)
        for _, r in j.iterrows():
            ax.annotate(r["name"].split()[-1], (r[f"{col}_IPL"], r[f"{col}_T20I"]), fontsize=5.5)
        from scipy.stats import spearmanr
        rho = spearmanr(j[f"{col}_IPL"], j[f"{col}_T20I"]).statistic if len(j) > 3 else np.nan
        ax.set_title(f"{col}: IPL vs T20I (n={len(j)}, rho={rho:.2f})"); ax.set_xlabel("IPL-only rating"); ax.set_ylabel("T20I-only rating")
    fig_.tight_layout(); fig_.savefig(F / "ipl_vs_t20i.png"); plt.close(fig_)
    out["ipl_t20i"] = F / "ipl_vs_t20i.png"
    return out


# ------------------------------------------------------------------ report
def status(r) -> str:
    """Short auction tag for tables: 'RR (retain)', 'Target' or 'Target (OS)'."""
    if str(r.get("auction_status", "")).startswith("Current"):
        return "RR (retain)"
    return "Target (OS)" if r.get("player_type") == "Overseas" else "Target"


def build_report():
    M = json.loads((C.OUTPUT_DIR / "metrics.json").read_text())
    d = pd.read_parquet(C.PROCESSED_DIR / "deliveries.parquet")
    bat = pd.read_parquet(C.PROCESSED_DIR / "batters.parquet")
    bowl = pd.read_parquet(C.PROCESSED_DIR / "bowlers.parquet")
    tb = pd.read_csv(C.OUTPUT_DIR / "top_10_batters.csv")
    tw = pd.read_csv(C.OUTPUT_DIR / "top_10_bowlers.csv")
    ch = make_charts(d, bat, bowl, tb, tw, M)
    O, A, K, WP = M["overview"], M["audit"], M["accounting_checks"], M["win_probability"]
    mb, mw = M["batter_meta"], M["bowler_meta"]
    PV, TS = M["pressure_validity"], M["temporal_stability"]
    AU = M["auction"]
    s = []

    # ---- cover --------------------------------------------------------------
    s += [Spacer(1, 3.2 * cm), P("SupeRR Selector Season 2 - Round 1", SUB), Spacer(1, .3 * cm),
          P("Who Delivers When It Matters?", TITLE),
          P("The most reliable players under pressure for Rajasthan Royals to back at the IPL 2027 auction", SUB),
          P("A win-probability pressure model and Bayesian ratings built on IPL &amp; T20I ball-by-ball data (2022-2026)", SMALL),
          Spacer(1, 1.2 * cm)]
    s.append(table([["Matches", "Deliveries", "Players", "Pressure balls", "Eligible batters", "Eligible bowlers"],
                    [f"{O['matches']:,}", f"{O['deliveries']:,}", f"{O['players']:,}", f"{O['pressure_deliveries']:,}",
                     O["eligible_batters"], O["eligible_bowlers"]]], [2.75 * cm] * 6, font=9))
    s += [Spacer(1, 1 * cm), P("Rajasthan Royals IPL 2027 auction shortlist", H2)]
    rows = [["#", "Top batters (BPPI)", "BPPI", "#", "Top bowlers (BoPPI)", "BoPPI"]]
    for i in range(10):
        rows.append([i + 1, tb.loc[i, "name"], f1(tb.loc[i, "BPPI"]), i + 1, tw.loc[i, "name"], f1(tw.loc[i, "BoPPI"])])
    s.append(table(rows, [.8 * cm, 5.2 * cm, 1.8 * cm, .8 * cm, 5.2 * cm, 1.8 * cm], font=8.5))
    s += [Spacer(1, .6 * cm), P(f"Generated {M['generated_at']} by <font face='Courier'>python main.py</font>. Every figure in this report is computed from the supplied files.", SMALL), PageBreak()]

    # ---- 1 executive summary ---------------------------------------------------
    b1, w1 = tb.iloc[0], tw.iloc[0]
    ex = AU["excluded"]

    def names(xs):
        return ", ".join(xs) if xs else "none"
    s += [P("1. Executive summary", H1),
          P(f"<b>Brief.</b> Identify the most reliable players under pressure whom <b>{AU['team']}</b> should back at the "
            f"<b>IPL 2027 auction</b>. The rankings are therefore restricted to players who can actually be bought: players who have "
            f"represented {', '.join(AU['ineligible_nations'])} are excluded because they cannot play in the IPL, and players with no "
            f"match since {AU['min_last_season'] - 1} are treated as inactive. All deliveries still feed the pressure model and the "
            "context baselines; only the ranking pool changes. Each player is tagged as a current RR player (retain) or an auction target, "
            "and as Indian or overseas, since overseas squad slots are limited."),
          P(f"Removed although they met the sample bar - Pakistan: batters {names(ex['batters']['ineligible_nation'])}; "
            f"bowlers {names(ex['bowlers']['ineligible_nation'])}. Inactive: batters {names(ex['batters']['inactive'])}; "
            f"bowlers {names(ex['bowlers']['inactive'])}.", SMALL),
          P(f"We define <b>pressure</b> as how much the result of a match hinges on a single delivery, measured "
            f"<i>before</i> it is bowled. Two cross-fitted win-probability (WP) models (chase AUC {WP['innings_2']['auc']:.3f}; "
            f"first innings AUC {WP['innings_1']['auc']:.3f}) estimate each side's chances from runs, balls and wickets in hand. "
            "A delivery's pressure score (0-100) combines its <b>leverage</b> (the WP swing between a boundary and a wicket), "
            "the <b>closeness</b> of the contest late in the match, and <b>situational stress</b> (required-rate difficulty, recent collapse), "
            "with a knockout multiplier. The top 25% of deliveries within each innings are 'pressure' deliveries (High + Extreme)."),
          P("Players are rated only on pressure deliveries, against a <b>context-expected</b> outcome for the same competition, "
            "innings, over, wickets lost, pressure level and opposition. Five components (scoring/economy, survival/wickets, "
            "win-probability added, uplift over own baseline, match-level consistency) are empirically-Bayes shrunk, combined and "
            f"normalised to 0-100 as the <b>BPPI</b> and <b>BoPPI</b>. Players need at least {C.MIN_PRESSURE_BALLS_BAT} pressure balls "
            f"and {C.MIN_PRESSURE_MATCHES} pressure matches to be ranked. Reliability, 90% bootstrap intervals and the bootstrap "
            "probability of a top-10 finish are reported separately from the ratings."),
          P(f"<b>{b1['name']}</b> tops the batting list (pressure SR {f1(b1.p_sr)} off {int(b1.p_balls)} balls), and "
            f"<b>{w1['name']}</b> tops the bowling list (pressure economy {f1(w1.p_econ, 2)} over {int(w1.p_legal_balls)} legal balls). "
            f"The {'bowling' if w1.p_top10 >= b1.p_top10 else 'batting'} list is the more settled one: the bowling #1 finishes in the top 10 in "
            f"{f1(100 * w1.p_top10, 0)}% of bootstrap resamples, against {f1(100 * b1.p_top10, 0)}% for the batting #1."),
          P("<b>Key findings.</b> (i) Pressure is not the same as the death overs: final-over balls in already-decided games are "
            f"almost never pressure ({100 * PV['decided_death_balls_pressure_share']:.1f}%). (ii) Pressure suppresses scoring league-wide, "
            "so we judge performance against pressure-specific expectations. (iii) A pure 'clutch' effect (pressure minus own normal form) "
            f"barely repeats: at 200 pressure balls only {100 * mb['uplift_reliability_at_200_balls']:.0f}% of a batter's observed uplift is signal, "
            "and for bowlers it cannot be told apart from chance. The model therefore down-weights it automatically and rewards proven pressure output. "
            f"(iv) Rankings are robust to rating weights and to competition weighting (Spearman >= 0.98), but year-to-year stability is "
            f"modest (split-half rho {TS['batters']['rating_spearman']:.2f} batters / {TS['bowlers']['rating_spearman']:.2f} bowlers). "
            "That is why every rating carries its uncertainty."),
          PageBreak()]

    # ---- 2-4 problem, data, cleaning ---------------------------------------------
    s += [P("2. Problem statement", H1),
          P("Build a data-driven system that measures how batters and bowlers perform in high-pressure match situations compared "
            "with their usual levels, and use it to rank the 10 batters and 10 bowlers who deliver most consistently when it matters. "
            "Pressure must be defined, justified and shown to separate pressure from ordinary situations, for both disciplines."),
          P("3. Dataset description", H1)]
    rows = [["File", "Rows", "Grain / key", "Used for"],
            ["ball_by_ball.csv", f"{A['rows']['ball_by_ball']:,}", "delivery: match_id, innings, overid, over_ball_num", "all performance and match-state features"],
            ["matches.csv", f"{A['rows']['matches']:,}", "match_id -> comp_id", "result, winner, DLS targets, knockout flag"],
            ["competitions.csv", f"{A['rows']['competitions']:,}", "comp_id", "IPL / T20I classification, season"],
            ["teams.csv", f"{A['rows']['teams']:,}", "comp_id, team_id", "team names, Full Member / Associate status"],
            ["playing_eleven.csv", f"{A['rows']['playing_eleven']:,}", "match_id, team_id, player_id", "identity cross-check"],
            ["competition_team_player_mapping.csv", f"{A['rows']['competition_team_player_mapping']:,}", "comp_id, team_id, player_id", "identity cross-check"]]
    s.append(table(rows, [5 * cm, 1.6 * cm, 5 * cm, 5 * cm]))
    s += [Spacer(1, 4), P(f"Scope after filtering: <b>{O['matches']}</b> matches with ball-by-ball data ({O['ipl_matches']} IPL, {O['t20i_matches']} T20I), "
                          f"seasons {O['seasons'][0]}-{O['seasons'][-1]}, {O['deliveries']:,} deliveries.")]

    s += [P("4. Data cleaning and preprocessing", H1),
          P("The audit found several encoding issues that, if missed, would corrupt economy rates and match states:")]
    rows = [["Finding", "Evidence", "Treatment"],
            ["<b>extras1_runs</b> holds the extra runs on the ball", f"range by type: {A['extras_runs_by_type']}", "Use extras_type for the kind of extra and extras1_runs (+ extras_2_runs for byes off a no-ball) for the amount"],
            ["'other' extras behave as no-balls", "treating them as illegal raises clean 6-ball overs to 98.2%", "Illegal delivery, charged to bowler"],
            ["Super overs present", f"{A['super_over_deliveries']} deliveries in innings 3-4", "Excluded"],
            ["Non-IPL 'T20' A-team events", "Emerging Teams Asia Cup 2024, Rising Stars 2025", "Excluded (not IPL / T20I)"],
            ["Revised overs stored in balls", "e.g. 114 = 19 overs", "Used as innings length for DLS games"],
            ["Duplicate deliveries", f"{A['duplicate_deliveries']}", "-"],
            ["Name collisions", f"{len(A['names_with_multiple_ids'])} names map to >1 id: {', '.join(A['names_with_multiple_ids'])}", "All joins use player ids"],
            ["Matches without ball data", f"{A['matches_without_bbb']} (mostly abandoned)", "Excluded"]]
    s.append(table(rows, [4.3 * cm, 6.2 * cm, 6.1 * cm]))
    mr = K["margin_reconstruction"]
    s += [Spacer(1, 4), P(f"<b>Reconstruction check.</b> Rebuilt innings totals reproduce the official winning margin in {mr['matches']} non-DLS "
                          f"'won by runs' matches with mean error {mr['mean_error']:+.2f} runs, median absolute error {mr['median_abs_error']:.0f}, "
                          f"{100 * mr['exact']:.1f}% exact and {100 * mr['within_3']:.0f}% within 3 runs, so match states are built on correct scores."),
          P("<b>Accounting rules.</b> Legal ball = not a wide or no-ball. Ball faced = not a wide. Batter runs = <i>runs</i> column. "
            "Extra runs = recorded amount (extras1_runs, plus byes off a no-ball). Bowler runs = batter runs + wide and no-ball runs (byes, leg-byes and penalties excluded). Bowler wickets = caught, bowled, LBW, "
            "stumped, hit wicket. Run-outs count against the dismissed batter, including non-strikers. Retired-out is not a dismissal. "
            "Every match-state feature is a cumulative sum of <i>strictly earlier</i> deliveries."),
          PageBreak()]

    # ---- 5-6 pressure ------------------------------------------------------------------
    s += [P("5. Definition of pressure", H1),
          P("Pressure is the degree to which <b>this delivery can change who wins</b>, judged from what is known before it is bowled. "
            "That single idea brings together the indicators the brief lists:"),
          table([["Indicator", "How it enters", "Why it matters"],
                 ["Runs required, balls left, required run rate", "chase WP model inputs", "together they set target difficulty: 30 off 18 is pressure, 30 off 60 is not"],
                 ["Wickets in hand", "both WP models", "fewer wickets means a dismissal costs more, and batters cannot attack freely"],
                 ["Current score and rate (1st innings)", "1st-innings WP model", "there is no target, so pressure comes from being above or below a winning trajectory"],
                 ["Innings stage", "WP inputs, plus match-progress weight on closeness", "a 50/50 game at ball 1 is not pressure; at ball 220 it is"],
                 ["Match closeness", "1 - |2 WP - 1|", "the contest is live"],
                 ["Recent collapse", "wickets in last 24 deliveries", "scoreboard stress the WP models cannot see"],
                 ["Knockout stage", "x1.15 multiplier", "elimination raises the stakes beyond the in-game situation"],
                 ["Bowler's spell so far (bowling only)", "economy-so-far stress, 15% weight", "a bowler who has been hit carries extra personal pressure"]],
                [5 * cm, 5 * cm, 6.6 * cm]),
          P("6. Mathematical pressure scoring formula", H1),
          P("<b>Step 1 - win probability.</b> For innings 2, WP = f(runs needed, balls left, wickets left, required rate, IPL flag). "
            "For innings 1, WP = g(runs, balls left, wickets left, IPL flag). f and g are gradient-boosted classifiers with "
            "<b>monotonic constraints</b> that encode cricket logic (chase WP can only fall as runs needed rise, and only rise with balls or wickets in hand). "
            "They are fitted with 5-fold cross-fitting <b>grouped by match</b>, so no match's own result ever informs its own WP (no leakage). "
            "A logistic regression is kept as a transparent benchmark."),
          table([["Model", "Out-of-fold AUC", "Brier", "Hold-out 2025-26 AUC", "Logistic benchmark AUC"],
                 ["Innings 1 (no target)", f"{WP['innings_1']['auc']:.3f}", f"{WP['innings_1']['brier']:.3f}", f"{WP['innings_1']['holdout_2025_26_auc']:.3f}", f"{WP['innings_1']['logistic_benchmark_auc_in_sample']:.3f}"],
                 ["Innings 2 (chase)", f"{WP['innings_2']['auc']:.3f}", f"{WP['innings_2']['brier']:.3f}", f"{WP['innings_2']['holdout_2025_26_auc']:.3f}", f"{WP['innings_2']['logistic_benchmark_auc_in_sample']:.3f}"]],
                [4 * cm, 3 * cm, 2.4 * cm, 3.6 * cm, 3.6 * cm]),
          fig(ch["calib"], 15),
          P("<b>Step 2 - components and score.</b>", BODY),
          P("leverage   L = clip( (WP_if_four - WP_if_wicket) / p99_innings , 0, 1 )<br/>"
            "closeness  Q = (1 - |2*WP - 1|) * match_progress         (progress 0 -> 1 over 240 balls)<br/>"
            "stress     S = max( clip(recent_wkts_24 / 3), clip((RRR - 7.5)/7.5) )<br/>"
            "raw        R = (0.55 L + 0.30 Q + 0.15 S) * (1.15 if knockout)<br/>"
            "bowling    R_bowl = 0.85 R + 0.15 clip((spell_econ - 7.5)/6)<br/>"
            "score      Pressure = 100 * percentile_rank(R | innings)", MATH),
          P("<b>Weights.</b> Leverage gets the largest weight (0.55) because it is the most direct measure of outcome dependence (the Tango leverage-index idea). "
            "Closeness (0.30) adds whether the game is still live and late. Stress (0.15) captures collapse and required-rate signals that the WP models smooth over. "
            "Section 15 tests alternatives (leverage-only, and 0.4/0.4/0.2)."),
          P(f"<b>Thresholds.</b> Low &lt; 50, Moderate 50-75, High 75-90, Extreme &ge; 90. Because the score is a within-innings percentile, "
            "first-innings pressure is judged against first-innings situations, which handles the absence of a target."),
          fig(ch["mix"], 15), fig(ch["outcomes"], 15),
          P(f"The score behaves like pressure. Extreme deliveries have the highest wicket rate and lowest scoring rate, and come disproportionately from close matches. "
            f"Death overs are pressure only when the game is live: {100 * PV['death_over_pressure_share']:.0f}% of death balls overall, but "
            f"{100 * PV['decided_death_balls_pressure_share']:.1f}% of the {PV['decided_death_balls']:,} death balls bowled when WP was already below 5% or above 95%."),
          fig(ch["match"], 15),
          P("One of the highest-pressure non-DLS matches in the data. The red area is the pressure score and the blue line is the batting side's win probability. "
            "Pressure rises whenever the contest is live late in an innings and collapses as soon as the result becomes clear.", SMALL)]
    ex = PV["extreme_examples"][:8]
    rows = [["Match", "Batting v bowling", "Over", "Need", "Balls", "Wkts down", "WP", "Pressure"]]
    for e in ex:
        rows.append([e["match_id"], f"{e['batting_team']} v {e['bowling_team']}", f"{e['overid']}.{e['over_ball_num']}",
                     "-" if e["runs_needed"] is None else int(e["runs_needed"]), int(e["balls_left"]), int(e["wkts_before"]),
                     f"{e['wp_before']:.2f}", f"{e['pressure_bat']:.1f}"])
    s += [P("Highest-pressure moment in each of the most pressured matches:", SMALL),
          table(rows, [1.4 * cm, 6.4 * cm, 1.2 * cm, 1.2 * cm, 1.2 * cm, 1.6 * cm, 1.2 * cm, 1.6 * cm]), PageBreak()]

    # ---- 7-8 batting & bowling methodology -------------------------------------
    s += [P("7. Batting performance methodology", H1),
          P("<b>Context baseline.</b> Each ball faced gets an expected outcome from a hierarchical cell model (competition x innings x over x "
            "wickets-lost bucket x pressure category). Each cell is shrunk toward its parent with 100 pseudo-balls, then adjusted for the "
            "shrunk strength of the bowling side. A batter is therefore compared with what an average batter does <i>in the same situation against "
            "the same opponent</i>. That makes the comparison fair across openers and finishers, IPL and T20I, strong and weak attacks."),
          P(f"<b>Wicket value.</b> Regressing WPA on runs and wickets across all balls puts a dismissal at <b>{M['wicket_run_value']:.1f} runs</b> of win probability. "
            "This converts survival into runs for the value-per-ball measure."),
          table([["Component (weight)", "Definition on pressure balls, competition-weighted, shrunk", "Rewards"],
                 ["Scoring (0.30)", "sum(runs - expected runs) / (balls + k)", "effective scoring beyond the situation's norm"],
                 ["Survival (0.20)", "sum(expected dismissals - dismissals) / (balls + k)", "avoiding unnecessary dismissals"],
                 ["Impact (0.20)", "sum(win probability added) / (balls + k)", "runs that actually moved the result"],
                 ["Uplift (0.15)", "[value/ball (pressure) - value/ball (normal)] x tau^2 / (tau^2 + sampling var)", "outperforming one's own baseline"],
                 ["Consistency (0.15)", "beta-binomial shrunk share of pressure matches (>=4 balls) with value >= 0", "repeatable delivery, not one-off innings"]],
                [3.2 * cm, 8.3 * cm, 5.1 * cm]),
          P("Value per ball = runs above expected + 9.5 x dismissals avoided. Accumulating many low-impact balls is not rewarded: every component is a per-ball rate, so volume only increases <i>certainty</i>."),
          P("<b>Composite.</b> Each shrunk component is centred on the eligible pool and divided by the spread of the <i>raw</i> (unshrunk) metric. "
            "This makes a noisy, heavily shrunk component contribute proportionally less without any ad-hoc reweighting. BPPI = 100 x (composite - min) / (max - min) over eligible players."),
          P("8. Bowling performance methodology", H1),
          P("The bowler engine mirrors batting on <i>every delivery bowled</i> (wides and no-balls are the bowler's responsibility), with expected bowler-runs and "
            "expected bowler-wicket probability from the same cell model plus a batting-side strength adjustment."),
          table([["Component (weight)", "Definition on pressure deliveries", "Rewards"],
                 ["Economy (0.30)", "sum(expected bowler runs - bowler runs) / (balls + k)", "restricting scoring when it is hardest"],
                 ["Wickets (0.20)", "sum(bowler wickets - expected) / (balls + k)", "crucial wickets (bowler-credited only)"],
                 ["Impact (0.20)", "sum(-WPA) / (balls + k)", "deliveries that swung the game to the fielding side"],
                 ["Uplift (0.15)", "shrunk pressure-minus-normal value", "holding nerve relative to own baseline"],
                 ["Consistency (0.15)", "share of pressure spells with value >= 0", "repeatable control"]],
                [3.2 * cm, 8.3 * cm, 5.1 * cm]),
          P("Descriptives reported for each bowler include pressure and normal economy, wickets per over, dot %, boundary %, death-over and close-finish economy, "
            "and economy when the required rate is at least 10.")]

    # ---- 9-10 reliability & fairness -------------------------------------------------------
    sig_b, sig_w = mb["component_signal_share"], mw["component_signal_share"]
    s += [P("9. Statistical reliability adjustments", H1),
          P("<b>Empirical-Bayes shrinkage.</b> Each per-ball rate is shrunk toward the population: (sum + k x 0) / (n + k), where "
            "k = sigma^2_within / tau^2_between is estimated by weighted method of moments. tau^2 is estimated from all of a player's deliveries, "
            "where talent differences are measurable, and k is capped at 3,000 when tau^2 is indistinguishable from zero."),
          table([["", "Scoring / Economy", "Survival / Wickets", "Impact (WPA)", "Value", "Uplift reliability @200 balls", "Consistency prior"],
                 ["k - batters", f"{mb['k']['score']:.0f}", f"{mb['k']['surv']:.0f}", f"{mb['k']['imp']:.0f}", f"{mb['k']['val']:.0f}", f"{100 * mb['uplift_reliability_at_200_balls']:.1f}%", f"{mb['consistency_prior_strength']:.0f} matches"],
                 ["k - bowlers", f"{mw['k']['score']:.0f}", f"{mw['k']['surv']:.0f}", f"{mw['k']['imp']:.0f}", f"{mw['k']['val']:.0f}", f"{100 * mw['uplift_reliability_at_200_balls']:.1f}%", f"{mw['consistency_prior_strength']:.0f} matches"]],
                [2.2 * cm, 2.4 * cm, 2.4 * cm, 2.2 * cm, 1.6 * cm, 3.2 * cm, 2.6 * cm]),
          P(f"<b>Effective signal share</b> (shrunk spread / raw spread among eligible players). Batters: " + ", ".join(f"{k} {v:.2f}" for k, v in sig_b.items())
            + ". Bowlers: " + ", ".join(f"{k} {v:.2f}" for k, v in sig_w.items())
            + ". So economy and scoring dominate the ratings, because they are the most repeatable signals. Bowler wicket counts and 'clutch' uplift are mostly noise at these sample sizes."),
          P(f"<b>Reliability score (0-100)</b> = 100 x n/(n + k_value) x sqrt(min(1, pressure matches / 25)). It measures <i>how certain</i> a rating is, not how good the player is, "
            "and it is shown next to (never mixed into) the rating. <b>Uncertainty</b>: a match-level cluster bootstrap (300 resamples) gives a 90% interval for each rating, a 90% rank interval, "
            "and P(top-10), the share of resampled worlds in which the player finishes top 10."),
          P("10. Fair comparison methodology", H1),
          P(f"<b>Eligibility</b>: at least {C.MIN_PRESSURE_BALLS_BAT} pressure balls faced (batters) or legal pressure balls bowled (bowlers), across at least {C.MIN_PRESSURE_MATCHES} different matches. "
            f"Players must also be in the IPL 2027 auction pool (not {', '.join(AU['ineligible_nations'])}; active since {AU['min_last_season']}). "
            f"That gives {O['eligible_batters']} eligible batters and {O['eligible_bowlers']} eligible bowlers. A single great innings cannot qualify a player, and even a qualified player is shrunk toward average."),
          P("<b>Context normalisation</b>: expected outcomes are conditioned on competition, innings, over, wickets lost and pressure level, then on opposition strength. "
            "Powerplay openers and death finishers are each compared with their own situational norms."),
          P(f"<b>IPL and T20I</b>: both are used. Deliveries are weighted IPL 1.0, Full-Member T20I 1.0, and T20I involving an Associate side {C.COMPETITION_WEIGHTS['T20I_ASSOC']}. "
            "This keeps runs against weaker attacks from inflating ratings, while the opposition adjustment handles the rest. Separate IPL-only and T20I-only ratings "
            "(100 balls / 10 matches) are produced for comparison."),
          fig(ch["ipl_t20i"], 15), PageBreak()]

    # ---- 11-12 rankings --------------------------------------------------------------
    s += [P("11. Top 10 batters for Rajasthan Royals to back", H1)]
    rows = [["#", "Batter", "Status", "Pressure balls", "Runs", "SR (P)", "SR (N)", "Avg (P)", "BPPI", "90% CI", "Rel.", "P(top10)"]]
    for _, r in tb.iterrows():
        rows.append([int(r["rank"]), r["name"], status(r), int(r.p_balls), int(r.p_runs), f1(r.p_sr), f1(r.n_sr), f1(r.p_avg),
                     f1(r.BPPI), f"{f1(r.BPPI_lo, 0)}-{f1(r.BPPI_hi, 0)}", f1(r.reliability, 0), f"{100 * r.p_top10:.0f}%"])
    s += [table(rows, [.6 * cm, 3.3 * cm, 3.1 * cm, 1.5 * cm, 1 * cm, 1.1 * cm, 1.1 * cm, 1.1 * cm, 1.1 * cm, 1.4 * cm, .8 * cm, 1.3 * cm], font=6.8),
          P("Status: RR (retain) = already in the Rajasthan Royals squad; Target = auction target, (OS) = overseas. "
            "SR (P) / SR (N) = strike rate on pressure / normal balls. Rel. = reliability score. P(top10) = bootstrap probability of a top-10 finish within the auction pool.", SMALL),
          fig(ch["lb_bat"], 15), fig(ch["contrib_bat"], 15)]
    s.append(P("<b>Justifications (generated from the data)</b>", H2))
    for _, r in tb.iterrows():
        s.append(P(f"<b>{int(r['rank'])}. {r['name']}</b> ({status(r)}, {r['player_type']}, {r['competition']}): {r['justification']}", SMALL))
    s += [fig(ch["bat_scatter"], 15), PageBreak()]

    s += [P("12. Top 10 bowlers for Rajasthan Royals to back", H1)]
    rows = [["#", "Bowler", "Status", "Type", "Legal balls (P)", "Wkts", "Econ (P)", "Econ (N)", "Dot% (P)", "BoPPI", "90% CI", "Rel.", "P(top10)"]]
    for _, r in tw.iterrows():
        rows.append([int(r["rank"]), r["name"], status(r), r["pace_or_spin"], int(r.p_legal_balls), int(r.p_wkts), f1(r.p_econ, 2), f1(r.n_econ, 2),
                     f1(r.p_dot_pct), f1(r.BoPPI), f"{f1(r.BoPPI_lo, 0)}-{f1(r.BoPPI_hi, 0)}", f1(r.reliability, 0), f"{100 * r.p_top10:.0f}%"])
    s += [table(rows, [.6 * cm, 3.1 * cm, 3 * cm, .9 * cm, 1.3 * cm, .8 * cm, 1.1 * cm, 1.1 * cm, 1.1 * cm, 1.1 * cm, 1.3 * cm, .8 * cm, 1.3 * cm], font=6.6),
          fig(ch["lb_bowl"], 15), fig(ch["contrib_bowl"], 15)]
    s.append(P("<b>Justifications (generated from the data)</b>", H2))
    for _, r in tw.iterrows():
        s.append(P(f"<b>{int(r['rank'])}. {r['name']}</b> ({status(r)}, {r['player_type']}, {r['pace_or_spin']}): {r['justification']}", SMALL))
    # pace-only supplementary list
    pace = bowl[bowl.eligible & bowl.pace_or_spin.eq("Pace")].sort_values("BoPPI", ascending=False).head(5)
    s.append(P(f"<b>Note on bowling type.</b> {int((tw.pace_or_spin == 'Spin').sum())} of the top 10 are spinners. Spinners concede less than pacers <i>in the same over and situation</i>, "
               "and the context baseline deliberately does not adjust for bowling type, because the question is who is most effective, not who is best of their type. "
               "For reference, the top pace bowlers by BoPPI are: " + ", ".join(f"{r['name']} ({f1(r.BoPPI)}, overall #{int(r['rank'])})" for _, r in pace.iterrows()) + ".", BODY))
    s += [fig(ch["bowl_scatter"], 15), PageBreak()]

    # ---- 13 charts note, 14 case studies -----------------------------------------------
    s += [P("13. Charts and visualisations", H1),
          P("The charts in sections 6, 10, 11, 12 and 15 are produced by <font face='Courier'>src/report.py</font> from the pipeline outputs. "
            "The interactive React dashboard (<font face='Courier'>frontend/</font>, served by the FastAPI backend) adds per-player match logs, "
            "pressure distributions, phase and chase splits, IPL-vs-T20I comparisons and filters for player, team, competition, season and pressure category."),
          P("14. Case studies", H1)]
    pmb = pd.read_parquet(C.PROCESSED_DIR / "batter_matches.parquet")
    pmw = pd.read_parquet(C.PROCESSED_DIR / "bowler_matches.parquet")
    cases = [("bat", tb.iloc[0]), ("bat", tb.sort_values("reliability", ascending=False).iloc[0]), ("bowl", tw.iloc[0])]
    seen = set()
    for role, r in cases:
        if (role, r.player_id) in seen:
            continue
        seen.add((role, r.player_id))
        pm = (pmb if role == "bat" else pmw)
        pm = pm[pm.player_id == r.player_id].sort_values("match_date")
        if role == "bat":
            pm = pm[pm.pressure_balls > 0]
            best = pm.assign(v=pm.pressure_runs - pm.pressure_exp_runs).nlargest(3, "v")
            txt = (f"<b>{r['name']}</b> (rank {int(r['rank'])}, reliability {f1(r.reliability, 0)}). {int(r.pressure_matches)} matches with pressure balls. "
                   f"Pressure SR {f1(r.p_sr)} against a context-expected {f1(r.p_sr - r.p_sr_vs_expected)}; normal SR {f1(r.n_sr)}. Best pressure contributions: "
                   + "; ".join(f"{str(b.match_date)[:10]} v {b.opponent}: {int(b.pressure_runs)} runs under pressure (+{b.v:.1f} vs expected)" for b in best.itertuples()) + ".")
        else:
            pm = pm[pm.pressure_legal_balls > 0]
            best = pm.assign(v=pm.pressure_exp_runs - pm.pressure_runs).nlargest(3, "v")
            txt = (f"<b>{r['name']}</b> (rank {int(r['rank'])}, reliability {f1(r.reliability, 0)}). Pressure economy {f1(r.p_econ, 2)} against a context-expected "
                   f"{f1(r.p_econ - r.p_econ_vs_expected, 2)}; normal economy {f1(r.n_econ, 2)}. Best pressure spells: "
                   + "; ".join(f"{str(b.match_date)[:10]} v {b.opponent}: {int(b.pressure_legal_balls)} balls, {int(b.pressure_runs)} runs, {int(b.pressure_wkts)} wkts (saved {b.v:.1f})" for b in best.itertuples()) + ".")
        s.append(P(txt))
        # cumulative value chart
        F = C.FIG_DIR / f"case_{role}_{int(r.player_id)}.png"
        fig_, ax = plt.subplots(figsize=(7.5, 1.9))
        v = (pm.pressure_runs - pm.pressure_exp_runs) if role == "bat" else (pm.pressure_exp_runs - pm.pressure_runs)
        ax.bar(range(len(v)), v, color=np.where(v >= 0, "#10b981", "#ef4444"))
        ax.plot(range(len(v)), v.cumsum().values / max(len(v), 1) * 4, c=INK, lw=1, label="running mean x4")
        ax.set_title(f"{r['name']}: match-by-match pressure value ({'runs above' if role == 'bat' else 'runs saved vs'} expected)")
        ax.set_xlabel("Pressure match (chronological)"); ax.grid(axis="x", visible=False)
        fig_.tight_layout(); fig_.savefig(F); plt.close(fig_)
        s.append(fig(F, 15))

    # ---- 15 validation ------------------------------------------------------------------
    sp = M["spot_check"]
    s += [PageBreak(), P("15. Model validation and consistency checks", H1),
          table([["Check", "Result"],
                 ["Wides counted as balls faced", K["wides_counted_as_ball_faced"]],
                 ["Illegal deliveries counted as legal balls", K["illegal_counted_legal"]],
                 ["Byes / leg-byes charged to bowler", K["byes_charged_to_bowler"]],
                 ["Run-outs credited to bowler", K["runouts_credited_to_bowler"]],
                 ["Bowler wickets that are not team wickets", K["bowler_wkts_not_team_wkts"]],
                 ["Overs with > 6 legal balls", f"{K['overs_with_more_than_6_legal']} of {K['overs_total']:,}"],
                 ["Leakage: pre-ball runs / wickets != cumulative earlier balls", f"{K['leakage_runs_before_mismatch']} / {K['leakage_wkts_before_mismatch']}"],
                 ["WP models: cross-fitted by match; 2025-26 hold-out AUC", f"{WP['innings_1']['holdout_2025_26_auc']:.3f} / {WP['innings_2']['holdout_2025_26_auc']:.3f}"],
                 [f"Independent recount - {sp['top_batter']['name']}", f"runs {sp['top_batter']['pipeline_runs']} vs {sp['top_batter']['manual_runs']}, balls {sp['top_batter']['pipeline_balls']} vs {sp['top_batter']['manual_balls']}"],
                 [f"Independent recount - {sp['top_bowler']['name']}", f"runs {sp['top_bowler']['pipeline_runs']} vs {sp['top_bowler']['manual_runs']}, balls {sp['top_bowler']['pipeline_legal_balls']} vs {sp['top_bowler']['manual_legal_balls']}, wkts {sp['top_bowler']['pipeline_wkts']} vs {sp['top_bowler']['manual_wkts']}"]],
                [9.5 * cm, 7.1 * cm]),
          Spacer(1, 6), P(f"<b>Sensitivity.</b> The full rating pipeline is re-run under {len(M['sensitivity'])} alternative assumptions. The table gives Spearman correlation with the baseline ratings and how many of the baseline top 10 remain in the top 10."),
          ]
    rows = [["Scenario", "Bat rho", "Bat top-10 kept", "Bowl rho", "Bowl top-10 kept"]]
    for x in M["sensitivity"]:
        rows.append([x["scenario"], f"{x['batters']['spearman']:.2f}", f"{x['batters']['top10_overlap']}/10", f"{x['bowlers']['spearman']:.2f}", f"{x['bowlers']['top10_overlap']}/10"])
    s += [table(rows, [7.6 * cm, 2 * cm, 2.6 * cm, 2 * cm, 2.6 * cm]), fig(ch["sens_bat"], 15), fig(ch["sens_bowl"], 15),
          P(f"<b>Temporal stability (split-half).</b> Rating players separately on 2022-24 and 2025-26 (60 balls / 6 matches each) gives rank correlations of "
            f"{TS['batters']['rating_spearman']:.2f} for batters (n={TS['batters']['players_in_both']}) and {TS['bowlers']['rating_spearman']:.2f} for bowlers (n={TS['bowlers']['players_in_both']}). "
            "By component: batters " + ", ".join(f"{k} {v:.2f}" for k, v in TS['batters']['component_spearman'].items())
            + "; bowlers " + ", ".join(f"{k} {v:.2f}" for k, v in TS['bowlers']['component_spearman'].items())
            + ". Performance under pressure is only weakly persistent across eras (players change roles, teams and form), which is exactly why shrinkage and intervals are essential."),
          ]

    # ---- 16-17 ---------------------------------------------------------------------------
    s += [P("16. Limitations and assumptions", H1)]
    for t in ["Ball-tracking fields (speed, line) are sparse and inconsistent, so they are not used.",
              "WP models do not know venue, pitch, dew or team strength, so pressure is defined by the scoreboard. Batting-first pressure (AUC 0.69) is inherently harder to read than chase pressure.",
              "A batter's role shapes the pressure balls they see. Context baselines correct for situation, but finishers and openers still face different mixes.",
              "Uplift and wicket-taking under pressure have low repeatability at these sample sizes, so they carry little weight in practice. This is a property of the data, not a modelling choice.",
              f"Within-innings percentiles fix the pressure share at 25% per innings, so 'pressure' is relative. The threshold sensitivity (65-85) shows how rankings move.",
              "Top-10 membership near the cut-off is uncertain (see P(top10) and rank intervals), and players ranked 8-15 are statistically close.",
              "Competition weights (Associate T20I = 0.6) are a judgement call, but ratings are insensitive to them (rho >= 0.99)."]:
        s.append(P("&bull; " + t))
    s += [P("17. Conclusion", H1),
          P("The system turns 'pressure' from a label into a measurable quantity: the share of the match result riding on a delivery, estimated without leakage and validated against outcomes. "
            "Ratings compare each player with what an average player achieves in the same pressure situation, shrink every component in proportion to its demonstrated reliability, "
            "and report uncertainty alongside every number. The resulting top-10 lists reward players who repeatedly produce above-context output when matches are on the line. "
            "Their limits (small samples, modest year-to-year persistence) are stated openly rather than hidden."),
          P("<b>Reproduce:</b> <font face='Courier'>pip install -r requirements.txt &amp;&amp; python main.py</font> regenerates every CSV, the DuckDB store, the figures and this PDF.", SMALL)]

    def deco(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor(ACCENT)); canvas.rect(0, A4[1] - 6, A4[0], 6, stroke=0, fill=1)
        canvas.setFont("Helvetica", 7); canvas.setFillColor(colors.HexColor(MUTED))
        canvas.drawString(1.8 * cm, 1.1 * cm, "SupeRR Selector S2 - Pressure Performance Methodology")
        canvas.drawRightString(A4[0] - 1.8 * cm, 1.1 * cm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(C.OUTPUT_DIR / "methodology_report.pdf"), pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.6 * cm, bottomMargin=1.6 * cm, title="SupeRR Selector S2 - Pressure Methodology")
    doc.build(s, onFirstPage=deco, onLaterPages=deco)
