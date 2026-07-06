"""Shared goal CRUD routes, scoped to the current user's household."""
import json

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from ..decorators import couple_required
from ..extensions import db
from ..models import Goal
from ..services import categories as categories_svc
from ..services import fx, goals as goals_svc, snapshots
from ..services.activity import log_activity
from ..services.finance import _is_liability
from .forms import GoalForm

goals_bp = Blueprint("goals", __name__, url_prefix="/goals")


def _get_owned_goal(goal_id: int) -> Goal:
    goal = db.session.get(Goal, goal_id)
    if goal is None or goal.couple_id != current_user.couple_id:
        abort(404)
    return goal


def _populate_links(form: GoalForm) -> None:
    """Category + asset choices a goal can link to (non-liability only)."""
    cats = [c for c in categories_svc.ordered(current_user.couple) if not c.is_liability]
    form.linked_categories.choices = [
        (c.id, f"{c.icon}  {c.name}") for c in cats
    ]
    assets = [a for a in current_user.couple.assets if not _is_liability(a)]
    assets.sort(key=lambda a: a.name)
    form.linked_assets.choices = [
        (a.id, f"{a.category.icon if a.category else '•'}  {a.name}") for a in assets
    ]


def _goal_views(goals):
    rate = fx.get_cached_rate()
    monthly_gain = snapshots.avg_monthly_gain(current_user.couple)
    return {
        g.id: goals_svc.goal_view(g, current_user.couple, rate, monthly_gain)
        for g in goals
    }


@goals_bp.route("/")
@login_required
@couple_required
def index():
    goals = (
        Goal.query.filter_by(couple_id=current_user.couple_id)
        .order_by(Goal.created_at.asc())
        .all()
    )
    return render_template("goals/index.html", goals=goals, views=_goal_views(goals))


@goals_bp.route("/new", methods=["GET", "POST"])
@login_required
@couple_required
def create():
    form = GoalForm()
    _populate_links(form)
    if form.validate_on_submit():
        goal = Goal(couple_id=current_user.couple_id)
        _apply(form, goal)
        db.session.add(goal)
        log_activity(
            current_user.couple_id, current_user,
            f"{current_user.display_name}님이 '{goal.name}' 목표를 만들었습니다.",
            icon="🎯",
        )
        db.session.commit()
        flash("목표가 추가되었습니다.", "success")
        return redirect(url_for("goals.index"))
    return render_template("goals/form.html", form=form, mode="new")


@goals_bp.route("/<int:goal_id>/edit", methods=["GET", "POST"])
@login_required
@couple_required
def edit(goal_id: int):
    goal = _get_owned_goal(goal_id)
    form = GoalForm(obj=goal)
    _populate_links(form)
    if form.validate_on_submit():
        _apply(form, goal)
        log_activity(
            current_user.couple_id, current_user,
            f"{current_user.display_name}님이 '{goal.name}' 목표를 업데이트했습니다.",
            icon="📈",
        )
        db.session.commit()
        flash("목표가 수정되었습니다.", "success")
        return redirect(url_for("goals.index"))
    # Preselect linked ids on GET.
    form.linked_categories.data = goal.category_id_list
    form.linked_assets.data = goal.asset_id_list
    return render_template("goals/form.html", form=form, mode="edit", goal=goal)


@goals_bp.route("/<int:goal_id>/delete", methods=["POST"])
@login_required
@couple_required
def delete(goal_id: int):
    goal = _get_owned_goal(goal_id)
    name = goal.name
    db.session.delete(goal)
    log_activity(
        current_user.couple_id, current_user,
        f"{current_user.display_name}님이 '{name}' 목표를 삭제했습니다.",
        icon="🗑️",
    )
    db.session.commit()
    flash("목표가 삭제되었습니다.", "info")
    return redirect(url_for("goals.index"))


def _apply(form: GoalForm, goal: Goal) -> None:
    goal.name = form.name.data.strip()
    goal.target_amount = form.target_amount.data
    goal.saved_amount = form.saved_amount.data or 0
    goal.stocks_amount = form.stocks_amount.data or 0
    goal.linked_category_ids = json.dumps(form.linked_categories.data or [])
    goal.linked_asset_ids = json.dumps(form.linked_assets.data or [])
