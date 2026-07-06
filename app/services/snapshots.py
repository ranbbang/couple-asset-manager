"""Monthly snapshot capture and report-data aggregation.

Snapshots store KRW-base totals so trends are comparable month to month. Each
snapshot stores per-category totals (by name), per-report-group totals (the
stable analytical buckets used by trend charts), per-currency native totals,
plus real-estate value and net worth excluding real estate. Accounts flagged
`exclude_from_stats` are omitted.
"""
import json
from datetime import date
from decimal import Decimal

from ..constants import REPORT_GROUP_KEYS, REPORT_GROUPS
from ..extensions import db
from ..models import AssetSnapshot
from .finance import included


def month_start(d: date | None = None) -> date:
    d = d or date.today()
    return date(d.year, d.month, 1)


def _compute(assets, rate):
    """Return a dict of all the KRW totals a snapshot needs."""
    cat_totals = {}
    group_totals = {k: Decimal(0) for k in REPORT_GROUP_KEYS}
    cur_totals = {"KRW": Decimal(0), "USD": Decimal(0)}
    assets_krw = Decimal(0)
    liab_krw = Decimal(0)
    re_krw = Decimal(0)

    for a in included(assets):
        cat = a.category
        if cat is None:
            continue
        krw = a.value_krw(rate)
        cat_totals[cat.name] = cat_totals.get(cat.name, Decimal(0)) + krw
        for cur, native in a.native_by_currency().items():
            cur_totals.setdefault(cur, Decimal(0))
            cur_totals[cur] += native
        if cat.is_liability:
            liab_krw += krw
        else:
            assets_krw += krw
            if cat.report_group in group_totals:
                group_totals[cat.report_group] += krw
            if cat.is_real_estate:
                re_krw += krw

    return {
        "cat_totals": cat_totals,
        "group_totals": group_totals,
        "cur_totals": cur_totals,
        "assets_krw": assets_krw,
        "liab_krw": liab_krw,
        "re_krw": re_krw,
    }


def capture_snapshot(couple, rate, taken_on: date | None = None) -> AssetSnapshot:
    """Create or update (upsert) the snapshot for a given month."""
    taken_on = taken_on or month_start()
    c = _compute(couple.assets, rate)

    snap = AssetSnapshot.query.filter_by(
        couple_id=couple.id, taken_on=taken_on
    ).first()
    if snap is None:
        snap = AssetSnapshot(couple_id=couple.id, taken_on=taken_on)
        db.session.add(snap)

    net = c["assets_krw"] - c["liab_krw"]
    snap.total_assets_krw = c["assets_krw"]
    snap.total_liabilities_krw = c["liab_krw"]
    snap.net_worth_krw = net
    snap.real_estate_krw = c["re_krw"]
    snap.net_worth_excl_re_krw = net - c["re_krw"]
    snap.category_totals = json.dumps({k: float(v) for k, v in c["cat_totals"].items()})
    snap.group_totals = json.dumps({k: float(v) for k, v in c["group_totals"].items()})
    snap.currency_totals = json.dumps({k: float(v) for k, v in c["cur_totals"].items()})
    snap.rate_used = Decimal(str(rate))
    return snap


def refresh_current_month(couple, rate) -> AssetSnapshot:
    snap = capture_snapshot(couple, rate, month_start())
    db.session.commit()
    return snap


def previous_month_snapshot(couple) -> AssetSnapshot | None:
    """The most recent snapshot before the current month (for MoM deltas)."""
    return (
        AssetSnapshot.query.filter(
            AssetSnapshot.couple_id == couple.id,
            AssetSnapshot.taken_on < month_start(),
        )
        .order_by(AssetSnapshot.taken_on.desc())
        .first()
    )


def month_over_month(couple, current_net_worth) -> dict | None:
    """MoM change of net worth vs the last pre-current-month snapshot.

    Returns {"delta": Decimal, "pct": float|None, "since": date} or None when
    there is no earlier month to compare against.
    """
    prev = previous_month_snapshot(couple)
    if prev is None:
        return None
    prev_net = Decimal(str(prev.net_worth_krw or 0))
    delta = Decimal(str(current_net_worth)) - prev_net
    pct = round(float(delta / abs(prev_net) * 100), 1) if prev_net else None
    return {"delta": delta, "pct": pct, "since": prev.taken_on}


def flow_split(couple, assets, rate) -> dict | None:
    """Rough cash-vs-investment split of the MoM change (no transaction data).

    Compares live report-group totals against the last pre-current-month
    snapshot: the 'cash' group's delta approximates money saved/spent, the
    remaining groups' delta approximates investment value change.
    """
    prev = previous_month_snapshot(couple)
    if prev is None:
        return None
    cur = _compute(assets, rate)["group_totals"]
    prev_groups = json.loads(prev.group_totals or "{}")
    invest_keys = [k for k in REPORT_GROUP_KEYS if k != "cash"]
    cash_delta = cur["cash"] - Decimal(str(prev_groups.get("cash", 0)))
    invest_delta = sum((cur[k] for k in invest_keys), Decimal(0)) - Decimal(
        str(sum(prev_groups.get(k, 0) for k in invest_keys))
    )
    return {"cash": cash_delta, "invest": invest_delta}


def avg_monthly_gain(couple, months: int = 6) -> Decimal | None:
    """Average month-over-month net-worth increase over the recent snapshots.

    Uses up to `months` consecutive deltas; needs at least two snapshots.
    Returns None when there isn't enough history.
    """
    snaps = history(couple)
    if len(snaps) < 2:
        return None
    recent = snaps[-(months + 1):]
    deltas = [
        Decimal(str(b.net_worth_krw or 0)) - Decimal(str(a.net_worth_krw or 0))
        for a, b in zip(recent, recent[1:])
    ]
    return sum(deltas, Decimal(0)) / len(deltas)


def history(couple) -> list[AssetSnapshot]:
    return (
        AssetSnapshot.query.filter_by(couple_id=couple.id)
        .order_by(AssetSnapshot.taken_on.asc())
        .all()
    )


def report_data(couple) -> dict:
    """Aggregate snapshot history into a JSON payload for the Reports charts."""
    snaps = history(couple)
    months, net_worth, total_assets, nw_excl_re = [], [], [], []
    groups = {k: [] for k in REPORT_GROUP_KEYS}

    for s in snaps:
        g = json.loads(s.group_totals or "{}")
        months.append(s.taken_on.strftime("%Y-%m"))
        net_worth.append(float(s.net_worth_krw))
        total_assets.append(float(s.total_assets_krw))
        nw_excl_re.append(float(s.net_worth_excl_re_krw or 0))
        for k in REPORT_GROUP_KEYS:
            groups[k].append(float(g.get(k, 0.0)))

    # Current category metadata for the selectable ratio bar.
    cat_meta = {
        c.name: {"color": c.color, "group": c.report_group,
                 "is_liability": c.is_liability, "is_real_estate": c.is_real_estate}
        for c in couple.categories
    }

    latest = snaps[-1] if snaps else None
    latest_cats = json.loads(latest.category_totals) if latest else {}
    allocation = [
        {"label": name, "value": amt}
        for name, amt in latest_cats.items()
        if not cat_meta.get(name, {}).get("is_liability", False) and amt > 0
    ]

    # Categories available to the ratio bar (non-liability, with latest value),
    # in the couple's display order. Default-selected = investment + cash-equiv
    # report groups (the "투자 예수금 vs 투자금" view, excluding plain cash).
    ratio_categories = []
    for c in couple.categories:
        if c.is_liability:
            continue
        amt = float(latest_cats.get(c.name, 0.0))
        # Default selection: cash/investment groups EXCEPT the plain "현금" category
        default_on = c.report_group in ("cash", "investment") and c.name != "현금"
        ratio_categories.append({
            "name": c.name, "color": c.color, "group": c.report_group,
            "value": amt, "default": default_on,
        })

    latest_groups = {k: (groups[k][-1] if groups[k] else 0.0) for k in REPORT_GROUP_KEYS}

    return {
        "months": months,
        "netWorth": net_worth,
        "netWorthExclRe": nw_excl_re,
        "totalAssets": total_assets,
        "groups": groups,
        "groupMeta": {k: {"label": v["label"], "color": v["color"]}
                      for k, v in REPORT_GROUPS.items()},
        "latestGroups": latest_groups,
        "allocation": allocation,
        "ratioCategories": ratio_categories,
        "categoryColors": {name: m["color"] for name, m in cat_meta.items()},
        "latestAssets": float(latest.total_assets_krw) if latest else 0.0,
        "latestLiabilities": float(latest.total_liabilities_krw) if latest else 0.0,
        "latestRealEstate": float(latest.real_estate_krw or 0) if latest else 0.0,
        "hasData": bool(snaps),
    }
