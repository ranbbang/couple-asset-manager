# 우리집 자산관리 — Couples Asset Management

A couples-focused personal finance web app inspired by **Monarch for Couples**.
Two partners share one financial dashboard built around transparency, shared
assets, shared goals, and a history-aware reports view.

> 모든 자산은 카테고리·통화별로 관리되고, 두 사람이 함께 순자산(Net Worth)을
> 키워가는 과정을 시간 흐름까지 한눈에 봅니다.

---

## ✨ Features

| # | Feature | Notes |
|---|---------|-------|
| 1 | **Auth** | Sign up / login / logout / **account settings** (change display name, email, password). Passwords hashed (Werkzeug), CSRF-protected forms, sessions. |
| 2 | **Couple invitation** | Create a household → shareable **invite code**. Partner joins by code. Max 2 members. |
| 3 | **Shared dashboard** | Total assets, total liabilities, **net worth** (KRW base), category breakdown, month-over-month change, net-worth sparkline, "생활비 N개월치" (liquid runway) once a monthly expense is set. |
| 4 | **Fully editable categories** | Categories are a per-household DB table, not a fixed list — add/rename/recolor/reorder/delete, toggle liability / real-estate / liquid flags, assign a report group. Seeded with 8 sensible defaults on signup. |
| 5 | **Multi-holding accounts** | An **Asset** (account) holds one or more **Holdings**: cash in a currency (KRW/USD), or a stock (ticker + quantity, priced live). Each asset has an **owner** (a partner or joint) and a category. |
| 6 | **Live stock prices & FX** | Stock quotes (Yahoo Finance, keyless) and the USD→KRW rate are fetched live, cached (memory + on-disk), and fall back to the last known value offline — no page load ever blocks on the network. |
| 7 | **Currency display toggle** | Asset Overview switches between **Separate by Currency** and **Combined Total** (everything converted to KRW at the cached/live rate). |
| 8 | **Shared & personal goals** | CRUD with a target amount and either manual saved/invested amounts, or auto-tracked progress linked to whole categories and/or individual accounts. Progress bar, ETA projection from recent pace. |
| 9 | **Asset Reports** | Historical net worth / asset growth / investment / cash / retirement trend charts, target-vs-current allocation with a rebalancing signal, CSV export. |
| 10 | **Activity log** | "OO님이 자산을 추가했습니다", "OO님이 스냅샷을 기록했습니다", … |

### Default categories (seeded on signup, fully editable afterward)
`현금` · `현금성 투자자산` · `중위험 투자자산` · `고위험 투자자산` ·
`노후·안전자산 (연금 등)` · `부동산` · `개인자산 (용돈·개인지출)` · `빚`

`빚` is a **liability**; every other category counts toward total assets.
**Net worth = Σ assets − Σ liabilities**, with USD holdings converted to KRW.
Each category also carries `is_real_estate` (excluded from "부동산 제외
순자산") and `is_liquid` (counted in the "생활비 몇 개월치" figure) flags, and
optionally rolls up into one of 4 fixed **report groups**
(`cash`/`investment`/`safe`/`personal`) used by the trend/allocation charts.

### Currencies & live prices
A holding is denominated in **KRW (₩)** or **USD ($)**. The live USD→KRW rate
comes from a free, no-key public API (`open.er-api.com`); stock quotes come
from Yahoo Finance's keyless chart endpoint. Both are cached server-side
(in-process memory + a JSON file under the Flask instance folder) and fall
back to the last known value — or a configurable default (`DEFAULT_USD_KRW`)
for the rate — when offline. No paid APIs, no API keys.

### How history works (Asset Reports)
The app stores one compact **monthly snapshot** per couple (`asset_snapshots`):
KRW-converted totals plus small JSON blobs of per-category/per-report-group/
per-currency totals. Snapshots auto-refresh on every dashboard/reports visit
and can be captured on demand with "이번 달 스냅샷 기록". Storing aggregated
KRW totals (not raw asset rows) keeps history cheap to query as it grows.

---

## 🧱 Tech Stack

- **Python 3.11 / Flask** — app-factory + blueprints
- **SQLAlchemy + SQLite** — zero external services for storage
- **Flask-Login** (sessions), **Werkzeug** (password hashing), **Flask-WTF** (CSRF)
- **Jinja2** templates + hand-written CSS design system (no build step), PWA shell (installable, service worker)
- **Chart.js** (CDN, with an offline/blocked-CDN fallback) for report/allocation charts
- Free public **FX** and **stock quote** APIs, both cached with offline fallback
- **pytest** — 83 tests covering every service module and route blueprint

---

## 🚀 Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (source .venv/bin/activate on *nix)
pip install -r requirements.txt

python seed.py                  # demo couple + assets (KRW & USD) + 12 months history
python run.py                   # → http://127.0.0.1:5000
```

### Demo logins (after `python seed.py`)

| Partner | Email | Password |
|---------|-------|----------|
| 지은 | `jieun@example.com` | `demo1234` |
| 민준 | `minjun@example.com` | `demo1234` |

Household invite code: **`LOVE2026`**

> For real deployment, copy `.env.example` → `.env`, set a strong `SECRET_KEY`,
> and optionally `DEFAULT_USD_KRW`. See `HANDOVER.md` for this deployment's
> actual account/household state and open items — don't rely on `README.md`
> for that, it stays generic on purpose.

### ⚠️ `seed.py` is non-destructive

`python seed.py` only seeds demo data into an **empty** database (first run).
If real accounts already exist, it refuses to touch anything and prints who's
there. To wipe everything and reseed demo data on purpose:

```bash
python seed.py --reset          # backs up app.db, then asks you to type RESET
python seed.py --reset --force  # same, but skips the confirmation prompt
```

### 💾 Backups

```bash
python backup_db.py             # copy app.db → backups/app_<timestamp>.db
python backup_db.py --list      # list existing backups, newest first
```
`seed.py --reset` also backs up automatically before wiping, and the app
itself takes one automatic daily backup on startup. The 20 most recent
backups are kept; older ones are pruned automatically. To restore, stop the
app and copy a file from `backups/` back over `app.db`.

### ✅ Running the tests

```bash
pip install -r requirements-dev.txt   # adds pytest on top of requirements.txt
pytest                                 # from the project root
```
Every test runs against an isolated, disposable SQLite file and an isolated
`instance/` cache directory (see `tests/conftest.py`'s module docstring) —
running the suite never touches your real `app.db` or its cached FX/price
files.

---

## 📁 Project Structure

```
쀼자산관리/
├── run.py                  # dev entry point (LAN-accessible: host 0.0.0.0)
├── seed.py                 # demo data + 12 months of snapshots (non-destructive; --reset to wipe)
├── backup_db.py            # manual app.db backup (backups/app_<timestamp>.db)
├── requirements.txt
├── requirements-dev.txt    # + pytest, for running tests/
├── .env.example            # SECRET_KEY / DATABASE_URL / FLASK_DEBUG
├── AGENTS.md                # repo map + conventions for AI coding agents
├── WORKLOG.md               # dated log of the autonomous improvement rounds
├── HANDOVER.md               # THIS deployment's real state — accounts, sensitive-data rules, open items
├── app/
│   ├── AGENTS.md            # same, scoped to the app/ package (more detail)
│   ├── __init__.py         # app factory + Jinja filters (won, won_short, money)
│   ├── config.py           # env-driven config (SECRET_KEY, DATABASE_URL, DEFAULT_USD_KRW)
│   ├── extensions.py       # db, login_manager, csrf
│   ├── constants.py        # DEFAULT_CATEGORIES (seed values), currencies, report groupings
│   ├── models.py           # Couple, User, Category, Asset, Holding, Goal, ActivityLog, AssetSnapshot
│   ├── decorators.py       # @couple_required
│   ├── services/
│   │   ├── finance.py      # currency-aware net-worth / breakdown / overview (pure functions)
│   │   ├── fx.py           # USD→KRW live rate (cached + offline fallback)
│   │   ├── prices.py       # stock quotes (Yahoo Finance, cached + offline fallback)
│   │   ├── snapshots.py    # monthly capture + report aggregation
│   │   ├── categories.py   # seed defaults / reorder / safe delete (reassigns assets first)
│   │   ├── goals.py        # goal progress math (pure functions over a pre-loaded asset list)
│   │   ├── activity.py     # activity-log helper
│   │   └── backup.py       # sqlite file backup (timestamped copies, auto-pruned)
│   ├── auth/                # signup / login / logout / account settings (blueprint + forms)
│   ├── couple/               # create / join / invite / household settings (blueprint + forms)
│   ├── main/                 # dashboard, activity feed, /api/fx-rate (blueprint)
│   ├── categories/            # category CRUD (blueprint + form)
│   ├── assets/                # account CRUD, holdings, price refresh, CSV export (blueprint + form)
│   ├── goals/                 # goal CRUD, category/asset linking (blueprint + form)
│   ├── reports/               # trends, target allocation, CSV export (blueprint)
│   ├── templates/          # base → shell → pages
│   └── static/
│       ├── css/styles.css  # design system
│       └── js/
│           ├── main.js     # reveal animations, comma inputs, submit-guard, PWA registration
│           ├── assets.js   # currency toggle + allocation charts
│           └── reports.js  # trend/allocation charts, KRW/USD + month/year
├── tests/                  # pytest suite — see conftest.py's docstring before adding fixtures
├── backups/                # timestamped app.db copies (git-ignored)
└── app.db                  # SQLite (created on first run / seed; git-ignored)
```

### Architecture notes
- **App factory** wires extensions, blueprints, Jinja helpers, creates tables,
  applies additive "micro-migrations" for new columns (`db.create_all()` never
  `ALTER`s existing tables), and takes a best-effort daily backup.
- **Blueprints** per feature area; **service layer** (`app/services/`) holds
  business logic (currency math, FX/price fetching, snapshots, goal progress)
  so routes stay thin and the logic is unit-testable without a request context.
- **An account has no currency of its own** — each `Holding` on it stores its
  own native `amount`/`currency` (or `quantity` + `cached_price` for a stock).
  `Holding.value_krw(rate)` / `Asset.value_krw(rate)` convert to the KRW base.
- **Charts** are client-side (Chart.js), with a graceful fallback message if
  the CDN is blocked or the browser is offline. Pages embed a JSON payload +
  the cached rate; JS fetches the live rate via `/api/fx-rate` and re-renders.
- **Tenant isolation**: every asset/category/goal/snapshot lookup is scoped to
  `couple_id`, 404-ing otherwise.
- **N+1 caution**: routes that need a full asset list eager-load explicitly
  (`selectinload(Asset.holdings, Asset.category)`) rather than walking the
  lazy `couple.assets` relationship — see `app/AGENTS.md` for the pattern.

---

## 🗄️ Database Schema

```
couples                users                    categories (per-household, editable)
-------                -----                    ----------
id (PK)                id (PK)                  id (PK)
name                   email (unique)           couple_id (FK couples)
invite_code (uniq)     password_hash            name (unique per couple)
monthly_expense_krw    display_name             icon / color
target_allocation      couple_id (FK, nullable) is_liability
  (JSON: {group: pct}) created_at               report_group (cash|investment|safe|personal|NULL)
created_at                                      is_real_estate / is_liquid
                                                 sort_order / created_at

assets                              holdings
------                              --------
id (PK)                             id (PK)
couple_id (FK)                      asset_id (FK assets)
owner_id (FK users, NULL = joint)   kind ('cash' | 'stock')
category_id (FK categories)         currency ('KRW' | 'USD')
name / institution / notes          amount (cash) / label
exclude_from_stats                  ticker / quantity / cached_price / cached_price_at (stock)
created_at / updated_at             sort_order

goals                                activity_logs             asset_snapshots
-----                                -------------             ---------------
id (PK)                              id (PK)                   id (PK)
couple_id (FK)                       couple_id (FK)            couple_id (FK)
owner_id (FK users, NULL = joint)    user_id (FK, nullable)    taken_on (Date, 1st of month)
name / target_amount                 action / detail / icon   net/total_assets/total_liabilities_krw
saved_amount / stocks_amount         created_at                real_estate_krw / net_worth_excl_re_krw
linked_category_ids (JSON list)                                category_totals / group_totals /
linked_asset_ids (JSON list)                                     currency_totals (JSON, per bucket)
created_at / updated_at                                        rate_used / created_at
                                                                UNIQUE(couple_id, taken_on)
```

Relationships: a **Couple** has up to two **Users**, and owns its
**Categories**, **Assets** (each with one or more **Holdings**), **Goals**,
**ActivityLogs**, and monthly **AssetSnapshots** (cascade delete on the
couple; deleting an asset cascades to its holdings).

---

## 🔒 Notes & Constraints

- **No external/paid APIs.** Data is entered manually; the only network calls
  are the free FX-rate and stock-quote lookups, both of which degrade
  gracefully to a cached/default value offline.
- Passwords hashed; forms CSRF-protected; `?next=` guarded against open-redirects.
- Ships with Flask's **development** server. For production use a WSGI server
  (waitress/gunicorn) behind HTTPS with a strong `SECRET_KEY`.
- **This repository has run with a real household's real financial data
  during development.** See `HANDOVER.md` for the sensitive-data handling
  rules that apply to this project specifically, and for this deployment's
  actual current state (which household/account is real vs. demo, etc.) —
  none of that belongs in this file.
