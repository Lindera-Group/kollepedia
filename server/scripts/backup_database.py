"""Timestamped backup of the NG database (parity with the prototype's policy).

Rotation: keep the 10 most recent, then one per ISO week.
Usage: uv run python scripts/backup_database.py
"""

import shutil
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BACKUP_DIR = DATA_DIR / "backups"
DB = DATA_DIR / "kollepedia.db"


def rotate() -> None:
    backups = sorted(BACKUP_DIR.glob("kollepedia_backup_*.db"), reverse=True)
    keep: set[Path] = set(backups[:10])
    seen_weeks: set[str] = set()
    for path in backups:
        stamp = path.stem.removeprefix("kollepedia_backup_")
        try:
            week = datetime.strptime(stamp, "%Y%m%d_%H%M%S").strftime("%G-W%V")
        except ValueError:
            keep.add(path)
            continue
        if path in keep:
            seen_weeks.add(week)
        elif week not in seen_weeks:
            keep.add(path)
            seen_weeks.add(week)
    for path in backups:
        if path not in keep:
            path.unlink()
            print(f"  rotated out: {path.name}")


def main() -> None:
    if not DB.exists():
        sys.exit(f"Database not found: {DB}")
    BACKUP_DIR.mkdir(exist_ok=True)
    target = BACKUP_DIR / f"kollepedia_backup_{datetime.now():%Y%m%d_%H%M%S}.db"
    shutil.copy2(DB, target)
    print(f"Backup created: {target} ({target.stat().st_size / 1e6:.1f} MB)")
    rotate()


if __name__ == "__main__":
    main()
