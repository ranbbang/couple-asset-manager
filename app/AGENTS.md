<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-12 | Updated: 2026-06-12 -->

# app

## Purpose
The Flask application package. Uses the application-factory pattern and organizes each
feature area as its own blueprint. Business logic lives in `services/`; presentation in
`templates/` + `static/`.

## Key Files
| File | Description |
|------|-------------|
| `__init__.py` | `create_app()` factory: registers extensions, blueprints, the `won` Jinja filter, and global template context; calls `db.create_all()` |
| `config.py` | Env-driven config (`SECRET_KEY`, `SQLALCHEMY_DATABASE_URI`) with dev defaults |
| `extensions.py` | Unbound singletons: `db` (SQLAlchemy), `login_manager`, `csrf` |
| `constants.py` | The 7 categories (6 assets + `Debt (빚)`), liability set, currencies (KRW/USD), per-category UI metadata, and report groupings |
| `models.py` | `Couple`, `User`, `Asset` (incl. `currency`), `Goal`, `ActivityLog`, `AssetSnapshot` + Flask-Login `user_loader` |
| `decorators.py` | `@couple_required` — redirects solo users to household setup |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `auth/` | Sign up / login / logout (blueprint + forms) |
| `couple/` | Create / join / invite a household (blueprint + forms) |
| `main/` | Landing redirect, dashboard, activity feed (blueprint) |
| `assets/` | Asset CRUD incl. currency + overview data (blueprint + form) |
| `goals/` | Shared goal CRUD (blueprint + form) |
| `reports/` | Asset Reports: historical trends + allocation charts (blueprint) |
| `services/` | `finance.py` (currency-aware math), `fx.py` (USD→KRW rate), `snapshots.py` (history + report aggregation), `activity.py` (log helper) |
| `templates/` | Jinja2 views: `base.html` → `shell.html` → pages; `_formhelpers.html` macro |
| `static/` | `css/styles.css` design system, `js/main.js` light enhancement |

## For AI Agents

### Working In This Directory
- Add a feature = add a blueprint folder (`routes.py` + optional `forms.py`) and register it in `__init__.py`.
- Extensions are created unbound in `extensions.py` and `.init_app(app)`-ed in the factory — never import a live app at module top level.
- Models must be imported before `db.create_all()`; the factory already does this.

### Testing Requirements
- Instantiate with `create_app()`; set `app.config["WTF_CSRF_ENABLED"] = False` for POST tests via the test client.
- `services/finance.py` functions take an iterable of `Asset` rows and return `Decimal`/dicts — unit-test them directly without a request context.

### Common Patterns
- Household scoping: `@login_required` + `@couple_required`; lookups verify `couple_id` and 404 otherwise.
- Activity logging via `services.activity.log_activity(...)`; caller commits.
- Owner select uses the `"joint"` sentinel (NULL `owner_id`) for jointly-owned assets.
- **Currency**: balances stored native; `finance.to_krw(amount, currency, rate)` converts to the KRW base. Server-side rendering uses `fx.get_cached_rate()` (no network); the `/api/fx-rate` endpoint does the live fetch for client toggles.
- **Snapshots**: mutating assets calls `snapshots.refresh_current_month(...)`; reports read `snapshots.report_data(...)`. Values are KRW; the frontend converts to USD.
- **Charts** are client-side (Chart.js via CDN). Pages embed a JSON payload (`overview | tojson`, `report | tojson`) consumed by `static/js/assets.js` and `reports.js`.

## Dependencies

### Internal
- `constants` ← used by `models`, `services.finance`, `assets`; `services` ← used by route blueprints.

### External
- Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF / WTForms, Werkzeug.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
