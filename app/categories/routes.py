"""Category management routes (per household): list, add, edit, delete, reorder."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..decorators import couple_required
from ..extensions import db
from ..models import Category
from ..services import categories as svc
from ..services.activity import log_activity
from .forms import NO_GROUP, CategoryForm

categories_bp = Blueprint("categories", __name__, url_prefix="/categories")


def _get_owned(category_id: int) -> Category:
    cat = db.session.get(Category, category_id)
    if cat is None or cat.couple_id != current_user.couple_id:
        abort(404)
    return cat


def _apply(form: CategoryForm, cat: Category) -> None:
    cat.name = form.name.data.strip()
    cat.icon = (form.icon.data or "").strip() or "•"
    cat.color = (form.color.data or "#9DBE8A").strip()
    cat.is_liability = form.is_liability.data
    # Liabilities have no report group; assets always do (form-validated).
    cat.report_group = None if form.is_liability.data else (form.report_group.data or None)
    # Liabilities can't be real estate or liquid assets.
    cat.is_real_estate = bool(form.is_real_estate.data) and not form.is_liability.data
    cat.is_liquid = bool(form.is_liquid.data) and not form.is_liability.data


@categories_bp.route("/")
@login_required
@couple_required
def index():
    cats = svc.ordered(current_user.couple)
    return render_template("categories/index.html", categories=cats)


@categories_bp.route("/new", methods=["GET", "POST"])
@login_required
@couple_required
def create():
    form = CategoryForm()
    if form.validate_on_submit():
        if _name_taken(form.name.data.strip()):
            flash("같은 이름의 카테고리가 이미 있습니다.", "error")
            return render_template("categories/form.html", form=form, mode="new")
        cat = Category(couple_id=current_user.couple_id,
                       sort_order=svc.next_sort_order(current_user.couple))
        _apply(form, cat)
        db.session.add(cat)
        log_activity(current_user.couple_id, current_user,
                     f"{current_user.display_name}님이 '{cat.name}' 카테고리를 추가했습니다.", icon="🏷️")
        db.session.commit()
        flash("카테고리가 추가되었습니다.", "success")
        return redirect(url_for("categories.index"))
    return render_template("categories/form.html", form=form, mode="new")


@categories_bp.route("/<int:category_id>/edit", methods=["GET", "POST"])
@login_required
@couple_required
def edit(category_id: int):
    cat = _get_owned(category_id)
    form = CategoryForm(obj=cat)
    if form.validate_on_submit():
        if _name_taken(form.name.data.strip(), exclude_id=cat.id):
            flash("같은 이름의 카테고리가 이미 있습니다.", "error")
            return render_template("categories/form.html", form=form, mode="edit", category=cat)
        _apply(form, cat)
        log_activity(current_user.couple_id, current_user,
                     f"{current_user.display_name}님이 '{cat.name}' 카테고리를 수정했습니다.", icon="✏️")
        db.session.commit()
        flash("카테고리가 수정되었습니다.", "success")
        return redirect(url_for("categories.index"))
    # Preselect report group (or NO_GROUP for liabilities) on GET.
    if request.method == "GET":
        form.report_group.data = cat.report_group or NO_GROUP
    return render_template("categories/form.html", form=form, mode="edit", category=cat)


@categories_bp.route("/<int:category_id>/delete", methods=["POST"])
@login_required
@couple_required
def delete(category_id: int):
    cat = _get_owned(category_id)
    if len(svc.ordered(current_user.couple)) <= 1:
        flash("카테고리는 최소 1개 이상 있어야 합니다.", "error")
        return redirect(url_for("categories.index"))

    target = None
    target_id = request.form.get("reassign_to", type=int)
    if target_id:
        target = _get_owned(target_id)

    name = cat.name
    if not svc.reassign_and_delete(cat, target):
        flash(f"'{name}'에 자산이 있어 삭제할 수 없습니다. 옮길 카테고리를 선택하세요.", "error")
        return redirect(url_for("categories.index"))

    log_activity(current_user.couple_id, current_user,
                 f"{current_user.display_name}님이 '{name}' 카테고리를 삭제했습니다.", icon="🗑️")
    db.session.commit()
    flash("카테고리가 삭제되었습니다.", "info")
    return redirect(url_for("categories.index"))


@categories_bp.route("/<int:category_id>/move", methods=["POST"])
@login_required
@couple_required
def move(category_id: int):
    cat = _get_owned(category_id)
    direction = request.form.get("dir", "up")
    svc.move(cat, "up" if direction == "up" else "down")
    db.session.commit()
    return redirect(url_for("categories.index"))


def _name_taken(name: str, exclude_id: int | None = None) -> bool:
    q = Category.query.filter_by(couple_id=current_user.couple_id, name=name)
    if exclude_id:
        q = q.filter(Category.id != exclude_id)
    return q.first() is not None
