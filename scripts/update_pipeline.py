"""Nightly refresh: pick up new data, rerun the pipeline and publish everything.

    python scripts/update_pipeline.py            # only runs if the data changed
    python scripts/update_pipeline.py --force    # rerun even if nothing changed
    python scripts/update_pipeline.py --no-publish   # skip Docker push and git commit/push

Steps
  1. Compare the CSVs in the inbox folder (default: local/dataset/) with data/raw/.
     Nothing new -> stop.
  2. Copy new CSVs into data/raw/ and rebuild data/dataset.zip.
  3. python main.py (ratings, outputs, DuckDB, PDF report).
  4. pytest. If the tests fail, stop: nothing is published.
  5. Rebuild the frontend (npm run build).
  6. docker build + push (skipped if Docker is not running).
  7. git commit, and git push if a remote is configured.

Scheduled by scripts/register_schedule.ps1. Logs go to local/logs/.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
ZIP = ROOT / "data" / "dataset.zip"
LOG_DIR = ROOT / "local" / "logs"
DEFAULT_INBOX = ROOT / "local" / "dataset"
IMAGE = os.environ.get("PRESSURE_INDEX_IMAGE", "kunnal404/pressure-index:latest")
CSV_NAMES = ["ball_by_ball", "matches", "competitions", "teams", "playing_eleven",
             "competition_team_player_mapping"]

LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"update-{datetime.now():%Y-%m-%d_%H%M}.log"


def log(msg: str) -> None:
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def run(cmd: list[str], cwd: Path = ROOT, check: bool = True) -> int:
    """Run a command, streaming its output into the log."""
    log("$ " + " ".join(cmd))
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        rc = subprocess.run(cmd, cwd=cwd, stdout=fh, stderr=subprocess.STDOUT).returncode
    if check and rc != 0:
        raise RuntimeError(f"command failed (exit {rc}): {' '.join(cmd)} - see {LOG_FILE}")
    return rc


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def changed_files(inbox: Path) -> list[str]:
    out = []
    for name in CSV_NAMES:
        new = inbox / f"{name}.csv"
        if not new.exists():
            continue
        cur = RAW / f"{name}.csv"
        if not cur.exists() or sha(new) != sha(cur):
            out.append(name)
    return out


def ingest(inbox: Path, names: list[str]) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copy2(inbox / f"{name}.csv", RAW / f"{name}.csv")
        log(f"updated data/raw/{name}.csv")
    tmp = ZIP.with_suffix(".tmp.zip")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for name in CSV_NAMES:
            z.write(RAW / f"{name}.csv", f"{name}.csv")
    tmp.replace(ZIP)
    log("rebuilt data/dataset.zip")


def docker_available() -> bool:
    return shutil.which("docker") is not None and subprocess.run(
        ["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def git(*args: str, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", type=Path, default=DEFAULT_INBOX, help="folder where new CSVs are dropped")
    ap.add_argument("--force", action="store_true", help="rerun even if the data has not changed")
    ap.add_argument("--no-publish", action="store_true", help="skip Docker push and git commit/push")
    a = ap.parse_args()

    log(f"nightly update started (inbox: {a.inbox})")
    names = changed_files(a.inbox) if a.inbox.exists() else []
    if not names and not a.force:
        log("no new data - nothing to do")
        return 0
    if names:
        log(f"new data in: {', '.join(names)}")
        ingest(a.inbox, names)

    py = sys.executable
    run([py, "main.py"])
    run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider"])
    log("pipeline + tests passed")

    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if npm:
        run([npm, "run", "build"], cwd=ROOT / "frontend")
    else:
        log("npm not found - skipped frontend build")

    if a.no_publish:
        log("--no-publish: skipping Docker and git")
        return 0

    if docker_available():
        run(["docker", "build", "-t", IMAGE, "."])
        run(["docker", "push", IMAGE])
        log(f"pushed {IMAGE}")
    else:
        log("Docker is not running - skipped image build/push (start Docker Desktop to include it)")

    git("add", "-A")
    if git("status", "--porcelain"):
        msg = "refresh data and outputs" + (f" ({', '.join(names)})" if names else "")
        git("commit", "-m", msg)
        log(f"committed: {msg}")
        if git("remote"):
            git("push")
            log("pushed to git remote")
        else:
            log("no git remote configured - commit kept locally")
    else:
        log("git: nothing to commit")

    log("done")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 - log every failure for the morning check
        log(f"FAILED: {e}")
        sys.exit(1)
