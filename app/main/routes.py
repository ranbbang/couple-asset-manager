"""Main routes: home redirect, dashboard, and activity feed."""
from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

from ..decorators import couple_required
from ..models import ActivityLog, Goal
from ..services import fx, goals as goals_svc
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
    couple = current_user.couple
    assets = couple.assets
    rate = fx.get_cached_rate()
    summary = dashboard_summary(assets, rate)
    goals = (
        Goal.query.filter_by(couple_id=couple.id)
        .order_by(Goal.created_at.asc())
        .all()
    )
    goal_views = {g.id: goals_svc.goal_view(g, couple, rate) for g in goals}
    recent = (
        ActivityLog.query.filter_by(couple_id=couple.id)
        .order_by(ActivityLog.created_at.desc())
        .limit(6)
        .all()
    )
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
    )


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
