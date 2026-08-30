"""Shared pytest fixtures.

Every test runs against a throwaway in-memory SQLite database created fresh
per test — this never touches the real app.db (or its backups/), so there is
no risk to the demo household or any imported real data.
"""
import pytest

from app import create_app
from app.config import Config
from app.extensions import db as _db
from app.models import Category, Couple, User


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret"


@pytest.fixture()
def app():
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
    a = User(email="a@test.local", display_name="에이", couple_id=couple.id)
    a.set_password("password123")
    b = User(email="b@test.local", display_name="비", couple_id=couple.id)
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
