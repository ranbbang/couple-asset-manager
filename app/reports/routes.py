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


@reports_bp.route("/export.csv")
@login_required
@couple_required
def export_csv():
    """Download the monthly snapshot history as CSV (Excel-friendly, UTF-8 BOM)."""
    import csv
    import io
    import json
    from datetime import date

    from flask import Response

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["월", "순자산", "총 자산", "총 부채", "부동산",
                "부동산 제외 순자산", "적용 환율(USD/KRW)", "카테고리별 상세"])
    for s in snapshots.history(current_user.couple):
        cats = json.loads(s.category_totals or "{}")
        cat_str = "; ".join(f"{k}={round(v):,}" for k, v in cats.items())
        w.writerow([
            s.taken_on.strftime("%Y-%m"),
            round(float(s.net_worth_krw)),
            round(float(s.total_assets_krw)),
            round(float(s.total_liabilities_krw)),
            round(float(s.real_estate_krw or 0)),
            round(float(s.net_worth_excl_re_krw or 0)),
            float(s.rate_used or 0),
            cat_str,
        ])
    return Response(
        "﻿" + buf.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition":
                 f"attachment; filename=snapshots_{date.today().isoformat()}.csv"},
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
