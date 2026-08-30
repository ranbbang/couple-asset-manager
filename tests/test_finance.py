"""Tests for app/services/finance.py — the core money-aggregation logic.

This module had zero test coverage before this file; it drives every total
shown on the dashboard, reports, and snapshots, so a regression here is a
silently wrong net-worth figure. Uses only the in-memory test DB (see
conftest.py) — never touches app.db.
"""
from decimal import Decimal

from app.extensions import db
from app.models import Asset, Holding
from app.services import finance

RATE = Decimal("1350")


def make_asset(couple, category, owner=None, exclude=False, holdings=()):
    a = Asset(
        couple_id=couple.id, owner_id=owner.id if owner else None,
        category_id=category.id, name="test", exclude_from_stats=exclude,
    )
    db.session.add(a)
    db.session.flush()
    for h in holdings:
        db.session.add(Holding(asset_id=a.id, **h))
    db.session.flush()
    return a


def test_total_assets_excludes_liabilities(db, couple, categories):
    cash = make_asset(couple, categories["현금"],
                       holdings=[{"kind": "cash", "currency": "KRW", "amount": 1_000_000}])
    debt = make_asset(couple, categories["빚"],
                       holdings=[{"kind": "cash", "currency": "KRW", "amount": 300_000}])
    assets = [cash, debt]

    assert finance.total_assets(assets, RATE) == Decimal("1000000")
    assert finance.total_liabilities(assets, RATE) == Decimal("300000")
    assert finance.net_worth(assets, RATE) == Decimal("700000")


def test_exclude_from_stats_is_dropped_everywhere(db, couple, categories):
    counted = make_asset(couple, categories["현금"],
                          holdings=[{"kind": "cash", "currency": "KRW", "amount": 500_000}])
    hidden = make_asset(couple, categories["현금"], exclude=True,
                         holdings=[{"kind": "cash", "currency": "KRW", "amount": 999_999_999}])
    assets = [counted, hidden]

    assert finance.total_assets(assets, RATE) == Decimal("500000")
    assert len(finance.included(assets)) == 1


def test_usd_conversion_and_exposure_pct(db, couple, categories):
    usd_asset = make_asset(couple, categories["투자"],
                            holdings=[{"kind": "cash", "currency": "USD", "amount": 100}])
    krw_asset = make_asset(couple, categories["현금"],
                            holdings=[{"kind": "cash", "currency": "KRW", "amount": 1_350_000}])
    assets = [usd_asset, krw_asset]

    # 100 USD @ 1350 == 135,000 KRW; total assets = 135,000 + 1,350,000
    exposure = finance.usd_exposure(assets, RATE)
    assert exposure["krw"] == Decimal("135000")
    assert exposure["pct"] == 9.1  # 135,000 / 1,485,000 * 100, rounded


def test_usd_exposure_pct_is_none_when_no_assets(db, couple):
    assert finance.usd_exposure([], RATE)["pct"] is None


def test_real_estate_excluded_from_net_worth_excl_re(db, couple, categories):
    house = make_asset(couple, categories["부동산"],
                        holdings=[{"kind": "cash", "currency": "KRW", "amount": 500_000_000}])
    cash = make_asset(couple, categories["현금"],
                       holdings=[{"kind": "cash", "currency": "KRW", "amount": 10_000_000}])
    assets = [house, cash]

    assert finance.real_estate_total(assets, RATE) == Decimal("500000000")
    assert finance.net_worth_excl_real_estate(assets, RATE) == Decimal("10000000")


def test_real_estate_liability_not_double_counted_as_asset(db, couple, categories):
    """A liability category flagged is_real_estate (edge case, shouldn't
    normally happen via the UI) must not show up in real_estate_total, which
    is meant to be a subset of assets, not liabilities."""
    categories["빚"].is_real_estate = True
    db.session.flush()
    mortgage = make_asset(couple, categories["빚"],
                           holdings=[{"kind": "cash", "currency": "KRW", "amount": 200_000_000}])

    assert finance.real_estate_total([mortgage], RATE) == Decimal("0")


def test_liquid_total_only_counts_liquid_categories(db, couple, categories):
    categories["현금"].is_liquid = True
    db.session.flush()
    liquid = make_asset(couple, categories["현금"],
                         holdings=[{"kind": "cash", "currency": "KRW", "amount": 2_000_000}])
    illiquid = make_asset(couple, categories["연금"],
                           holdings=[{"kind": "cash", "currency": "KRW", "amount": 50_000_000}])

    assert finance.liquid_total([liquid, illiquid], RATE) == Decimal("2000000")


def test_owner_breakdown_groups_joint_assets_under_none(db, couple, members, categories):
    a, b = members
    a_asset = make_asset(couple, categories["현금"], owner=a,
                          holdings=[{"kind": "cash", "currency": "KRW", "amount": 100}])
    b_asset = make_asset(couple, categories["현금"], owner=b,
                          holdings=[{"kind": "cash", "currency": "KRW", "amount": 200}])
    joint = make_asset(couple, categories["현금"], owner=None,
                        holdings=[{"kind": "cash", "currency": "KRW", "amount": 300}])

    rows = finance.owner_breakdown([a_asset, b_asset, joint], RATE, members)
    by_label = {r["label"]: r for r in rows}

    assert by_label["에이"]["net"] == Decimal("100")
    assert by_label["비"]["net"] == Decimal("200")
    assert by_label["공동"]["net"] == Decimal("300")


def test_owner_breakdown_drops_empty_rows(db, couple, members, categories):
    a, _b = members
    a_asset = make_asset(couple, categories["현금"], owner=a,
                          holdings=[{"kind": "cash", "currency": "KRW", "amount": 1}])
    rows = finance.owner_breakdown([a_asset], RATE, members)
    assert {r["label"] for r in rows} == {"에이"}


def test_category_breakdown_skips_zero_amount_categories(db, couple, categories):
    nonzero = make_asset(couple, categories["현금"],
                          holdings=[{"kind": "cash", "currency": "KRW", "amount": 1_000}])
    zero = make_asset(couple, categories["투자"],
                       holdings=[{"kind": "cash", "currency": "KRW", "amount": 0}])

    rows = finance.category_breakdown([nonzero, zero], RATE)
    names = {r["category"] for r in rows}
    assert "현금" in names
    assert "투자" not in names


def test_currency_split_multi_currency_asset_counts_in_both_buckets(db, couple, categories):
    mixed = make_asset(couple, categories["투자"], holdings=[
        {"kind": "cash", "currency": "KRW", "amount": 1_000_000},
        {"kind": "cash", "currency": "USD", "amount": 50},
    ])
    split = finance.currency_split([mixed])
    assert split["KRW"]["assets"] == Decimal("1000000")
    assert split["USD"]["assets"] == Decimal("50")
    assert split["KRW"]["count"] == 1
    assert split["USD"]["count"] == 1
