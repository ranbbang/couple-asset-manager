"""Helper for appending to the household activity feed.

Centralising this keeps route handlers tidy and guarantees every log entry is
attributed to an actor and a couple.
"""
from ..extensions import db
from ..models import ActivityLog


def log_activity(couple_id: int, user, action: str, icon: str = "•") -> None:
    """Record an activity entry. Caller is responsible for committing.

    Args:
        couple_id: household the activity belongs to.
        user:      the acting User (or None for system events).
        action:    human-readable sentence, e.g. "지은님이 자산을 추가했습니다".
        icon:      short emoji shown beside the entry.
    """
    entry = ActivityLog(
        couple_id=couple_id,
        user_id=user.id if user else None,
        action=action,
        icon=icon,
    )
    db.session.add(entry)
