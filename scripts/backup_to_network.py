"""
Back up the live RoboTaste database, logs, and protocol definitions to a shared
network folder, so any PC on the network can read the latest data.

Intended to run unattended from Windows Task Scheduler via backup_to_network.bat,
but also runs standalone on any OS (falls back to a plain directory mirror when
the `robocopy` binary is unavailable, e.g. during local development on macOS/Linux).

Usage: python scripts/backup_to_network.py

Configuration (all overridable via environment variable, see CONFIG section below):
  ROBOTASTE_BACKUP_DEST   Destination root, e.g. \\\\SERVER\\Share\\RoboTaste
  ROBOTASTE_DB_PATH       Source DB path (matches robotaste/data/database.py)
  ROBOTASTE_BACKUP_KEEP   Number of timestamped DB snapshots to retain (default 30)
"""

import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent

# EDIT THIS on the Windows host, or set the ROBOTASTE_BACKUP_DEST env var —
# the script refuses to run while this is left as the placeholder.
_BACKUP_DEST_PLACEHOLDER = r"\\SERVER\Share\RoboTaste"
BACKUP_DEST = Path(os.environ.get("ROBOTASTE_BACKUP_DEST", _BACKUP_DEST_PLACEHOLDER))

DB_PATH = Path(os.environ.get("ROBOTASTE_DB_PATH", str(REPO_ROOT / "robotaste.db")))
LOGS_SRC = REPO_ROOT / "logs"
PROTOCOLS_SRC = REPO_ROOT / "protocols"

KEEP_SNAPSHOTS = int(os.environ.get("ROBOTASTE_BACKUP_KEEP", "30"))

# ── Helpers ─────────────────────────────────────────────────────────────────


def log(lines: list[str], message: str) -> None:
    stamped = f"[{datetime.now().isoformat(timespec='seconds')}] {message}"
    print(stamped)
    lines.append(stamped)


def backup_database(lines: list[str]) -> bool:
    if not DB_PATH.exists():
        log(lines, f"FAIL db: source not found at {DB_PATH}")
        return False

    db_dir = BACKUP_DEST / "db"
    db_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_path = db_dir / f"robotaste_{timestamp}.db"
    tmp_path = db_dir / f".robotaste_{timestamp}.db.tmp"
    latest_path = db_dir / "robotaste_latest.db"

    try:
        # sqlite3's online backup API takes a consistent snapshot even while
        # the live app holds the database open for writes.
        src = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        try:
            dst = sqlite3.connect(str(tmp_path))
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()

        os.replace(tmp_path, snapshot_path)
        shutil.copyfile(snapshot_path, latest_path)
    except Exception as exc:
        log(lines, f"FAIL db: {exc}")
        tmp_path.unlink(missing_ok=True)
        return False

    size_kb = snapshot_path.stat().st_size / 1024
    log(lines, f"OK db: {snapshot_path.name} ({size_kb:.0f} KB)")

    prune_snapshots(lines, db_dir)
    return True


def prune_snapshots(lines: list[str], db_dir: Path) -> None:
    snapshots = sorted(db_dir.glob("robotaste_2*.db"))
    excess = snapshots[:-KEEP_SNAPSHOTS] if KEEP_SNAPSHOTS > 0 else snapshots
    for old in excess:
        old.unlink(missing_ok=True)
    if excess:
        log(lines, f"OK prune: removed {len(excess)} snapshot(s), kept {min(len(snapshots), KEEP_SNAPSHOTS)}")


def mirror_dir(lines: list[str], label: str, src: Path, dst: Path) -> bool:
    if not src.exists():
        log(lines, f"SKIP {label}: source not found at {src}")
        return True  # not a failure — e.g. protocols/ may not exist on every install

    dst.mkdir(parents=True, exist_ok=True)

    if shutil.which("robocopy"):
        result = subprocess.run(
            ["robocopy", str(src), str(dst), "/MIR", "/R:2", "/W:2", "/NP", "/NDL"],
            capture_output=True,
            text=True,
        )
        # robocopy exit codes 0-7 indicate success (files copied / no changes);
        # 8+ indicates at least one failure.
        if result.returncode < 8:
            log(lines, f"OK {label}: mirrored via robocopy (code {result.returncode})")
            return True
        log(lines, f"FAIL {label}: robocopy exit code {result.returncode}\n{result.stdout}\n{result.stderr}")
        return False

    try:
        shutil.copytree(src, dst, dirs_exist_ok=True)
        log(lines, f"OK {label}: mirrored via copytree (robocopy unavailable)")
        return True
    except Exception as exc:
        log(lines, f"FAIL {label}: {exc}")
        return False


def check_destination(lines: list[str]) -> bool:
    if str(BACKUP_DEST) == _BACKUP_DEST_PLACEHOLDER:
        log(
            lines,
            "FAIL: BACKUP_DEST is still the placeholder "
            f"({_BACKUP_DEST_PLACEHOLDER}). Set ROBOTASTE_BACKUP_DEST or edit "
            "BACKUP_DEST in scripts/backup_to_network.py.",
        )
        return False

    try:
        BACKUP_DEST.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log(lines, f"FAIL: cannot reach/create destination {BACKUP_DEST}: {exc}")
        return False

    return True


# ── Main ────────────────────────────────────────────────────────────────────


def main() -> int:
    lines: list[str] = []
    start = time.monotonic()

    log(lines, f"Backup run starting (dest={BACKUP_DEST})")

    if not check_destination(lines):
        return _finish(lines, ok=False, start=start)

    ok = True
    ok &= backup_database(lines)
    ok &= mirror_dir(lines, "logs", LOGS_SRC, BACKUP_DEST / "logs")
    ok &= mirror_dir(lines, "protocols", PROTOCOLS_SRC, BACKUP_DEST / "protocols")

    return _finish(lines, ok=ok, start=start)


def _finish(lines: list[str], ok: bool, start: float) -> int:
    elapsed = time.monotonic() - start
    log(lines, f"Backup run {'OK' if ok else 'FAILED'} ({elapsed:.1f}s)")

    try:
        with open(BACKUP_DEST / "backup.log", "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except OSError:
        pass  # destination unreachable is already reported above

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
