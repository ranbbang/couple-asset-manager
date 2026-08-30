"""Tests for app/services/backup.py.

Regression coverage for a real bug found while adding the test suite: backup
code used to read the hardcoded Config class attribute instead of the active
app's config, so even an in-memory test database resolved to (and copied)
the real app.db on disk. Everything here must run without ever touching the
project's real app.db or backups/ directory.
"""
from app.services import backup


def test_db_path_follows_active_app_config_not_the_class_default(app):
    """Regression test: db_path() must resolve from current_app.config,
    not app.config.Config.SQLALCHEMY_DATABASE_URI. The test app is
    configured with sqlite:///:memory:, which has no directory component —
    if this ever again reads the class default, it will return the real
    project's app.db path instead.
    """
    path = backup.db_path()
    assert str(path) == ":memory:"


def test_backup_database_is_a_noop_for_an_in_memory_db(app, tmp_path, monkeypatch):
    """backup_database() must not create a file (and must not touch the
    real project's backups/ directory) when the active DB has no on-disk
    file to copy."""
    monkeypatch.setattr(backup, "BACKUP_DIR", tmp_path)
    result = backup.backup_database(reason="test")
    assert result is None
    assert list(tmp_path.iterdir()) == []
