<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-12 | Updated: 2026-08-30 -->

# app

## Purpose
The Flask application package. Uses the application-factory pattern and organizes each
feature area as its own blueprint. Business logic lives in `services/`; presentation in
`templates/` + `static/`.

## Key Files
| File | Description |
|------|-------------|
| `__init__.py` | `create_app()` factory: registers extensions, blueprints, the `won`/`won_short`/`money` Jinja filters, and global template context; calls `db.create_all()` + additive micro-migrations + best-effort daily backup |
| `config.py` | Env-driven config (`SECRET_KEY`, `SQLALCHEMY_DATABASE_URI`, `DEFAULT_USD_KRW`) with dev defaults; loads `.env` from the project root |
| `extensions.py` | Unbound singletons: `db` (SQLAlchemy), `login_manager`, `csrf` |
| `constants.py` | `DEFAULT_CATEGORIES` — the 8 categories a new household is seeded with (7 asset + 1 liability, `빚`); currencies (KRW/USD); the 4 fixed `REPORT_GROUPS` categories roll up into for trend charts. Categories themselves are a fully user-editable DB table (see `models.Category`), not a fixed set — these are only the seed defaults. |
| `models.py` | `Couple`, `User`, `Category` (per-household, editable: icon/color/liability/report_group/is_real_estate/is_liquid), `Asset` (an account; holds one or more `Holding`s, no currency of its own), `Holding` (cash in a currency, or a stock: ticker+quantity+cached_price), `Goal`, `ActivityLog`, `AssetSnapshot` (monthly point-in-time totals) + Flask-Login `user_loader` |
| `decorators.py` | `@couple_required` — redirects solo users to household setup |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `auth/` | Sign up / login / logout / account settings (email, display name, password) (blueprint + forms) |
| `couple/` | Create / join / invite a household, household settings (blueprint + forms) |
| `main/` | Landing redirect, dashboard, activity feed, `/api/fx-rate` (blueprint) |
| `categories/` | Per-household category CRUD: add/edit/delete (with asset reassignment)/reorder (blueprint + form) |
| `assets/` | Asset (account) CRUD, holdings parsed from dynamic form rows, price refresh, CSV export (blueprint + form) |
| `goals/` | Shared/personal goal CRUD, category/asset linking (blueprint + form) |
| `reports/` | Asset Reports: historical trends, target allocation, CSV export (blueprint) |
| `services/` | `finance.py` (currency-aware aggregation math — pure functions over an `Asset` iterable), `fx.py` (USD→KRW rate, cached), `prices.py` (stock quotes, cached), `snapshots.py` (monthly history + report aggregation), `categories.py` (seed/reorder/safe-delete), `goals.py` (goal progress math), `activity.py` (log helper), `backup.py` (sqlite file backup) |
| `templates/` | Jinja2 views: `base.html` → `shell.html` → pages; `_formhelpers.html` macro |
| `static/` | `css/styles.css` design system, `js/main.js` / `assets.js` / `reports.js` |

## For AI Agents

### Working In This Directory
- Add a feature = add a blueprint folder (`routes.py` + optional `forms.py`) and register it in `__init__.py`.
- Extensions are created unbound in `extensions.py` and `.init_app(app)`-ed in the factory — never import a live app at module top level.
- Models must be imported before `db.create_all()`; the factory already does this.
- Schema changes: `db.create_all()` never ALTERs existing tables. Additive column changes go in `_apply_micro_migrations()` in `__init__.py` (see its existing entries for the pattern); back up `app.db` first via `services.backup.backup_database()`.

### Testing Requirements
- A real `pytest` suite exists under `../tests/` (run from the project root: `pytest`, or `.venv/Scripts/python.exe -m pytest`; `requirements-dev.txt` adds `pytest` on top of `requirements.txt`). `tests/conftest.py` has the shared fixtures — read its module docstring before adding new ones, it documents two non-obvious traps already hit once each:
  - The test DB is a `tmp_path`-backed **file**, not `sqlite:///:memory:` — an in-memory DB isn't visible across the separate connection a live test-client request opens, so fixture data set up before a request silently isn't there.
  - `current_app.instance_path` (where `fx.py`/`prices.py` cache JSON files) is reassigned to a `tmp_path` subdirectory in the `app` fixture. Skipping this makes a test read/overwrite the *real* project's `instance/fx_cache.json` / `instance/price_cache.json`.
  - Test user emails must use a real, resolvable domain (`@example.com`, per RFC 2606) — `.local`/`.test`/`.invalid` are rejected by `email_validator` as reserved names, which fails WTForms' `Email()` validator on login/signup/account forms even though nothing does a network deliverability check.
- `services/finance.py` and `services/goals.py` functions take a plain iterable (`Asset` rows / a pre-loaded assets list) and return `Decimal`/dicts — unit-test them directly without a request context or the ORM relationships.
- For a route test, use the Flask test client with `app.config["WTF_CSRF_ENABLED"] = False`, and assert login actually succeeded (e.g. check for "로그아웃" in the response) rather than just a 200 status — a silently-failed login still returns 200 on the login page.

### Common Patterns
- Household scoping: `@login_required` + `@couple_required`; lookups verify `couple_id` and 404 otherwise.
- Activity logging via `services.activity.log_activity(...)`; caller commits.
- Owner select uses the `"joint"` sentinel (NULL `owner_id`) for jointly-owned assets/goals.
- **Currency**: an `Asset` has no currency of its own — each `Holding` stores its own native `amount`/`currency` (or `quantity`+`cached_price` for a stock) and `Holding.value_krw(rate)` / `Asset.value_krw(rate)` convert to the KRW base. Server-side rendering uses `fx.get_cached_rate()` (no network); the `/api/fx-rate` endpoint does the live fetch for client toggles.
- **N+1 caution**: iterating `couple.assets` (or `couple.categories`) lazy-loads, then each asset's `.holdings`/`.category` lazy-loads again per-object the first time it's touched in that request. Every route that needs a full asset list eager-loads explicitly instead: `Asset.query.filter_by(couple_id=...).options(selectinload(Asset.holdings), selectinload(Asset.category))`. Follow this pattern for any new route/service that needs more than one asset.
- **Snapshots**: mutating assets calls `snapshots.refresh_current_month(...)` (also runs on every `/reports` page load to keep the current month fresh); reports read `snapshots.report_data(...)`. Values are KRW; the frontend converts to USD.
- **Charts** are client-side (Chart.js via CDN, with a graceful "couldn't load" fallback if it's blocked/offline). Pages embed a JSON payload (`overview | tojson`, `report | tojson`) consumed by `static/js/assets.js` and `reports.js`.
- **WTForms gotcha**: a field with `Optional()` and a form-level `validate_<fieldname>` method — that custom validator is silently skipped whenever the field is empty, because `Optional()` raises `StopValidation` and cuts the rest of that field's validator chain, including the extra `validate_<name>` method. If a field needs both "empty is fine sometimes" and "but validate something about it always," don't use `Optional()`/`DataRequired()` on the field — put the whole rule in the custom validator instead (see `categories/forms.py::CategoryForm.report_group` for the fixed pattern and the comment explaining it).

## Dependencies

### Internal
- `constants` ← used by `models`, `services.finance`, `assets`; `services` ← used by route blueprints.

### External
- Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF / WTForms, Werkzeug.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
