"""Flask extension singletons.

Instantiated here (unbound) and initialised against the app inside the
application factory (app/__init__.py). This avoids circular imports.
"""
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

db = SQLAlchemy()

# Registers the `csrf_token()` Jinja global app-wide and enforces CSRF on all
# POST requests (including the raw <form> delete buttons).
csrf = CSRFProtect()

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "로그인이 필요합니다."
login_manager.login_message_category = "warning"
