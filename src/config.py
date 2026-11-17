"""Central configuration: paths, constants and every tunable modelling choice.

Keeping all knobs here makes the methodology auditable and lets the
sensitivity analysis re-run the pipeline with alternative assumptions.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"            # optional: unzipped CSVs, used if present
DATASET_ZIP = ROOT / "data" / "dataset.zip"  # the supplied CSVs, committed to git
PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUT_DIR = ROOT / "outputs"
FIG_DIR = OUTPUT_DIR / "figures"
DUCKDB_PATH = PROCESSED_DIR / "analytics.duckdb"

SEED = 42

# --- Scope -----------------------------------------------------------------
# Only senior IPL and T20I competitions are in scope. The two "T20" A-team
# events (Emerging Teams Asia Cup 2024, Asia Cup Rising Stars 2025) are excluded.
IN_SCOPE_FORMATS = {"T20I"}
IPL_PREFIX = "IPL"

# --- IPL 2027 auction pool ---------------------------------------------------
# Rankings answer: whom should Rajasthan Royals back at the IPL 2027 auction?
AUCTION_TEAM = "Rajasthan Royals"
IPL_INELIGIBLE_NATIONS = {"Pakistan"}     # Pakistan players cannot play in the IPL
AUCTION_MIN_LAST_SEASON = 2               # must have played in one of the last 2 seasons (2025-2026)

# ICC Full Members. T20I balls involving an Associate opponent are down-weighted.
FULL_MEMBERS = {
    "India", "Australia", "England", "South Africa", "New Zealand", "Pakistan",
    "Sri Lanka", "West Indies", "Bangladesh", "Afghanistan", "Ireland", "Zimbabwe",
}

# Competition weighting applied to every delivery when aggregating.
COMPETITION_WEIGHTS = {
    "IPL": 1.0,
    "T20I_FULL": 1.0,      # Full Member v Full Member
    "T20I_ASSOC": 0.6,     # at least one Associate side
}

# --- Extras encoding (validated in data audit) ------------------------------
# extras1_runs holds the extra runs on the ball (e.g. 5 wides = 5, penalty = 5);
# extras_2_runs holds byes / leg-byes run off a no-ball. Bowlers are charged
# extras1_runs for wides and no-balls, never for byes, leg-byes or penalties.
ILLEGAL_EXTRAS = {"wide", "Overstep", "other"}          # do not count as a legal ball
NO_BALL_EXTRAS = {"Overstep", "other"}
BOWLER_CHARGED_EXTRAS = {"wide", "Overstep", "other"}   # charged to bowler's figures
BYE_EXTRAS = {"byes", "legbyes"}                         # not charged to bowler
PENALTY_RUNS = 5

BOWLER_CREDITED_DISMISSALS = {"Caught", "Bowled", "LBW", "Stump", "Hit Wicket"}
NON_BATTER_FAULT_DISMISSALS = {"Retire Out"}             # not counted as a batter dismissal

# --- Pressure model -----------------------------------------------------------
PRESSURE_WEIGHTS = {"leverage": 0.55, "closeness": 0.30, "stress": 0.15}
KNOCKOUT_MULTIPLIER = 1.15
BOWLING_SPELL_WEIGHT = 0.15            # share of bowler-specific spell stress
# Category cut-points on the 0-100 pressure score (score = within-innings percentile).
PRESSURE_BINS = [0, 50, 75, 90, 100.0001]
PRESSURE_LABELS = ["Low", "Moderate", "High", "Extreme"]
PRESSURE_THRESHOLD = 75                # High + Extreme = "pressure delivery"

# --- Ratings ------------------------------------------------------------------
MIN_PRESSURE_BALLS_BAT = 150
MIN_PRESSURE_BALLS_BOWL = 150
MIN_PRESSURE_MATCHES = 15
MIN_BALLS_IN_MATCH_FOR_CONSISTENCY = 4

BPPI_WEIGHTS = {"scoring": 0.30, "survival": 0.20, "impact": 0.20, "uplift": 0.15, "consistency": 0.15}
BOPPI_WEIGHTS = {"economy": 0.30, "wickets": 0.20, "impact": 0.20, "uplift": 0.15, "consistency": 0.15}

BOOTSTRAP_REPS = 300
