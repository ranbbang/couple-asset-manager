"""Tests for app/couple/routes.py — no coverage before this round."""
from app.extensions import db
from app.models import Couple, User


def _signup(client, app, email, password, display_name):
    app.config["WTF_CSRF_ENABLED"] = False
    r = client.post("/signup", data={
        "display_name": display_name, "email": email,
        "password": password, "confirm": password,
    }, follow_redirects=True)
    assert "회원가입" not in r.data.decode("utf-8").split("<title>")[1].split("</title>")[0]
    return r


def _login(client, app, email, password):
    app.config["WTF_CSRF_ENABLED"] = False
    r = client.post("/login", data={"email": email, "password": password},
                     follow_redirects=True)
    assert "로그아웃" in r.data.decode("utf-8"), "login did not actually succeed"
    return r


def test_create_couple_seeds_default_categories(app, db):
    client = app.test_client()
    _signup(client, app, "solo@example.com", "password123", "혼자")

    r = client.post("/couple/create", data={"name": "우리집"}, follow_redirects=True)

    user = User.query.filter_by(email="solo@example.com").first()
    assert user.has_couple
    cats = user.couple.categories
    assert len(cats) == 8  # DEFAULT_CATEGORIES
    assert "초대" in r.data.decode("utf-8") or r.status_code == 200


def test_create_couple_blank_name_defaults_to_placeholder(app, db):
    client = app.test_client()
    _signup(client, app, "blank@example.com", "password123", "이름없음")

    client.post("/couple/create", data={"name": ""}, follow_redirects=True)

    user = User.query.filter_by(email="blank@example.com").first()
    assert user.couple.name == "우리집"


def test_join_with_invalid_code_shows_error(app, db):
    client = app.test_client()
    _signup(client, app, "joiner@example.com", "password123", "조인러")

    r = client.post("/couple/join", data={"invite_code": "NOPE0000"}, follow_redirects=True)

    assert "찾을 수 없습니다" in r.data.decode("utf-8")
    user = User.query.filter_by(email="joiner@example.com").first()
    assert not user.has_couple


def test_join_with_valid_code_links_user_to_couple(app, db, couple, members):
    client = app.test_client()
    # couple already has 2 members from the fixture — remove one to make room.
    db.session.delete(members[1])
    db.session.commit()

    _signup(client, app, "newpartner@example.com", "password123", "새파트너")
    r = client.post("/couple/join", data={"invite_code": couple.invite_code},
                     follow_redirects=True)

    user = User.query.filter_by(email="newpartner@example.com").first()
    assert user.couple_id == couple.id
    assert "연결되었어요" in r.data.decode("utf-8")


def test_join_rejects_when_couple_already_full(app, db, couple, members):
    # members fixture already fills both of MAX_MEMBERS slots.
    client = app.test_client()
    _signup(client, app, "thirdwheel@example.com", "password123", "삼자")

    r = client.post("/couple/join", data={"invite_code": couple.invite_code},
                     follow_redirects=True)

    assert "이미 두 명이 연결된" in r.data.decode("utf-8")
    user = User.query.filter_by(email="thirdwheel@example.com").first()
    assert not user.has_couple


def test_settings_rejects_negative_monthly_expense(app, db, couple, members):
    client = app.test_client()
    _login(client, app, "a@example.com", "password123")

    r = client.post("/couple/settings", data={"monthly_expense": "-1000"},
                     follow_redirects=True)

    assert "0 이상의 숫자" in r.data.decode("utf-8")
    db.session.refresh(couple)
    assert couple.monthly_expense_krw is None


def test_settings_blank_clears_monthly_expense(app, db, couple, members):
    couple.monthly_expense_krw = 2_000_000
    db.session.commit()

    client = app.test_client()
    _login(client, app, "a@example.com", "password123")

    client.post("/couple/settings", data={"monthly_expense": ""}, follow_redirects=True)

    db.session.refresh(couple)
    assert couple.monthly_expense_krw is None


def test_settings_accepts_comma_formatted_amount(app, db, couple, members):
    client = app.test_client()
    _login(client, app, "a@example.com", "password123")

    client.post("/couple/settings", data={"monthly_expense": "2,500,000"}, follow_redirects=True)

    db.session.refresh(couple)
    assert couple.monthly_expense_krw == 2_500_000
