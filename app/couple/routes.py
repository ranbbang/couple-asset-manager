"""Household (couple) routes: setup, create, join, and invite view."""
import secrets
import string

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Couple
from ..services.activity import log_activity
from ..services.categories import create_default_categories
from .forms import CreateCoupleForm, JoinCoupleForm

couple_bp = Blueprint("couple", __name__, url_prefix="/couple")

# Unambiguous alphabet (no 0/O/1/I) for human-friendly invite codes.
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_invite_code(length: int = 8) -> str:
    """Return a unique, readable invite code not already used by a couple."""
    while True:
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))
        if not Couple.query.filter_by(invite_code=code).first():
            return code


@couple_bp.route("/setup")
@login_required
def setup():
    """Landing page for users who have not joined a household yet."""
    if current_user.has_couple:
        return redirect(url_for("main.dashboard"))
    return render_template(
        "couple/setup.html",
        create_form=CreateCoupleForm(),
        join_form=JoinCoupleForm(),
    )


@couple_bp.route("/create", methods=["POST"])
@login_required
def create():
    if current_user.has_couple:
        return redirect(url_for("main.dashboard"))

    form = CreateCoupleForm()
    if form.validate_on_submit():
        couple = Couple(
            name=(form.name.data or "").strip() or "우리집",
            invite_code=generate_invite_code(),
        )
        db.session.add(couple)
        db.session.flush()  # assign couple.id

        create_default_categories(couple)
        current_user.couple_id = couple.id
        log_activity(
            couple.id,
            current_user,
            f"{current_user.display_name}님이 '{couple.name}' 가구를 만들었습니다.",
            icon="🏡",
        )
        db.session.commit()
        flash("가구가 만들어졌어요. 파트너를 초대해 보세요!", "success")
        return redirect(url_for("couple.invite"))

    flash("가구 이름을 확인해 주세요.", "error")
    return redirect(url_for("couple.setup"))


@couple_bp.route("/join", methods=["POST"])
@login_required
def join():
    if current_user.has_couple:
        return redirect(url_for("main.dashboard"))

    form = JoinCoupleForm()
    if not form.validate_on_submit():
        flash("초대 코드를 입력해 주세요.", "error")
        return redirect(url_for("couple.setup"))

    code = form.invite_code.data.strip().upper()
    couple = Couple.query.filter_by(invite_code=code).first()
    if couple is None:
        flash("초대 코드를 찾을 수 없습니다.", "error")
        return redirect(url_for("couple.setup"))
    if couple.is_full:
        flash("이미 두 명이 연결된 가구입니다.", "error")
        return redirect(url_for("couple.setup"))

    current_user.couple_id = couple.id
    log_activity(
        couple.id,
        current_user,
        f"{current_user.display_name}님이 가구에 합류했습니다. 💕",
        icon="💕",
    )
    db.session.commit()
    flash("파트너와 연결되었어요!", "success")
    return redirect(url_for("main.dashboard"))


@couple_bp.route("/settings", methods=["POST"])
@login_required
def settings():
    """Update lightweight household settings (currently: monthly expense)."""
    if not current_user.has_couple:
        return redirect(url_for("couple.setup"))
    raw = (request.form.get("monthly_expense") or "").replace(",", "").strip()
    couple = current_user.couple
    if raw == "":
        couple.monthly_expense_krw = None
    else:
        try:
            value = int(raw)
            if value < 0:
                raise ValueError
        except ValueError:
            flash("월 생활비는 0 이상의 숫자로 입력해 주세요.", "error")
            return redirect(url_for("couple.invite"))
        couple.monthly_expense_krw = value
    db.session.commit()
    flash("가구 설정이 저장되었습니다.", "success")
    return redirect(url_for("couple.invite"))


@couple_bp.route("/invite")
@login_required
def invite():
    """Show the shareable invite code (acts as the 'invite by shared key')."""
    if not current_user.has_couple:
        return redirect(url_for("couple.setup"))
    couple = current_user.couple
    partner = couple.partner_of(current_user)
    return render_template("couple/invite.html", couple=couple, partner=partner)
