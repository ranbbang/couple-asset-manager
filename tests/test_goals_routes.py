"""Tests for app/goals/routes.py — no route-level coverage before this
round (services/goals.py itself was already unit-tested in Round 3)."""
import json
import re

from app.extensions import db
from app.models import Asset, Couple, Goal


def _login(client, app, email="a@example.com", password="password123"):
    app.config["WTF_CSRF_ENABLED"] = False
    r = client.post("/login", data={"email": email, "password": password},
                     follow_redirects=True)
    assert "로그아웃" in r.data.decode("utf-8"), "login did not actually succeed"
    return r


def test_create_goal_with_linked_category(app, db, couple, members, categories):
    cat = categories["현금"]
    client = app.test_client()
    _login(client, app)

    r = client.post("/goals/new", data={
        "name": "비상금", "target_amount": "1000000",
        "owner": "joint", "linked_categories": [str(cat.id)],
        "saved_amount": "0", "stocks_amount": "0",
    }, follow_redirects=True)

    assert "추가되었습니다" in r.data.decode("utf-8")
    goal = Goal.query.filter_by(name="비상금").first()
    assert goal is not None
    assert goal.category_id_list == [cat.id]
    assert goal.owner_id is None


def test_create_goal_with_personal_owner(app, db, couple, members, categories):
    a, _ = members
    client = app.test_client()
    _login(client, app)

    client.post("/goals/new", data={
        "name": "개인 목표", "target_amount": "500000",
        "owner": str(a.id), "saved_amount": "0", "stocks_amount": "0",
    }, follow_redirects=True)

    goal = Goal.query.filter_by(name="개인 목표").first()
    assert goal.owner_id == a.id


def test_edit_preserves_and_updates_links(app, db, couple, members, categories):
    cat = categories["현금"]
    goal = Goal(couple_id=couple.id, name="목표", target_amount=1000,
                linked_category_ids=json.dumps([cat.id]), linked_asset_ids="[]")
    db.session.add(goal)
    db.session.commit()

    client = app.test_client()
    _login(client, app)

    # GET should preselect the existing link (rendered as a checked checkbox).
    r = client.get(f"/goals/{goal.id}/edit")
    body = r.data.decode("utf-8")
    match = re.search(rf'name="linked_categories" value="{cat.id}"\s*(\w*)>', body)
    assert match and match.group(1) == "checked", body

    # POST with the category unlinked should clear it.
    client.post(f"/goals/{goal.id}/edit", data={
        "name": "목표", "target_amount": "2000000", "owner": "joint",
        "saved_amount": "0", "stocks_amount": "0",
    }, follow_redirects=True)

    db.session.refresh(goal)
    assert goal.category_id_list == []
    assert goal.target_amount == 2000000


def test_edit_of_another_households_goal_is_404(app, db, couple, members, categories):
    other = Couple(name="다른집", invite_code="GOALOTHR1")
    db.session.add(other)
    db.session.flush()
    other_goal = Goal(couple_id=other.id, name="남의 목표", target_amount=1)
    db.session.add(other_goal)
    db.session.flush()

    client = app.test_client()
    _login(client, app)

    r = client.get(f"/goals/{other_goal.id}/edit")
    assert r.status_code == 404


def test_delete_removes_goal(app, db, couple, members, categories):
    goal = Goal(couple_id=couple.id, name="삭제될 목표", target_amount=1000)
    db.session.add(goal)
    db.session.commit()
    goal_id = goal.id

    client = app.test_client()
    _login(client, app)

    r = client.post(f"/goals/{goal_id}/delete", data={}, follow_redirects=True)

    assert "삭제되었습니다" in r.data.decode("utf-8")
    assert db.session.get(Goal, goal_id) is None


def test_delete_of_another_households_goal_is_404(app, db, couple, members, categories):
    other = Couple(name="다른집2", invite_code="GOALOTHR2")
    db.session.add(other)
    db.session.flush()
    other_goal = Goal(couple_id=other.id, name="남의 목표2", target_amount=1)
    db.session.add(other_goal)
    db.session.commit()

    client = app.test_client()
    _login(client, app)

    r = client.post(f"/goals/{other_goal.id}/delete", data={})
    assert r.status_code == 404
    # Must still exist — the cross-tenant request must not have deleted it.
    assert db.session.get(Goal, other_goal.id) is not None


def test_liability_categories_are_not_offered_as_link_choices(app, db, couple, members, categories):
    client = app.test_client()
    _login(client, app)

    r = client.get("/goals/new")
    body = r.data.decode("utf-8")
    debt_cat = categories["빚"]
    # The liability category must not appear as a selectable linked category.
    assert f'value="{debt_cat.id}"' not in body
