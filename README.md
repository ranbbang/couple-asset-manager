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
| 1 | **Auth** | Sign up / login / logout. Passwords hashed (Werkzeug), CSRF-protected forms, sessions. |
| 2 | **Couple invitation** | Create a household → shareable **invite code** (shared key). Partner joins by code. Max 2 members. |
| 3 | **Shared dashboard** | Total assets, total liabilities, **net worth** (KRW base), category breakdown. |
| 4 | **Manual asset entry** | Full CRUD. Each asset has a category, an **owner** (partner or joint), and a **currency** (KRW/USD). |
| 5 | **Currency display toggle** | Asset Overview switches between **Separate by Currency** (KRW vs USD totals) and **Combined Total** (everything converted to KRW at the live rate). |
| 6 | **Shared goals** | CRUD with name, target, saved amount, stocks amount, and a progress bar. |
| 7 | **Asset Reports** | Historical **net worth / asset growth / investment / cash / retirement** trends, allocation & breakdown charts. Monthly & yearly views, KRW/USD modes. |
| 8 | **Activity log** | "지은님이 자산을 추가했습니다", "민준님이 스냅샷을 기록했습니다", … |

### Asset categories
`Cash` · `Cash Equivalent Investments` · `Medium-Risk Investments` ·
`High-Risk Investments` · `Safe Assets (Real Estate, Pension, etc.)` ·
`Personal Assets (Allowance / Personal Spending Money)` · `Debt (빚)`

`Debt (빚)` is a **liability**; every other category counts toward total assets.
**Net worth = Σ assets − Σ liabilities**, with USD balances converted to KRW.

### Currencies & exchange rate
Each asset is denominated in **KRW (₩)** or **USD ($)**. The live USD→KRW rate
is fetched from a **free, no-key public API** (`open.er-api.com`), cached
server-side (memory + file), and falls back to a configurable default
(`DEFAULT_USD_KRW`, ~1,350) when offline. No paid APIs.

### How history works (Asset Reports)
The app stores one compact **monthly snapshot** per couple (`asset_snapshots`):
KRW-converted category totals + net worth. Snapshots auto-refresh on each
reports visit and can be captured on demand with **"이번 달 스냅샷 기록"**. Storing
KRW totals (not raw rows) keeps the reports fast and cheap as history grows.

---

## 🧱 Tech Stack

- **Python 3.11 / Flask** — app-factory + blueprints
- **SQLAlchemy + SQLite** — zero external services for storage
- **Flask-Login** (sessions), **Werkzeug** (password hashing), **Flask-WTF** (CSRF)
- **Jinja2** templates + hand-written CSS (no build step)
- **Chart.js** (CDN) for report/allocation charts
- Free public **FX API** for live USD↔KRW (cached + offline fallback)

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
> and optionally `DEFAULT_USD_KRW`.

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
`seed.py --reset` also backs up automatically before wiping. The 20 most
recent backups are kept; older ones are pruned automatically. To restore, stop
the app and copy a file from `backups/` back over `app.db`.

---

## 📁 Project Structure

```
쀼자산관리/
├── run.py                  # dev entry point (LAN-accessible: host 0.0.0.0)
├── seed.py                 # demo data + 12 months of snapshots (non-destructive; --reset to wipe)
├── backup_db.py             # manual app.db backup (backups/app_<timestamp>.db)
├── requirements.txt
├── .env.example            # SECRET_KEY / DATABASE_URL / DEFAULT_USD_KRW
├── app/
│   ├── __init__.py         # app factory + Jinja filters (won, money)
│   ├── config.py           # env-driven config (+ DEFAULT_USD_KRW)
│   ├── extensions.py       # db, login_manager, csrf
│   ├── constants.py        # categories, currencies, report groupings
│   ├── models.py           # Couple, User, Asset(+currency), Goal, ActivityLog, AssetSnapshot
│   ├── decorators.py       # @couple_required
│   ├── services/
│   │   ├── finance.py      # currency-aware net-worth / breakdown / overview
│   │   ├── fx.py           # USD→KRW live rate (cached + offline fallback)
│   │   ├── snapshots.py    # capture + report aggregation
│   │   └── activity.py     # activity-log helper
│   ├── auth/ couple/ main/ assets/ goals/ reports/   # blueprints
│   ├── templates/          # base → shell → pages (+ reports, charts)
│   └── static/
│       ├── css/styles.css  # design system (+ toggle, charts)
│       └── js/
│           ├── main.js     # relative time, copy buttons
│           ├── assets.js   # currency toggle + allocation charts
│           └── reports.js  # trend/allocation charts, KRW/USD + month/year
└── app.db                  # SQLite (created on first run / seed)
```

### Architecture notes
- **App factory** wires extensions, blueprints, Jinja helpers, and creates tables.
- **Blueprints** per feature area; **service layer** holds business logic
  (currency math, FX, snapshots) so routes stay thin and testable.
- **Currency model**: balances are stored in their native currency; the service
  layer converts to a **KRW base** for combined totals, the dashboard, and
  snapshots. The "Separate" view uses native per-currency sums (no conversion).
- **Charts** are client-side (Chart.js). Pages embed a JSON payload + the cached
  rate; JS fetches the live rate via `/api/fx-rate` and re-renders.
- **Tenant isolation**: every asset/goal/snapshot lookup is scoped to `couple_id`.

---

## 🗄️ Database Schema

```
couples            users                  assets
-------            -----                  ------
id (PK)            id (PK)                id (PK)
name               email (unique)         couple_id (FK couples)
invite_code (uniq) password_hash          owner_id (FK users, NULL = joint)
created_at         display_name           name
                   couple_id (FK)         category   (1 of 7)
                   created_at             balance    (Numeric 16,2)
goals                                     currency   ('KRW' | 'USD')
-----              activity_logs          institution / notes
id (PK)            -------------          created_at / updated_at
couple_id (FK)     id (PK)
name               couple_id (FK)         asset_snapshots
target_amount      user_id   (FK)         ---------------
saved_amount       action / icon         id (PK)
stocks_amount      created_at             couple_id (FK)
created/updated                           taken_on (Date, 1st of month)
                                          net_worth_krw / total_assets_krw /
                                          total_liabilities_krw
                                          category_totals (JSON, KRW)
                                          currency_totals (JSON, native)
                                          rate_used / created_at
                                          UNIQUE(couple_id, taken_on)
```

Relationships: a **Couple** has up to two **Users** and owns its **Assets**,
**Goals**, **ActivityLogs**, and monthly **AssetSnapshots** (cascade delete).

---

## 🔒 Notes & Constraints

- **No external/paid APIs.** Data is entered manually; the only network call is
  the free FX rate, which degrades gracefully to a cached/default value offline.
- Passwords hashed; forms CSRF-protected; `?next=` guarded against open-redirects.
- Ships with Flask's **development** server. For production use a WSGI server
  (waitress/gunicorn) behind HTTPS with a strong `SECRET_KEY`.
