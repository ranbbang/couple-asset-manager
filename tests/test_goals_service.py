"""Tests for app/services/goals.py.

Also locks in the recent signature change (couple -> assets): current_amount
/ progress_pct / goal_view now take a pre-loaded assets list instead of a
Couple, so callers can pass one already eager-loaded (fixing an N+1 — see
WORKLOG.md Round 3).
"""
from decimal import Decimal

from app.extensions import db
from app.models import Asset, Goal, Holding
from app.services import goals as goals_svc

RATE = Decimal("1350")


def make_asset(couple, category, exclude=False, amount=0):
    a = Asset(couple_id=couple.id, category_id=category.id, name="test",
              exclude_from_stats=exclude)
    db.session.add(a)
    db.session.flush()
    db.session.add(Holding(asset_id=a.id, kind="cash", currency="KRW", amount=amount))
    db.session.flush()
    return a


def make_goal(couple, target, cat_ids=None, asset_ids=None, saved=0, stocks=0):
    import json
    g = Goal(
        couple_id=couple.id, name="목표", target_amount=Decimal(target),
        saved_amount=Decimal(saved), stocks_amount=Decimal(stocks),
        linked_category_ids=json.dumps(cat_ids or []),
        linked_asset_ids=json.dumps(asset_ids or []),
    )
    db.session.add(g)
    db.session.flush()
    return g


def test_unlinked_goal_uses_manual_amount(db, couple):
    g = make_goal(couple, target=1_000_000, saved=300_000, stocks=100_000)
    assert goals_svc.current_amount(g, [], RATE) == Decimal("400000")


def test_linked_goal_sums_matching_category_and_asset(db, couple, categories):
    cat = categories["현금"]
    other_cat = categories["투자"]
    a1 = make_asset(couple, cat, amount=1_000_000)
    a2 = make_asset(couple, other_cat, amount=500_000)  # linked directly by id
    a3 = make_asset(couple, other_cat, amount=999_999)  # not linked at all
    g = make_goal(couple, target=1_000_000, cat_ids=[cat.id], asset_ids=[a2.id])

    total = goals_svc.current_amount(g, [a1, a2, a3], RATE)
    assert total == Decimal("1500000")


def test_linked_goal_excludes_liability_and_hidden_assets(db, couple, categories):
    cat = categories["현금"]
    counted = make_asset(couple, cat, amount=1_000_000)
    hidden = make_asset(couple, cat, exclude=True, amount=1_000_000)
    debt_cat = categories["빚"]
    debt = make_asset(couple, debt_cat, amount=1_000_000)
    g = make_goal(couple, target=1, cat_ids=[cat.id, debt_cat.id])

    total = goals_svc.current_amount(g, [counted, hidden, debt], RATE)
    assert total == Decimal("1000000")


def test_linked_goal_does_not_double_count_asset_matched_both_ways(db, couple, categories):
    cat = categories["현금"]
    a = make_asset(couple, cat, amount=1_000_000)
    g = make_goal(couple, target=1, cat_ids=[cat.id], asset_ids=[a.id])

    assert goals_svc.current_amount(g, [a], RATE) == Decimal("1000000")


def test_progress_pct_caps_at_100_and_guards_zero_target(db, couple, categories):
    cat = categories["현금"]
    a = make_asset(couple, cat, amount=5_000_000)
    over_target = make_goal(couple, target=1_000_000, cat_ids=[cat.id])
    zero_target = make_goal(couple, target=0, cat_ids=[cat.id])

    assert goals_svc.progress_pct(over_target, [a], RATE) == 100
    assert goals_svc.progress_pct(zero_target, [a], RATE) == 0


def test_estimate_completion_none_when_no_gain_or_already_reached():
    goal = Goal(name="x", target_amount=Decimal(1000), owner_id=None)
    assert goals_svc.estimate_completion(goal, Decimal(1000), Decimal(10)) is None  # reached
    assert goals_svc.estimate_completion(goal, Decimal(0), None) is None  # no gain
    assert goals_svc.estimate_completion(goal, Decimal(0), Decimal(-5)) is None  # negative gain
