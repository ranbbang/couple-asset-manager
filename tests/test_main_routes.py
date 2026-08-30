"""Tests for app/main/routes.py — no coverage before this round."""
from unittest.mock import patch

from app.extensions import db
from app.main.routes import _donut_stops, _spark_points
from app.models import ActivityLog


def _login(client, app, email="a@example.com", password="password123"):
    app.config["WTF_CSRF_ENABLED"] = False
    r = client.post("/login", data={"email": email, "password": password},
                     follow_redirects=True)
    assert "로그아웃" in r.data.decode("utf-8"), "login did not actually succeed"
    return r


def test_root_redirects_unauthenticated_to_login(app):
    client = app.test_client()
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_root_redirects_authenticated_without_couple_to_setup(app, db):
    client = app.test_client()
    app.config["WTF_CSRF_ENABLED"] = False
    client.post("/signup", data={
        "display_name": "혼자", "email": "solo2@example.com",
        "password": "password123", "confirm": "password123",
    }, follow_redirects=True)

    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert "/couple/setup" in r.headers["Location"]


def test_root_redirects_authenticated_with_couple_to_dashboard(app, db, couple, members):
    client = app.test_client()
    _login(client, app)
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert "/dashboard" in r.headers["Location"]


def test_dashboard_renders_with_no_assets_or_goals(app, db, couple, members):
    """Empty-state dashboard must not crash (division guards, None handling)."""
    client = app.test_client()
    _login(client, app)
    r = client.get("/dashboard")
    assert r.status_code == 200


def test_dashboard_liquid_months_only_set_when_expense_configured(app, db, couple, members, categories):
    from app.models import Asset, Holding

    liquid_cat = categories["현금"]
    liquid_cat.is_liquid = True
    a = Asset(couple_id=couple.id, category_id=liquid_cat.id, name="비상금")
    db.session.add(a)
    db.session.flush()
    db.session.add(Holding(asset_id=a.id, kind="cash", currency="KRW", amount=6_000_000))
    db.session.commit()

    client = app.test_client()
    _login(client, app)

    # No monthly expense configured -> "생활비 N개월치" must not appear.
    r = client.get("/dashboard")
    assert "개월치" not in r.data.decode("utf-8")

    couple.monthly_expense_krw = 2_000_000
    db.session.commit()
    r2 = client.get("/dashboard")
    assert "개월치" in r2.data.decode("utf-8")


def test_activity_page_lists_entries_for_own_household_only(app, db, couple, members):
    from app.models import Couple

    other = Couple(name="다른집3", invite_code="MAINOTHR1")
    db.session.add(other)
    db.session.flush()
    db.session.add(ActivityLog(couple_id=couple.id, action="우리집 활동", icon="•"))
    db.session.add(ActivityLog(couple_id=other.id, action="남의집 활동", icon="•"))
    db.session.commit()

    client = app.test_client()
    _login(client, app)
    r = client.get("/activity")
    body = r.data.decode("utf-8")
    assert "우리집 활동" in body
    assert "남의집 활동" not in body


def test_fx_rate_api_returns_expected_shape(app, db, couple, members):
    client = app.test_client()
    _login(client, app)

    with patch("app.services.fx.fetch_live_rate", return_value=(1400.0, "fallback")):
        r = client.get("/api/fx-rate")

    assert r.status_code == 200
    payload = r.get_json()
    assert payload == {"base": "USD", "quote": "KRW", "rate": 1400.0, "source": "fallback"}


def test_spark_points_returns_none_for_fewer_than_two_values():
    assert _spark_points([]) is None
    assert _spark_points([100.0]) is None


def test_spark_points_handles_flat_series_without_division_by_zero():
    """All-equal values -> rng would be 0 without the `or 1.0` guard."""
    points = _spark_points([500.0, 500.0, 500.0])
    assert points is not None
    assert "nan" not in points.lower()


def test_donut_stops_skips_liabilities_and_zero_share_rows():
    breakdown = [
        {"is_liability": False, "share": 60.0, "color": "#111111"},
        {"is_liability": True, "share": 30.0, "color": "#222222"},  # excluded
        {"is_liability": False, "share": 0.0, "color": "#333333"},  # excluded (falsy share)
    ]
    stops = _donut_stops(breakdown)
    assert "#111111" in stops
    assert "#222222" not in stops
    assert "#333333" not in stops
    assert "var(--surface-2)" in stops  # remaining 40% filled with the empty-track color


def test_donut_stops_returns_none_when_nothing_to_show():
    assert _donut_stops([]) is None
    assert _donut_stops([{"is_liability": True, "share": 100.0, "color": "#000"}]) is None
