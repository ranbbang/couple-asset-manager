"""Tests for app/assets/routes.py.

Focused on the negative-cash-amount validation added in Round 4 (see
WORKLOG.md): before this, a negative amount was accepted silently and
quietly shrank every total that summed it, with no error and nothing
visibly wrong on screen.
"""
from app.models import Asset, Holding


def _login(client, app, email, password):
    app.config["WTF_CSRF_ENABLED"] = False
    r = client.post("/login", data={"email": email, "password": password},
                     follow_redirects=True)
    assert "로그아웃" in r.data.decode("utf-8"), "login did not actually succeed"
    return r


def _post_asset_form(client, category_id, amount, name="test asset"):
    return client.post("/assets/new", data={
        "name": name,
        "category": str(category_id),
        "owner": "joint",
        "institution": "",
        "notes": "",
        "holding_kind": "cash",
        "holding_currency": "KRW",
        "holding_label": "",
        "holding_amount": str(amount),
        "holding_ticker": "",
        "holding_qty": "",
    }, follow_redirects=True)


def test_negative_cash_amount_is_rejected(app, db, couple, members, categories):
    client = app.test_client()
    _login(client, app, "a@example.com", "password123")

    r = _post_asset_form(client, categories["현금"].id, amount="-50000")

    body = r.data.decode("utf-8")
    assert "0 이상이어야" in body
    assert Asset.query.filter_by(name="test asset").first() is None


def test_positive_cash_amount_still_works(app, db, couple, members, categories):
    client = app.test_client()
    _login(client, app, "a@example.com", "password123")

    r = _post_asset_form(client, categories["현금"].id, amount="50000")

    asset = Asset.query.filter_by(name="test asset").first()
    assert asset is not None
    holding = Holding.query.filter_by(asset_id=asset.id).first()
    assert holding.amount == 50000


def test_negative_amount_on_edit_is_also_rejected(app, db, couple, members, categories):
    client = app.test_client()
    _login(client, app, "a@example.com", "password123")
    _post_asset_form(client, categories["현금"].id, amount="10000", name="editable")
    asset = Asset.query.filter_by(name="editable").first()

    r = client.post(f"/assets/{asset.id}/edit", data={
        "name": "editable",
        "category": str(categories["현금"].id),
        "owner": "joint",
        "institution": "",
        "notes": "",
        "holding_kind": "cash",
        "holding_currency": "KRW",
        "holding_label": "",
        "holding_amount": "-1",
        "holding_ticker": "",
        "holding_qty": "",
    }, follow_redirects=True)

    body = r.data.decode("utf-8")
    assert "0 이상이어야" in body
    # The original (positive) holding must survive untouched.
    holding = Holding.query.filter_by(asset_id=asset.id).first()
    assert holding.amount == 10000
