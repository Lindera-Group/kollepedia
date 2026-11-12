"""Interactive restore of the NG database from a backup.

A safety backup of the current database is taken before restoring.
Usage: uv run python scripts/restore_database.py
"""

import shutil
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BACKUP_DIR = DATA_DIR / "backups"
DB = DATA_DIR / "kollepedia.db"


def main() -> None:
    backups = sorted(BACKUP_DIR.glob("kollepedia_backup_*.db"), reverse=True)
    if not backups:
        sys.exit(f"No backups found in {BACKUP_DIR}")
    print("Available backups (newest first):")
    for i, path in enumerate(backups, start=1):
        print(f"  {i}. {path.name} ({path.stat().st_size / 1e6:.1f} MB)")
    choice = input("Restore which backup? [number, empty aborts] ").strip()
    if not choice:
        sys.exit("Aborted.")
    try:
        selected = backups[int(choice) - 1]
    except (ValueError, IndexError):
        sys.exit("Invalid selection.")
    if DB.exists():
        safety = BACKUP_DIR / f"kollepedia_backup_{datetime.now():%Y%m%d_%H%M%S}_pre_restore.db"
        shutil.copy2(DB, safety)
        print(f"Safety backup: {safety.name}")
    shutil.copy2(selected, DB)
    print(f"Restored {selected.name} → {DB}. Restart the backend if it is running.")


if __name__ == "__main__":
    main()
