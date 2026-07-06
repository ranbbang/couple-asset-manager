"""Application factory.

Creates and configures the Flask app, registers extensions, blueprints,
template helpers, and ensures the database schema exists.
"""
from flask import Flask

from .config import Config
from .constants import CURRENCIES, CURRENCY_SYMBOL
from .extensions import csrf, db, login_manager


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    if app.config.get("SECRET_KEY") == "dev-secret-change-me":
        app.logger.warning(
            "SECRET_KEY is the development default — set the SECRET_KEY "
            "environment variable before exposing this app on a network."
        )

    # --- extensions -------------------------------------------------------
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # --- blueprints -------------------------------------------------------
    from .auth.routes import auth_bp
    from .couple.routes import couple_bp
    from .main.routes import main_bp
    from .assets.routes import assets_bp
    from .goals.routes import goals_bp
    from .reports.routes import reports_bp
    from .categories.routes import categories_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(couple_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(assets_bp)
    app.register_blueprint(goals_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(categories_bp)

    # --- template helpers -------------------------------------------------
    register_template_helpers(app)

    # --- database ---------------------------------------------------------
    # Models must be imported before create_all so tables are registered.
    from . import models  # noqa: F401

    with app.app_context():
        db.create_all()

    return app


def register_template_helpers(app: Flask) -> None:
    """Jinja filters and globals shared across templates."""

    @app.template_filter("won")
    def won(value) -> str:
        """Format a number as Korean won, e.g. 1234567 -> '₩1,234,567'."""
        try:
            return f"₩{float(value):,.0f}"
        except (TypeError, ValueError):
            return "₩0"

    @app.template_filter("won_short")
    def won_short(value) -> str:
        """Compact Korean amount, e.g. 129925000 -> '1억 2,992만'.

        Shows down to the 만 (10k) unit only — the small sub-label under amounts.
        """
        try:
            n = int(round(float(value)))
        except (TypeError, ValueError):
            return ""
        sign = "−" if n < 0 else ""
        n = abs(n)
        eok, rem = divmod(n, 10**8)        # 억
        man = rem // 10**4                  # 만 (drop sub-10k)
        parts = []
        if eok:
            parts.append(f"{eok:,}억")
        if man:
            parts.append(f"{man:,}만")
        if not parts:
            # under 1만 — show the raw won so tiny values aren't blank
            return f"{sign}{n:,}원" if n else "0원"
        return sign + " ".join(parts)

    @app.template_filter("money")
    def money(value, currency: str = "KRW") -> str:
        """Format a native amount with its currency symbol.

        KRW shows no decimals; USD shows two (cents).
        """
        symbol = CURRENCY_SYMBOL.get(currency, "")
        try:
            if currency == "USD":
                return f"{symbol}{float(value):,.2f}"
            return f"{symbol}{float(value):,.0f}"
        except (TypeError, ValueError):
            return f"{symbol}0"

    @app.context_processor
    def inject_globals() -> dict:
        from flask_login import current_user

        couple_categories = []
        try:
            if current_user.is_authenticated and current_user.couple:
                couple_categories = current_user.couple.categories
        except Exception:
            couple_categories = []
        return {
            "CURRENCIES": CURRENCIES,
            "CURRENCY_SYMBOL": CURRENCY_SYMBOL,
            "couple_categories": couple_categories,
            "APP_NAME": "우리집 자산관리",
        }
