"""Currency-aware financial calculations over a couple's accounts (assets).

Each account holds one or more Holdings (cash and/or stocks); an account's value
is the sum of its holdings converted to the KRW base currency. Accounts flagged
`exclude_from_stats` are dropped from every aggregation here so the dashboard,
overview, reports, and snapshots all agree.
"""
from decimal import Decimal

from ..constants import CURRENCIES, DEFAULT_META


def _d(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value or 0))


def included(assets):
    """Accounts that count toward statistics (exclude flag off)."""
    return [a for a in assets if not a.exclude_from_stats]


def _is_liability(asset) -> bool:
    return bool(asset.category and asset.category.is_liability)


def _is_real_estate(asset) -> bool:
    return bool(asset.category and asset.category.is_real_estate)


# --- KRW base totals ------------------------------------------------------
def total_assets(assets, rate) -> Decimal:
    return sum(
        (a.value_krw(rate) for a in included(assets) if not _is_liability(a)),
        Decimal(0),
    )


def total_liabilities(assets, rate) -> Decimal:
    return sum(
        (a.value_krw(rate) for a in included(assets) if _is_liability(a)),
        Decimal(0),
    )


def real_estate_total(assets, rate) -> Decimal:
    """Sum of real-estate accounts (non-liability)."""
    return sum(
        (a.value_krw(rate) for a in included(assets)
         if _is_real_estate(a) and not _is_liability(a)),
        Decimal(0),
    )


def net_worth(assets, rate) -> Decimal:
    return total_assets(assets, rate) - total_liabilities(assets, rate)


def net_worth_excl_real_estate(assets, rate) -> Decimal:
    """Net worth with real-estate value removed (req: 부동산 제외 순자산)."""
    return net_worth(assets, rate) - real_estate_total(assets, rate)


def category_breakdown(assets, rate) -> list[dict]:
    """Per-category KRW totals with share-of-total-assets, ordered by category."""
    buckets = {}  # category_id -> {category, amount}
    for a in included(assets):
        cat = a.category
        if cat is None:
            continue
        b = buckets.setdefault(cat.id, {"cat": cat, "amount": Decimal(0)})
        b["amount"] += a.value_krw(rate)

    assets_sum = total_assets(assets, rate)
    rows = []
    for b in sorted(buckets.values(), key=lambda x: (x["cat"].sort_order, x["cat"].id)):
        cat, amount = b["cat"], b["amount"]
        if amount == 0:
            continue
        share = 0.0
        if not cat.is_liability and assets_sum > 0:
            share = round(float(amount / assets_sum * 100), 1)
        rows.append(
            {
                "id": cat.id,
                "category": cat.name,
                "amount": amount,
                "icon": cat.icon,
                "color": cat.color,
                "hint": "",
                "is_liability": cat.is_liability,
                "is_real_estate": cat.is_real_estate,
                "share": share,
            }
        )
    return rows


def dashboard_summary(assets, rate) -> dict:
    return {
        "total_assets": total_assets(assets, rate),
        "total_liabilities": total_liabilities(assets, rate),
        "net_worth": net_worth(assets, rate),
        "real_estate": real_estate_total(assets, rate),
        "net_worth_excl_re": net_worth_excl_real_estate(assets, rate),
        "breakdown": category_breakdown(assets, rate),
    }


# --- Per-currency split (native amounts, no conversion) -------------------
def currency_split(assets) -> dict:
    """Native per-currency totals keyed by category id, e.g. {'KRW': {...}}.

    Iterates holdings so a multi-currency account contributes to both buckets.
    """
    result = {cur: {"assets": Decimal(0), "liabilities": Decimal(0),
                    "by_category": {}, "count": 0} for cur in CURRENCIES}
    for a in included(assets):
        cat = a.category
        if cat is None:
            continue
        for h in a.holdings:
            cur = h.currency
            if cur not in result:
                result[cur] = {"assets": Decimal(0), "liabilities": Decimal(0),
                               "by_category": {}, "count": 0}
            native = h.value_native
            bucket = result[cur]
            bucket["by_category"][cat.id] = bucket["by_category"].get(cat.id, Decimal(0)) + native
            if cat.is_liability:
                bucket["liabilities"] += native
            else:
                bucket["assets"] += native
    for cur, data in result.items():
        data["net"] = data["assets"] - data["liabilities"]
        data["count"] = sum(
            1 for a in included(assets) for h in a.holdings if h.currency == cur
        )
    return result


def overview_data(assets, cached_rate) -> dict:
    """JSON-serialisable payload for the Asset Overview toggle + charts."""
    active = included(assets)
    cats = {}
    for a in active:
        if a.category and a.category.id not in cats:
            cats[a.category.id] = a.category
    ordered_cats = sorted(cats.values(), key=lambda c: (c.sort_order, c.id))

    split = currency_split(assets)
    by_currency = {
        cur: {
            "byCategory": {str(cid): float(amt) for cid, amt in data["by_category"].items()},
            "assets": float(data["assets"]),
            "liabilities": float(data["liabilities"]),
            "count": data["count"],
        }
        for cur, data in split.items()
    }
    categories = [
        {
            "id": str(c.id),
            "label": c.name,
            "icon": c.icon or DEFAULT_META["icon"],
            "color": c.color or DEFAULT_META["color"],
            "is_liability": c.is_liability,
        }
        for c in ordered_cats
    ]
    return {
        "categories": categories,
        "byCurrency": by_currency,
        "cachedRate": float(cached_rate),
    }
