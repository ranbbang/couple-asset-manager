"""Shared route decorators."""
from functools import wraps

from flask import redirect, url_for
from flask_login import current_user


def couple_required(view):
    """Ensure the user has joined a household before accessing a view.

    Assumes the view is already wrapped with @login_required (so the user is
    authenticated). Redirects solo users to the household setup page.
    """

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.has_couple:
            return redirect(url_for("couple.setup"))
        return view(*args, **kwargs)

    return wrapped
