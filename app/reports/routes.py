"""Asset Reports routes: net-worth and category trends over time."""
from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from ..decorators import couple_required
from ..services import fx, snapshots
from ..services.activity import log_activity
from ..extensions import db

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.route("/")
@login_required
@couple_required
def index():
    couple = current_user.couple
    # Keep the current month in sync so the latest point reflects today's data.
    snapshots.refresh_current_month(couple, fx.get_cached_rate())
    data = snapshots.report_data(couple)
    return render_template(
        "reports/index.html",
        report=data,
        cached_rate=fx.get_cached_rate(),
    )


@reports_bp.route("/snapshot", methods=["POST"])
@login_required
@couple_required
def record_snapshot():
    """Manually capture this month's snapshot at the live exchange rate."""
    couple = current_user.couple
    rate, _ = fx.fetch_live_rate()
    snapshots.capture_snapshot(couple, rate)
    log_activity(
        couple.id,
        current_user,
        f"{current_user.display_name}님이 자산 스냅샷을 기록했습니다.",
        icon="📸",
    )
    db.session.commit()
    flash("이번 달 자산 스냅샷이 기록되었습니다.", "success")
    return redirect(url_for("reports.index"))
