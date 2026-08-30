"""Tests for app/reports/routes.py — no coverage before this round."""
import json

from app.extensions import db
from app.models import AssetSnapshot


def _login(client, app, email="a@example.com", password="password123"):
    app.config["WTF_CSRF_ENABLED"] = False
    r = client.post("/login", data={"email": email, "password": password},
                     follow_redirects=True)
    assert "로그아웃" in r.data.decode("utf-8"), "login did not actually succeed"
    return r


def test_set_allocation_saves_partial_targets(app, db, couple, members, categories):
    client = app.test_client()
    _login(client, app)

    r = client.post("/reports/allocation", data={
        "target_cash": "30", "target_investment": "40",
        "target_safe": "", "target_personal": "",
    }, follow_redirects=True)

    assert "저장되었습니다" in r.data.decode("utf-8")
    db.session.refresh(couple)
    assert json.loads(couple.target_allocation) == {"cash": 30.0, "investment": 40.0}


def test_set_allocation_rejects_sum_over_100(app, db, couple, members, categories):
    couple.target_allocation = json.dumps({"cash": 10.0})
    db.session.commit()
    client = app.test_client()
    _login(client, app)

    r = client.post("/reports/allocation", data={
        "target_cash": "60", "target_investment": "60",
        "target_safe": "", "target_personal": "",
    }, follow_redirects=True)

    assert "100%를 넘을 수 없습니다" in r.data.decode("utf-8")
    db.session.refresh(couple)
    # Unchanged from before the rejected submission.
    assert json.loads(couple.target_allocation) == {"cash": 10.0}


def test_set_allocation_rejects_non_numeric_value(app, db, couple, members, categories):
    client = app.test_client()
    _login(client, app)

    r = client.post("/reports/allocation", data={
        "target_cash": "abc", "target_investment": "",
        "target_safe": "", "target_personal": "",
    }, follow_redirects=True)

    assert "숫자(%)로 입력" in r.data.decode("utf-8")


def test_set_allocation_rejects_out_of_range_value(app, db, couple, members, categories):
    client = app.test_client()
    _login(client, app)

    r = client.post("/reports/allocation", data={
        "target_cash": "150", "target_investment": "",
        "target_safe": "", "target_personal": "",
    }, follow_redirects=True)

    assert "0~100 사이" in r.data.decode("utf-8")


def test_record_snapshot_creates_current_month_entry(app, db, couple, members, categories):
    from datetime import date

    client = app.test_client()
    _login(client, app)

    assert AssetSnapshot.query.filter_by(couple_id=couple.id).count() == 0

    r = client.post("/reports/snapshot", follow_redirects=True)

    assert "기록되었습니다" in r.data.decode("utf-8")
    snaps = AssetSnapshot.query.filter_by(couple_id=couple.id).all()
    assert len(snaps) == 1
    assert snaps[0].taken_on.replace(day=1) == date.today().replace(day=1)


def test_export_csv_contains_snapshot_history(app, db, couple, members, categories):
    from datetime import date
    from decimal import Decimal

    db.session.add(AssetSnapshot(
        couple_id=couple.id, taken_on=date(2026, 1, 1),
        net_worth_krw=Decimal("1000000"), total_assets_krw=Decimal("1200000"),
        total_liabilities_krw=Decimal("200000"), real_estate_krw=Decimal("0"),
        net_worth_excl_re_krw=Decimal("1000000"),
        category_totals=json.dumps({"현금": 1200000.0}),
        group_totals=json.dumps({"cash": 1200000.0}),
        currency_totals=json.dumps({"KRW": 1200000.0}),
        rate_used=Decimal("1350"),
    ))
    db.session.commit()

    client = app.test_client()
    _login(client, app)

    r = client.get("/reports/export.csv")

    assert r.status_code == 200
    assert r.mimetype == "text/csv"
    body = r.data.decode("utf-8-sig")
    assert "2026-01" in body
    assert "1000000" in body  # net worth column (plain int, no comma formatting)
    assert "현금=1,200,000" in body  # category-detail column IS comma-formatted
