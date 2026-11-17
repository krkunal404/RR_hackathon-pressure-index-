"""Data access layer.

Reads the bundled file data/processed/analytics.duckdb (read-only).
Each request thread gets its own cursor on the shared DuckDB database.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "processed" / "analytics.duckdb"
METRICS_PATH = ROOT / "outputs" / "metrics.json"


_lock = threading.Lock()
_base: duckdb.DuckDBPyConnection | None = None
_metrics: dict | None = None
_source = "not loaded"
_local = threading.local()


def init() -> None:
    """Open the data source once (called at app start-up, safe to call again)."""
    global _base, _metrics, _source
    with _lock:
        if _base is not None:
            return
        if not DB_PATH.exists():
            raise RuntimeError(f"{DB_PATH} not found - run `python main.py` first")
        _base = duckdb.connect(str(DB_PATH), read_only=True)
        _metrics = json.loads(METRICS_PATH.read_text())
        _source = "duckdb-file"


def source() -> str:
    return _source


def con() -> duckdb.DuckDBPyConnection:
    if _base is None:
        init()
    if getattr(_local, "con", None) is None:
        _local.con = _base.cursor()
    return _local.con


def q(sql: str, params: list | None = None) -> pd.DataFrame:
    return con().execute(sql, params or []).df()


def records(df: pd.DataFrame) -> list[dict]:
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.astype(object).where(df.notna(), None)
    for c in df.columns:
        if len(df) and isinstance(df[c].iloc[0], pd.Timestamp):
            df[c] = df[c].map(lambda v: v.isoformat()[:10] if v is not None else None)
    return df.to_dict("records")


def metrics() -> dict:
    if _metrics is None:
        init()
    return _metrics


def where(filters: dict[str, object], alias: str = "") -> tuple[str, list]:
    """Build a parameterised WHERE clause from optional equality filters."""
    p = f"{alias}." if alias else ""
    clauses, params = [], []
    for col, val in filters.items():
        if val is None or val == "" or val == "All":
            continue
        clauses.append(f"{p}{col} = ?")
        params.append(val)
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params
