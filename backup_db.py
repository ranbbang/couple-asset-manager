"""Manual database backup.

Usage:
    python backup_db.py            Back up app.db to backups/app_<timestamp>.db
    python backup_db.py --list     List existing backups (newest first)

Backups are plain file copies of the SQLite database — restoring means copying
one back over app.db (with the app stopped). The 20 most recent backups are
kept automatically; older ones are pruned on each new backup.
"""
import argparse
import sys

# Windows consoles often default to cp949/cp1252, which can't encode the ✅
# character below and would otherwise crash. UTF-8 works everywhere.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from app import create_app
from app.services.backup import backup_database, list_backups


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="List existing backups instead of creating one.")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if args.list:
            backups = list_backups()
            if not backups:
                print("아직 백업이 없습니다.")
                return
            print(f"백업 {len(backups)}개 (최신순):")
            for b in backups:
                print(f"  {b.name}  ({human_size(b.stat().st_size)})")
            return

        path = backup_database(reason="manual")
        if path is None:
            print("백업할 app.db 파일이 아직 없습니다 (첫 실행 전).")
            sys.exit(1)
        print(f"✅ 백업 완료: {path}")


if __name__ == "__main__":
    main()
