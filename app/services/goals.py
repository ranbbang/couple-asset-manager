"""Goal progress: compute current amount from linked assets/categories.

A goal can link to whole categories and/or individual accounts. When linked, its
current amount is the live KRW value of those assets (auto-updating as balances
and stock prices change). With no links, it falls back to the manually entered
saved + stocks amounts.
"""
from decimal import Decimal

from .finance import _is_liability


def current_amount(goal, couple, rate) -> Decimal:
    """Live current amount for a goal in KRW."""
    if not goal.is_linked:
        return goal.manual_amount

    cat_ids = set(goal.category_id_list)
    asset_ids = set(goal.asset_id_list)
    total = Decimal(0)
    seen = set()
    for a in couple.assets:
        if a.exclude_from_stats or _is_liability(a):
            continue
        if a.id in seen:
            continue
        if (a.category_id in cat_ids) or (a.id in asset_ids):
            total += a.value_krw(rate)
            seen.add(a.id)
    return total


def progress_pct(goal, couple, rate) -> int:
    target = goal.target_amount or Decimal(0)
    if target <= 0:
        return 0
    pct = current_amount(goal, couple, rate) / target * 100
    return min(int(pct), 100)


def goal_view(goal, couple, rate) -> dict:
    """Bundle the numbers a goal card needs."""
    cur = current_amount(goal, couple, rate)
    return {
        "current": cur,
        "pct": progress_pct(goal, couple, rate),
        "linked": goal.is_linked,
    }
