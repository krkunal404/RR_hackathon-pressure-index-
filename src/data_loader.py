"""Load raw CSVs, enforce types and produce an auditable data-quality report."""
from __future__ import annotations

import re
import zipfile

import numpy as np
import pandas as pd

from . import config as C


RAW_FILES = ["ball_by_ball", "matches", "competitions", "teams", "playing_eleven",
             "competition_team_player_mapping"]


def read_raw_csv(name: str) -> pd.DataFrame:
    """Read one supplied CSV: from data/raw/ if unzipped there, else from data/dataset.zip."""
    path = C.RAW_DIR / f"{name}.csv"
    if path.exists():
        return pd.read_csv(path)
    if not C.DATASET_ZIP.exists():
        raise FileNotFoundError(f"Neither {path} nor {C.DATASET_ZIP} exists")
    with zipfile.ZipFile(C.DATASET_ZIP) as z, z.open(f"{name}.csv") as fh:
        return pd.read_csv(fh)


def load_raw() -> dict[str, pd.DataFrame]:
    return {f: read_raw_csv(f) for f in RAW_FILES}


def classify_competition(comp: pd.DataFrame) -> pd.DataFrame:
    comp = comp.copy()
    comp["is_ipl"] = comp["comp_name"].str.startswith(C.IPL_PREFIX)
    comp["competition"] = np.where(comp["is_ipl"], "IPL",
                                   np.where(comp["match_format"].isin(C.IN_SCOPE_FORMATS), "T20I", "OTHER"))
    comp["season_year"] = comp["season"].astype(str).str[:4].astype(int)
    return comp


def parse_result(m: pd.DataFrame) -> pd.DataFrame:
    m = m.copy()
    res = m["result"].fillna("")
    m["margin_runs"] = res.str.extract(r"[Ww]on by (\d+) [Rr]uns?", expand=False).astype(float)
    m["margin_wkts"] = res.str.extract(r"[Ww]on by (\d+) [Ww]ickets?", expand=False).astype(float)
    m["is_dls"] = res.str.contains(r"D/?L", flags=re.I) | m["revised_target"].notna()
    m["no_result"] = res.str.contains("No Result|Abandoned", case=False)
    m["tied"] = res.str.contains("Tied", case=False)
    m["match_date"] = pd.to_datetime(m["match_date"])
    return m


def audit(raw: dict[str, pd.DataFrame]) -> dict:
    """Data-quality facts quoted in the methodology report."""
    b, m = raw["ball_by_ball"], raw["matches"]
    out = {
        "rows": {k: int(len(v)) for k, v in raw.items()},
        "bbb_matches": int(b.match_id.nunique()),
        "matches_without_bbb": int(len(set(m.match_id) - set(b.match_id))),
        "bbb_without_match": int(len(set(b.match_id) - set(m.match_id))),
        "duplicate_deliveries": int(b.duplicated(["match_id", "innings", "overid", "over_ball_num"]).sum()),
        "super_over_deliveries": int((b.innings > 2).sum()),
        "extras_type_counts": b["extras_type"].fillna("none").value_counts().to_dict(),
        "extras_runs_by_type": b[b["extras_type"].notna()].groupby("extras_type")["extras1_runs"]
                                .agg(lambda s: f"{int(s.min())}-{int(s.max())} (mean {s.mean():.2f})").to_dict(),
        "extra_runs_total": int(b["extras1_runs"].fillna(0).sum()),
        "dismissal_counts": b["dismissal_type"].dropna().value_counts().to_dict(),
        "ids_with_multiple_names": int(b.groupby("striker_id").striker_name.nunique().gt(1).sum()
                                       + b.groupby("bowler_id").bowler_name.nunique().gt(1).sum()),
        "names_with_multiple_ids": sorted(set(
            b.groupby("striker_name").striker_id.nunique()[lambda s: s > 1].index.tolist()
            + b.groupby("bowler_name").bowler_id.nunique()[lambda s: s > 1].index.tolist())),
        "missing_values_bbb": b.isna().sum()[lambda s: s > 0].astype(int).to_dict(),
        "matches_no_result": int(m.result.str.contains("No Result|Abandoned", case=False).sum()),
        "matches_dls": int(m.revised_target.notna().sum()),
    }
    return out
