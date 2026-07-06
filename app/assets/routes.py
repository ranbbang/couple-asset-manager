"""Account (asset) CRUD routes, scoped to the current user's household.

An account holds one or more holdings (cash and/or stock). Holdings are parsed
from dynamic form rows. Stock holdings are priced via the free quote service on
save and via the explicit "가격 새로고침" action.
"""
from decimal import Decimal, InvalidOperation

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from ..constants import CURRENCIES, HOLDING_CASH, HOLDING_STOCK
from ..decorators import couple_required
from ..extensions import db
from ..models import Asset, Category, Holding
from ..services import categories as categories_svc
from ..services import finance, fx, prices, snapshots
from ..services.activity import log_activity
from .forms import JOINT_OWNER_VALUE, AssetForm

assets_bp = Blueprint("assets", __name__, url_prefix="/assets")


def _couple_categories():
    return categories_svc.ordered(current_user.couple)


def _populate_choices(form: AssetForm) -> None:
    form.category.choices = [
        (c.id, f"{c.icon}  {c.name}{'  · 부채' if c.is_liability else ''}")
        for c in _couple_categories()
    ]
    owner_choices = [(JOINT_OWNER_VALUE, "🤝  공동 (둘이 함께)")]
    for member in current_user.couple.members:
        owner_choices.append((str(member.id), f"🙋  {member.display_name}"))
    form.owner.choices = owner_choices


def _resolve_owner_id(form: AssetForm):
    if form.owner.data == JOINT_OWNER_VALUE:
        return None
    member_ids = {str(m.id) for m in current_user.couple.members}
    if form.owner.data in member_ids:
        return int(form.owner.data)
    return None


def _get_category(category_id: int) -> Category:
    cat = db.session.get(Category, category_id)
    if cat is None or cat.couple_id != current_user.couple_id:
        abort(400)
    return cat


def _get_owned_asset(asset_id: int) -> Asset:
    asset = db.session.get(Asset, asset_id)
    if asset is None or asset.couple_id != current_user.couple_id:
        abort(404)
    return asset


def _sync_snapshot() -> None:
    snapshots.refresh_current_month(current_user.couple, fx.get_cached_rate())


def _won(value) -> str:
    """₩-formatted amount for activity-feed detail lines."""
    return f"₩{float(value):,.0f}"


def _dec(value, default="0") -> Decimal:
    try:
        return Decimal(str(value).replace(",", "").strip() or default)
    except (InvalidOperation, AttributeError):
        return Decimal(default)


def _parse_holdings() -> list[Holding]:
    """Build Holding rows from the dynamic form arrays.

    Cash rows need a non-empty amount; stock rows need a ticker + quantity.
    Empty rows are skipped. Returns a list of unsaved Holding objects.
    """
    kinds = request.form.getlist("holding_kind")
    currencies = request.form.getlist("holding_currency")
    labels = request.form.getlist("holding_label")
    amounts = request.form.getlist("holding_amount")
    tickers = request.form.getlist("holding_ticker")
    qtys = request.form.getlist("holding_qty")

    holdings = []
    for i, kind in enumerate(kinds):
        cur = currencies[i] if i < len(currencies) else "KRW"
        if cur not in CURRENCIES:
            cur = "KRW"
        if kind == HOLDING_STOCK:
            ticker = (tickers[i] if i < len(tickers) else "").strip().upper()
            qty = _dec(qtys[i] if i < len(qtys) else 0)
            if not ticker or qty <= 0:
                continue
            holdings.append(Holding(
                kind=HOLDING_STOCK, currency=cur, ticker=ticker,
                quantity=qty, sort_order=i,
            ))
        else:
            amt = _dec(amounts[i] if i < len(amounts) else 0)
            label = (labels[i] if i < len(labels) else "").strip() or None
            if amt == 0 and label is None:
                continue
            holdings.append(Holding(
                kind=HOLDING_CASH, currency=cur, amount=amt,
                label=label, sort_order=i,
            ))
    return holdings


@assets_bp.route("/")
@login_required
@couple_required
def index():
    from sqlalchemy.orm import selectinload

    rate = fx.get_cached_rate()
    assets = sorted(
        Asset.query.filter_by(couple_id=current_user.couple_id)
        .options(selectinload(Asset.holdings), selectinload(Asset.category))
        .all(),
        key=lambda a: a.value_krw(rate),
        reverse=True,
    )
    overview = finance.overview_data(assets, rate)
    breakdown = finance.category_breakdown(assets, rate)
    cat_krw = {row["id"]: row["amount"] for row in breakdown}
    cat_share = {row["id"]: row["share"] for row in breakdown}
    asset_krw = {a.id: a.value_krw(rate) for a in assets}
    total = finance.total_assets(assets, rate)
    has_stocks = any(h.kind == "stock" for a in assets for h in a.holdings)
    return render_template(
        "assets/index.html",
        assets=assets,
        categories=_couple_categories(),
        overview=overview,
        cat_krw=cat_krw,
        cat_share=cat_share,
        asset_krw=asset_krw,
        total_assets=total,
        has_stocks=has_stocks,
        cached_rate=rate,
    )


@assets_bp.route("/new", methods=["GET", "POST"])
@login_required
@couple_required
def create():
    form = AssetForm()
    _populate_choices(form)

    if form.validate_on_submit():
        cat = _get_category(form.category.data)
        holdings = _parse_holdings()
        if not holdings:
            flash("최소 한 개의 보유 항목(현금 또는 주식)을 입력하세요.", "error")
            return render_template("assets/form.html", form=form, mode="new",
                                   holdings_json="[]")
        asset = Asset(
            couple_id=current_user.couple_id,
            owner_id=_resolve_owner_id(form),
            category_id=cat.id,
            name=form.name.data.strip(),
            institution=(form.institution.data or "").strip() or None,
            notes=(form.notes.data or "").strip() or None,
            exclude_from_stats=form.exclude_from_stats.data,
        )
        asset.holdings = holdings
        db.session.add(asset)
        # Price any stock holdings immediately so the value is populated.
        prices.refresh_holdings(holdings)
        log_activity(
            current_user.couple_id, current_user,
            f"{current_user.display_name}님이 '{asset.name}' 자산을 추가했습니다.",
            icon=cat.icon,
            detail=_won(asset.value_krw(fx.get_cached_rate())),
        )
        db.session.commit()
        _sync_snapshot()
        flash("자산이 추가되었습니다.", "success")
        return redirect(url_for("assets.index"))

    return render_template("assets/form.html", form=form, mode="new", holdings_json="[]")


@assets_bp.route("/<int:asset_id>/edit", methods=["GET", "POST"])
@login_required
@couple_required
def edit(asset_id: int):
    asset = _get_owned_asset(asset_id)
    form = AssetForm(obj=asset)
    _populate_choices(form)

    if form.validate_on_submit():
        cat = _get_category(form.category.data)
        holdings = _parse_holdings()
        if not holdings:
            flash("최소 한 개의 보유 항목(현금 또는 주식)을 입력하세요.", "error")
            return render_template("assets/form.html", form=form, mode="edit",
                                   asset=asset, holdings_json=_holdings_json(asset))
        rate = fx.get_cached_rate()
        old_value = asset.value_krw(rate)
        asset.name = form.name.data.strip()
        asset.category_id = cat.id
        asset.owner_id = _resolve_owner_id(form)
        asset.institution = (form.institution.data or "").strip() or None
        asset.notes = (form.notes.data or "").strip() or None
        asset.exclude_from_stats = form.exclude_from_stats.data
        # Replace holdings wholesale (orphan-cleanup deletes the old rows).
        asset.holdings = holdings
        prices.refresh_holdings(holdings)
        new_value = asset.value_krw(rate)
        detail = (
            f"{_won(old_value)} → {_won(new_value)}"
            if new_value != old_value else None
        )
        log_activity(
            current_user.couple_id, current_user,
            f"{current_user.display_name}님이 '{asset.name}' 자산을 수정했습니다.",
            icon="✏️",
            detail=detail,
        )
        db.session.commit()
        _sync_snapshot()
        flash("자산이 수정되었습니다.", "success")
        return redirect(url_for("assets.index"))

    if request.method == "GET":
        if asset.owner_id is None:
            form.owner.data = JOINT_OWNER_VALUE
        else:
            form.owner.data = str(asset.owner_id)
        form.category.data = asset.category_id
    return render_template("assets/form.html", form=form, mode="edit", asset=asset,
                           holdings_json=_holdings_json(asset))


@assets_bp.route("/<int:asset_id>/delete", methods=["POST"])
@login_required
@couple_required
def delete(asset_id: int):
    asset = _get_owned_asset(asset_id)
    name = asset.name
    old_value = asset.value_krw(fx.get_cached_rate())
    db.session.delete(asset)
    log_activity(
        current_user.couple_id, current_user,
        f"{current_user.display_name}님이 '{name}' 자산을 삭제했습니다.",
        icon="🗑️",
        detail=_won(old_value),
    )
    db.session.commit()
    _sync_snapshot()
    flash("자산이 삭제되었습니다.", "info")
    return redirect(url_for("assets.index"))


@assets_bp.route("/refresh-prices", methods=["POST"])
@login_required
@couple_required
def refresh_prices():
    """Fetch live stock prices for every stock holding in the household."""
    all_holdings = [h for a in current_user.couple.assets for h in a.holdings]
    updated = prices.refresh_holdings(all_holdings)
    db.session.commit()
    _sync_snapshot()
    if updated:
        flash(f"{updated}개 종목의 가격을 업데이트했습니다.", "success")
    else:
        flash("업데이트할 주식 종목이 없거나 시세를 불러오지 못했습니다.", "info")
    return redirect(url_for("assets.index"))


@assets_bp.route("/export.csv")
@login_required
@couple_required
def export_csv():
    """Download every account/holding as CSV (Excel-friendly, UTF-8 BOM)."""
    import csv
    import io
    from datetime import date

    from flask import Response
    from sqlalchemy.orm import selectinload

    rate = fx.get_cached_rate()
    assets = (
        Asset.query.filter_by(couple_id=current_user.couple_id)
        .options(selectinload(Asset.holdings), selectinload(Asset.category))
        .all()
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["계좌명", "카테고리", "소유자", "기관", "종류", "항목",
                "통화", "수량", "현재가", "원화 평가액", "통계 제외"])
    for a in sorted(assets, key=lambda x: x.category_name):
        for h in a.holdings:
            w.writerow([
                a.name, a.category_name, a.owner_label, a.institution or "",
                "주식" if h.is_stock else "현금", h.display_name, h.currency,
                float(h.quantity) if h.is_stock else "",
                float(h.cached_price) if (h.is_stock and h.cached_price) else "",
                round(float(h.value_krw(rate))),
                "Y" if a.exclude_from_stats else "",
            ])
    return Response(
        "﻿" + buf.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition":
                 f"attachment; filename=assets_{date.today().isoformat()}.csv"},
    )


def _holdings_json(asset: Asset) -> str:
    """Serialise an account's holdings for the edit form's JS editor."""
    import json

    rows = []
    for h in asset.holdings:
        rows.append({
            "kind": h.kind,
            "currency": h.currency,
            "label": h.label or "",
            "amount": float(h.amount or 0),
            "ticker": h.ticker or "",
            "qty": float(h.quantity or 0),
            "price": float(h.cached_price or 0),
        })
    return json.dumps(rows)
