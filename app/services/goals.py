"""Goal progress: compute current amount from linked assets/categories.

A goal can link to whole categories and/or individual accounts. When linked, its
current amount is the live KRW value of those assets (auto-updating as balances
and stock prices change). With no links, it falls back to the manually entered
saved + stocks amounts.
"""
import math
from datetime import date
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


def estimate_completion(goal, current, monthly_gain) -> date | None:
    """Projected month the goal is reached at the recent average pace.

    Returns the first day of the estimated month, or None when it can't be
    estimated (already reached, no/negative pace, or absurdly far out).
    """
    target = goal.target_amount or Decimal(0)
    remaining = target - current
    if remaining <= 0 or not monthly_gain or monthly_gain <= 0:
        return None
    months = math.ceil(remaining / monthly_gain)
    if months > 50 * 12:  # not a meaningful projection
        return None
    today = date.today()
    total = today.year * 12 + (today.month - 1) + months
    return date(total // 12, total % 12 + 1, 1)


def goal_view(goal, couple, rate, monthly_gain=None) -> dict:
    """Bundle the numbers a goal card needs."""
    cur = current_amount(goal, couple, rate)
    return {
        "current": cur,
        "pct": progress_pct(goal, couple, rate),
        "linked": goal.is_linked,
        "eta": estimate_completion(goal, cur, monthly_gain),
    }
