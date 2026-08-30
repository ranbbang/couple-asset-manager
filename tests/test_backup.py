"""Tests for app/services/backup.py.

Regression coverage for a real bug found while adding the test suite: backup
code used to read the hardcoded Config class attribute instead of the active
app's config, so even an isolated test database resolved to (and copied)
the real app.db on disk. Everything here must run without ever touching the
project's real app.db or backups/ directory.
"""
from app import config as app_config
from app.services import backup


def test_db_path_follows_active_app_config_not_the_class_default(app):
    """Regression test: db_path() must resolve from current_app.config,
    not app.config.Config.SQLALCHEMY_DATABASE_URI. The test app points at a
    throwaway file under pytest's tmp_path — if this ever again reads the
    class default, it will return the real project's app.db path instead.
    """
    path = backup.db_path()
    assert path.name == "test.db"
    assert path != app_config.BASE_DIR / "app.db"


def test_backup_database_copies_the_active_apps_own_db(app, tmp_path, monkeypatch):
    """backup_database() must back up the ACTIVE app's database file, not
    the real project's app.db, and must not touch the real backups/ dir."""
    monkeypatch.setattr(backup, "BACKUP_DIR", tmp_path / "backups")
    result = backup.backup_database(reason="test")
    assert result is not None
    assert result.parent == tmp_path / "backups"
    assert result.read_bytes() == backup.db_path().read_bytes()
