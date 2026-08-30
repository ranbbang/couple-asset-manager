"""Shared pytest fixtures.

Every test runs against a throwaway SQLite database file created fresh per
test under pytest's `tmp_path` — this never touches the real app.db (or its
backups/), so there is no risk to the demo household or any imported real
data, and the file is cleaned up automatically after the test.

Deliberately NOT `sqlite:///:memory:`: an in-memory database lives on a
single DB-API connection, so any code path that opens a second connection
(e.g. a Flask test-client request, which runs in its own app/request
context) sees a *different*, empty database — the tables exist but none of
the fixture data set up before the request is visible. That failure is
silent (queries just return nothing, not an error), so it slipped past
Round 1's tests, which never issued an HTTP request. A per-test file keeps
one real file on disk that every connection opens, side-stepping that
entirely, while still being fully isolated and disposable.
"""
import pytest

from app import create_app
from app.config import Config
from app.extensions import db as _db
from app.models import Category, Couple, User


@pytest.fixture()
def app(tmp_path):
    class TestConfig(Config):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'test.db'}"
        TESTING = True
        WTF_CSRF_ENABLED = False
        SECRET_KEY = "test-secret"

    application = create_app(TestConfig)
    with application.app_context():
        yield application


@pytest.fixture()
def db(app):
    yield _db


@pytest.fixture()
def couple(db):
    c = Couple(name="테스트가구", invite_code="TESTCODE")
    db.session.add(c)
    db.session.flush()
    return c


@pytest.fixture()
def members(db, couple):
    # example.com/.org/.net (RFC 2606) — real, resolvable domains. A
    # reserved TLD like .local/.test/.invalid gets flagged by
    # email_validator as "a special-use or reserved name" and fails
    # WTForms' Email() validator on any route that actually validates the
    # form (login, account settings), even though it never touches the
    # network for a deliverability check.
    a = User(email="a@example.com", display_name="에이", couple_id=couple.id)
    a.set_password("password123")
    b = User(email="b@example.com", display_name="비", couple_id=couple.id)
    b.set_password("password123")
    db.session.add_all([a, b])
    db.session.flush()
    return [a, b]


@pytest.fixture()
def categories(db, couple):
    """One category per report_group, plus one liability category."""
    specs = [
        ("현금", "cash", False, False, True),
        ("투자", "investment", False, False, False),
        ("연금", "safe", False, False, False),
        ("부동산", "safe", False, True, False),
        ("빚", None, True, False, False),
    ]
    cats = {}
    for i, (name, group, is_liability, is_re, is_liquid) in enumerate(specs):
        c = Category(
            couple_id=couple.id, name=name, icon="•", color="#000000",
            is_liability=is_liability, report_group=group,
            is_real_estate=is_re, is_liquid=is_liquid, sort_order=i,
        )
        db.session.add(c)
        cats[name] = c
    db.session.flush()
    return cats
