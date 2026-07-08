"""Main routes: home redirect, dashboard, and activity feed."""
from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

from ..decorators import couple_required
from ..models import ActivityLog, Goal
from ..services import fx, goals as goals_svc, snapshots
from ..services.finance import dashboard_summary

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    if not current_user.has_couple:
        return redirect(url_for("couple.setup"))
    return redirect(url_for("main.dashboard"))


@main_bp.route("/dashboard")
@login_required
@couple_required
def dashboard():
    from sqlalchemy.orm import selectinload

    from ..models import Asset

    couple = current_user.couple
    assets = (
        Asset.query.filter_by(couple_id=couple.id)
        .options(selectinload(Asset.holdings), selectinload(Asset.category))
        .all()
    )
    rate = fx.get_cached_rate()
    summary = dashboard_summary(assets, rate)
    mom = snapshots.month_over_month(couple, summary["net_worth"])
    flow = snapshots.flow_split(couple, assets, rate)
    monthly_gain = snapshots.avg_monthly_gain(couple)

    # "생활비 N개월치" — only when the household set its monthly expense.
    liquid_months = None
    expense = couple.monthly_expense_krw
    if expense and expense > 0:
        liquid_months = round(float(summary["liquid"] / expense), 1)
    goals = (
        Goal.query.filter_by(couple_id=couple.id)
        .order_by(Goal.created_at.asc())
        .all()
    )
    goal_views = {
        g.id: goals_svc.goal_view(g, couple, rate, monthly_gain) for g in goals
    }
    recent = (
        ActivityLog.query.filter_by(couple_id=couple.id)
        .order_by(ActivityLog.created_at.desc())
        .limit(3)
        .all()
    )

    # Net-worth sparkline (last 12 monthly snapshots) as SVG polyline points.
    spark_points = _spark_points(
        [float(s.net_worth_krw) for s in snapshots.history(couple)][-12:]
    )
    # Donut segments for the category composition chart (non-liability only).
    donut_css = _donut_stops(summary["breakdown"])
    partner = couple.partner_of(current_user)
    return render_template(
        "dashboard.html",
        couple=couple,
        partner=partner,
        summary=summary,
        goals=goals,
        goal_views=goal_views,
        recent=recent,
        asset_count=len(assets),
        mom=mom,
        flow=flow,
        liquid_months=liquid_months,
        spark_points=spark_points,
        donut_css=donut_css,
    )


def _spark_points(values, width: int = 220, height: int = 56) -> str | None:
    """Normalise a value series into SVG polyline points (needs >= 2 points)."""
    if len(values) < 2:
        return None
    lo, hi = min(values), max(values)
    rng = (hi - lo) or 1.0
    step = width / (len(values) - 1)
    pad = 4  # keep the line inside the viewBox
    return " ".join(
        f"{i * step:.1f},{height - pad - (v - lo) / rng * (height - pad * 2):.1f}"
        for i, v in enumerate(values)
    )


def _donut_stops(breakdown) -> str | None:
    """conic-gradient stops for the asset-composition donut."""
    stops, start = [], 0.0
    for row in breakdown:
        if row["is_liability"] or not row["share"]:
            continue
        end = min(start + row["share"], 100.0)
        stops.append(f"{row['color']} {start:.1f}% {end:.1f}%")
        start = end
    if not stops:
        return None
    if start < 100:
        stops.append(f"var(--surface-2) {start:.1f}% 100%")
    return ", ".join(stops)


@main_bp.route("/api/fx-rate")
@login_required
def fx_rate():
    """Live USD->KRW rate for the currency toggle (cached server-side)."""
    rate, source = fx.fetch_live_rate()
    return {"base": "USD", "quote": "KRW", "rate": rate, "source": source}


@main_bp.route("/activity")
@login_required
@couple_required
def activity():
    couple = current_user.couple
    entries = (
        ActivityLog.query.filter_by(couple_id=couple.id)
        .order_by(ActivityLog.created_at.desc())
        .limit(100)
        .all()
    )
    return render_template("activity.html", entries=entries)
