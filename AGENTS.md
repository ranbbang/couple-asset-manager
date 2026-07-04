<!-- Generated: 2026-06-12 | Updated: 2026-06-12 -->

# 우리집 자산관리 (Couples Asset Management)

## Purpose
A couples-focused personal finance web app inspired by "Monarch for Couples". Two partners
share one household, one dashboard, and shared goals. Every asset belongs to exactly one of
eight categories; net worth = Σ(assets) − Σ(빚 liabilities). Built with Flask + SQLAlchemy +
SQLite and server-rendered Jinja2 templates. No external/paid APIs — all data is entered
manually and stored locally.

## Key Files
| File | Description |
|------|-------------|
| `run.py` | Dev entry point — `python run.py` serves on http://127.0.0.1:5000 |
| `seed.py` | Loads a demo couple, assets, goals, and activity (drops & recreates tables) |
| `requirements.txt` | Pinned dependencies (Flask, SQLAlchemy, Flask-Login, Flask-WTF) |
| `.env.example` | Template for `SECRET_KEY` / `DATABASE_URL` (copy to `.env`) |
| `README.md` | Setup, architecture, schema, and demo logins |
| `app.db` | SQLite database (git-ignored; created on first run / seed) |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `app/` | The Flask application package (see `app/AGENTS.md`) |
| `.venv/` | Local virtual environment (git-ignored, not application code) |
| `.idea/` `.claude/` `.omc/` | IDE / tooling state (not application code) |

## For AI Agents

### Working In This Directory
- Activate the venv first: `.venv\Scripts\activate` (Windows). Dependencies are pinned in `requirements.txt`.
- The app uses the **application-factory** pattern: `app.create_app()` builds and configures the app. Tables are auto-created on startup via `db.create_all()`.
- After changing models, the simplest reset is `python seed.py` (it drops & recreates all tables). There is no migration tool wired up yet — add Flask-Migrate if schema evolution matters.
- Keep business logic in `app/services/` and route handlers thin.

### Testing Requirements
- No persistent test suite is committed. Validate changes with Flask's test client against `create_app()` (set `app.config["WTF_CSRF_ENABLED"] = False` for POST tests).
- Smoke-check the boot path: `python run.py` then load `/login`.
- The finance math in `app/services/finance.py` is pure and the prime target for unit tests.

### Common Patterns
- One blueprint per feature area, each bundling `routes.py` (+ `forms.py`).
- `@login_required` then `@couple_required` guards on household-scoped views.
- Every asset/goal lookup verifies `couple_id` and 404s otherwise (tenant isolation).
- `₩` currency rendering via the `won` Jinja filter; KRW integers (no decimals shown).

## Dependencies

### Internal
- None outside this repo.

### External
- Flask 3 · Flask-SQLAlchemy · Flask-Login · Flask-WTF / WTForms · Werkzeug · python-dotenv
- SQLite (stdlib). Pretendard webfont loaded via CDN for typography only.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
