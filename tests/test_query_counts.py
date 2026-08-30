"""Regression guards for the N+1 fixes in Round 3 (see WORKLOG.md).

Asserts that hitting the dashboard, goals index, and refresh-prices routes
issues a bounded number of SQL queries regardless of how many assets the
household has — a query count that scales with asset count is exactly the
bug that was fixed (couple.assets accessed lazily, then .holdings/.category
touched per asset one at a time).
"""
import json
from decimal import Decimal

from sqlalchemy import event

from app.extensions import db
from app.models import Asset, Goal, Holding


def _make_many_assets(couple, category, n=15):
    ids = []
    for i in range(n):
        a = Asset(couple_id=couple.id, category_id=category.id, name=f"asset-{i}")
        db.session.add(a)
        db.session.flush()
        db.session.add(Holding(asset_id=a.id, kind="cash", currency="KRW", amount=1000))
        ids.append(a.id)
    db.session.commit()
    return ids


def _make_linked_goals(couple, category_id, n=3):
    """Goals linked to a category — current_amount() then actually walks
    every asset (not the manual_amount early return), which is what
    exercises the couple.assets N+1."""
    for i in range(n):
        db.session.add(Goal(couple_id=couple.id, name=f"goal-{i}",
                             target_amount=Decimal(1000),
                             linked_category_ids=json.dumps([category_id]),
                             linked_asset_ids="[]"))
    db.session.commit()


def _count_queries(fn):
    queries = []

    def _log(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(db.engine, "before_cursor_execute", _log)
    try:
        fn()
    finally:
        event.remove(db.engine, "before_cursor_execute", _log)
    return queries


def _login(client, app, email, password):
    app.config["WTF_CSRF_ENABLED"] = False
    r = client.post("/login", data={"email": email, "password": password},
                     follow_redirects=True)
    assert "로그아웃" in r.data.decode("utf-8"), (
        "login did not actually succeed — fixture broken, "
        "the query counts below would be meaningless"
    )
    return r


def test_dashboard_query_count_does_not_scale_with_asset_count(app, db, couple, members, categories):
    cat = categories["현금"]
    _make_many_assets(couple, cat, n=15)
    # Goals must be LINKED (to a category/asset) so goal_view ->
    # current_amount actually walks the asset list instead of taking the
    # manual_amount early-return — that walk is what used to N+1.
    _make_linked_goals(couple, cat.id, n=3)

    client = app.test_client()
    _login(client, app, "a@example.com", "password123")

    queries = _count_queries(lambda: client.get("/dashboard"))
    # Measured with these fixtures: 10 queries, same before and after this
    # round's fix here specifically — dashboard() already did its own
    # eager-loaded assets query before calling goal_view, which happened to
    # pre-populate every asset's holdings/category in the identity map, so
    # goal_view's old couple.assets access was riding on that rather than
    # N+1'ing on its own. The explicit assets-passing is still kept: it's
    # the correct, self-contained interface (see services/goals.py) and
    # doesn't depend on a call in a *different* module having already
    # warmed the cache for it. Bound is a generous ceiling, not a tight one.
    assert len(queries) <= 15, f"expected a bounded query count, got {len(queries)}"


def test_goals_index_query_count_does_not_scale_with_asset_count(app, db, couple, members, categories):
    cat = categories["현금"]
    _make_many_assets(couple, cat, n=15)
    _make_linked_goals(couple, cat.id, n=3)

    client = app.test_client()
    _login(client, app, "a@example.com", "password123")

    queries = _count_queries(lambda: client.get("/goals/"))
    # Unlike dashboard(), goals/routes.py::index() had nothing upstream
    # warming the identity map, yet the old couple.assets path still only
    # measured 2 queries here (5 after adding the explicit eager-load).
    # Kept for the same reason as the dashboard test: an explicit,
    # self-contained assets list is the more robust interface regardless
    # of what a particular SQLAlchemy version's caching happens to do.
    assert len(queries) <= 15, f"expected a bounded query count, got {len(queries)}"


def test_refresh_prices_query_count_does_not_scale_with_asset_count(app, db, couple, members, categories):
    _make_many_assets(couple, categories["현금"], n=15)

    client = app.test_client()
    _login(client, app, "a@example.com", "password123")

    queries = _count_queries(lambda: client.post("/assets/refresh-prices", follow_redirects=True))
    # Measured: 17 after the fix vs. 45 before, with these 15 assets — no
    # earlier request warmed the identity map here, so the raw N+1 (one
    # holdings query per asset, from both the route itself and the
    # _sync_snapshot() call it triggers) was fully exposed. This is the
    # clearest, most reproducible win of this round.
    assert len(queries) <= 25, f"expected a bounded query count, got {len(queries)}"
