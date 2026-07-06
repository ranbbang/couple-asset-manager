"""Category helpers: seed defaults for a new household, ordering, reordering,
and safe deletion (reassigning any assets first).
"""
from ..constants import DEFAULT_CATEGORIES
from ..extensions import db
from ..models import Category


def create_default_categories(couple) -> list[Category]:
    """Seed the standard starter categories for a newly created household."""
    created = []
    for spec in DEFAULT_CATEGORIES:
        cat = Category(
            couple_id=couple.id,
            name=spec["name"],
            icon=spec["icon"],
            color=spec["color"],
            is_liability=spec["is_liability"],
            report_group=spec["report_group"],
            is_real_estate=spec.get("is_real_estate", False),
            is_liquid=spec.get("is_liquid", False),
            sort_order=spec["sort_order"],
        )
        db.session.add(cat)
        created.append(cat)
    return created


def ordered(couple) -> list[Category]:
    """Categories for a couple in display order."""
    return (
        Category.query.filter_by(couple_id=couple.id)
        .order_by(Category.sort_order.asc(), Category.id.asc())
        .all()
    )


def next_sort_order(couple) -> int:
    cats = ordered(couple)
    return (cats[-1].sort_order + 1) if cats else 0


def move(category: Category, direction: str) -> None:
    """Swap a category's order with its neighbour (direction 'up'|'down')."""
    cats = ordered(category.couple)
    idx = next((i for i, c in enumerate(cats) if c.id == category.id), None)
    if idx is None:
        return
    swap = idx - 1 if direction == "up" else idx + 1
    if swap < 0 or swap >= len(cats):
        return
    other = cats[swap]
    category.sort_order, other.sort_order = other.sort_order, category.sort_order


def reassign_and_delete(category: Category, target: Category | None) -> bool:
    """Delete a category. If it has assets, move them to `target` first.

    Returns True on success, False if assets exist but no valid target given.
    Reassignment is done at the ORM level so the moved assets are detached from
    the category before it is deleted (otherwise the delete would null their FK).
    """
    if category.assets:
        if target is None or target.id == category.id:
            return False
        for asset in list(category.assets):
            asset.category = target
    db.session.delete(category)
    return True
