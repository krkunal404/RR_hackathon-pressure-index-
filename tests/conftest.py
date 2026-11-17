import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import config as C  # noqa: E402


@pytest.fixture(scope="session")
def deliveries() -> pd.DataFrame:
    p = C.PROCESSED_DIR / "deliveries.parquet"
    if not p.exists():
        pytest.skip("run `python main.py` first")
    return pd.read_parquet(p)


@pytest.fixture(scope="session")
def raw():
    from src.data_loader import load_raw
    return load_raw()


@pytest.fixture(scope="session")
def built(raw):
    from src.preprocessing import build_deliveries
    return build_deliveries(raw)
