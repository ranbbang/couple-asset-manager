"""Application configuration.

Values are read from environment variables (optionally via a local .env file),
falling back to sensible development defaults.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env if present (absolute path so it also works when launched from a
# scheduled task whose working directory isn't the project root).
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # Default to a SQLite file in the project root.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Keep sessions reasonable for a shared household device.
    REMEMBER_COOKIE_DURATION = 60 * 60 * 24 * 14  # 14 days (seconds)

    # Fallback USD->KRW rate used when the live FX API is unreachable (offline).
    DEFAULT_USD_KRW = float(os.environ.get("DEFAULT_USD_KRW", "1350"))
