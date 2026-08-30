"""Tests for app/categories/routes.py — no coverage before this round."""
from app.extensions import db
from app.models import Asset, Category, Couple


def _login(client, app, email="a@example.com", password="password123"):
    app.config["WTF_CSRF_ENABLED"] = False
    r = client.post("/login", data={"email": email, "password": password},
                     follow_redirects=True)
    assert "로그아웃" in r.data.decode("utf-8"), "login did not actually succeed"
    return r


def _category_form(**overrides):
    data = {
        "name": "새 카테고리",
        "icon": "🆕",
        "color": "#123456",
        "report_group": "cash",
    }
    data.update(overrides)
    return data


def test_create_rejects_duplicate_name_in_same_household(app, db, couple, members, categories):
    client = app.test_client()
    _login(client, app)

    r = client.post("/categories/new", data=_category_form(name="현금"), follow_redirects=True)

    assert "이미 있습니다" in r.data.decode("utf-8")
    assert Category.query.filter_by(couple_id=couple.id, name="현금").count() == 1


def test_create_requires_report_group_for_non_liability_category(app, db, couple, members, categories):
    client = app.test_client()
    _login(client, app)

    r = client.post("/categories/new", data=_category_form(name="애매한자산", report_group=""),
                     follow_redirects=True)

    assert "리포트 그룹을 선택" in r.data.decode("utf-8")
    assert Category.query.filter_by(name="애매한자산").first() is None


def test_create_liability_category_does_not_require_report_group(app, db, couple, members, categories):
    client = app.test_client()
    _login(client, app)

    r = client.post("/categories/new", data={
        "name": "새 빚", "icon": "💳", "color": "#000000",
        "is_liability": "y", "report_group": "",
    }, follow_redirects=True)

    cat = Category.query.filter_by(name="새 빚").first()
    assert cat is not None
    assert cat.is_liability is True
    assert cat.report_group is None


def test_edit_of_another_households_category_is_404(app, db, couple, members, categories):
    other_couple = Couple(name="다른집", invite_code="OTHER1234")
    db.session.add(other_couple)
    db.session.flush()
    other_cat = Category(couple_id=other_couple.id, name="남의 카테고리", icon="x",
                          color="#000000", is_liability=False, report_group="cash",
                          sort_order=0)
    db.session.add(other_cat)
    db.session.flush()

    client = app.test_client()
    _login(client, app)

    r = client.get(f"/categories/{other_cat.id}/edit")
    assert r.status_code == 404


def test_delete_blocked_when_it_is_the_last_category(app, db, couple, members):
    only = Category(couple_id=couple.id, name="유일한카테고리", icon="x", color="#000",
                     is_liability=False, report_group="cash", sort_order=0)
    db.session.add(only)
    db.session.flush()

    client = app.test_client()
    _login(client, app)

    r = client.post(f"/categories/{only.id}/delete", data={}, follow_redirects=True)

    assert "최소 1개 이상" in r.data.decode("utf-8")
    assert db.session.get(Category, only.id) is not None


def test_delete_with_assets_and_no_reassign_target_is_rejected(app, db, couple, members, categories):
    cash = categories["현금"]
    asset = Asset(couple_id=couple.id, category_id=cash.id, name="계좌")
    db.session.add(asset)
    db.session.flush()

    client = app.test_client()
    _login(client, app)

    r = client.post(f"/categories/{cash.id}/delete", data={}, follow_redirects=True)

    assert "삭제할 수 없습니다" in r.data.decode("utf-8")
    assert db.session.get(Category, cash.id) is not None
    assert db.session.get(Asset, asset.id).category_id == cash.id


def test_delete_with_assets_and_valid_target_reassigns_and_deletes(app, db, couple, members, categories):
    cash = categories["현금"]
    invest = categories["투자"]
    asset = Asset(couple_id=couple.id, category_id=cash.id, name="계좌")
    db.session.add(asset)
    db.session.flush()

    client = app.test_client()
    _login(client, app)

    r = client.post(f"/categories/{cash.id}/delete",
                     data={"reassign_to": str(invest.id)}, follow_redirects=True)

    assert "삭제되었습니다" in r.data.decode("utf-8")
    assert db.session.get(Category, cash.id) is None
    assert db.session.get(Asset, asset.id).category_id == invest.id


def test_move_swaps_sort_order_with_neighbour(app, db, couple, members, categories):
    cash = categories["현금"]      # sort_order 0
    invest = categories["투자"]    # sort_order 1
    assert cash.sort_order < invest.sort_order

    client = app.test_client()
    _login(client, app)

    client.post(f"/categories/{invest.id}/move", data={"dir": "up"}, follow_redirects=True)

    db.session.refresh(cash)
    db.session.refresh(invest)
    assert invest.sort_order < cash.sort_order
