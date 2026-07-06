"""SQLite database backup helper.

Copies the live app.db file to backups/app_<timestamp>.db before any
destructive operation (like reseeding). Backups are plain file copies, so
restoring is just copying one back over app.db.
"""
import shutil
from datetime import datetime
from pathlib import Path

from .. import config as app_config

BACKUP_DIR = app_config.BASE_DIR / "backups"
MAX_BACKUPS = 20  # keep the most recent N; older ones are pruned automatically


def db_path() -> Path:
    """Resolve the on-disk path of the sqlite file from the configured URI."""
    uri = app_config.Config.SQLALCHEMY_DATABASE_URI
    prefix = "sqlite:///"
    if not uri.startswith(prefix):
        raise ValueError(f"backup only supports sqlite databases, got: {uri}")
    return Path(uri[len(prefix):])


def backup_database(reason: str = "manual") -> Path | None:
    """Copy app.db to backups/ with a timestamped name.

    Returns the backup path, or None if there was no database file to back up
    (e.g. first run before any data exists).
    """
    src = db_path()
    if not src.exists():
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"app_{stamp}_{reason}.db"
    shutil.copy2(src, dest)
    _prune_old_backups()
    return dest


def _prune_old_backups() -> None:
    """Keep only the MAX_BACKUPS most recent backup files."""
    if not BACKUP_DIR.exists():
        return
    backups = sorted(BACKUP_DIR.glob("app_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[MAX_BACKUPS:]:
        old.unlink(missing_ok=True)


def auto_backup_if_due() -> Path | None:
    """At most one automatic backup per calendar day (called on app startup).

    Light local safety net for the single-household deployment; a real backup
    strategy comes with the future hosted setup.
    """
    today = datetime.now().strftime("%Y%m%d")
    for p in list_backups():
        if p.name.startswith(f"app_{today}") and p.name.endswith("_auto.db"):
            return None
    return backup_database(reason="auto")


def list_backups() -> list[Path]:
    if not BACKUP_DIR.exists():
        return []
    return sorted(BACKUP_DIR.glob("app_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
