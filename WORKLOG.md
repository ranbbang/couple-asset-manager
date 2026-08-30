# WORKLOG

Autonomous improvement log. One entry per round: what was found, what changed,
how it was verified. Newest round on top.

**Absolute rules for every round (do not relax these):**
- Never touch the demo account/data: `jieun@example.com` / `minjun@example.com` (couple_id=1).
- Never re-access the source Google Sheet (no network calls to docs.google.com).
- Never write account numbers, card CVCs, or plaintext passwords/credentials
  into code, logs, commits, or this file.
- Back up `app.db` to `backups/` (existing naming convention) before any
  schema/migration change.
- Any newly generated login credentials go to chat only, never to a file.

---

## Round 0 — 2026-08-30

Setup: created this log. Earlier in this session (separate from the loop
below): imported real household data from the source Google Sheet into a new
Couple/User pair (kept the demo account untouched), added the `/auth/account`
settings page, and pushed an accessibility/resilience hardening pass —
commits `48cfaae` and `07d1b0e` on `master`.

Starting the improvement loop from here.

---

## Round 1 — 2026-08-30

**Found**: no `tests/` directory at all — `app/services/finance.py` (every
KRW total on the dashboard/reports/snapshots flows through it: total assets,
liabilities, net worth, real-estate exclusion, USD exposure %, owner/category
breakdown, currency split) had zero coverage. A regression there is a
silently wrong net-worth figure with no CI/local signal.

**Changed**: added `requirements-dev.txt` (pytest==9.1.1, layered on top of
`requirements.txt`), `tests/conftest.py` (app/db/couple/members/categories
fixtures on an in-memory `sqlite:///:memory:` DB — never touches `app.db`),
and `tests/test_finance.py` (11 tests) covering: asset/liability totals,
`exclude_from_stats` filtering, USD conversion + exposure % (incl. the
zero-total division-guard), real-estate inclusion/exclusion (incl. an edge
case: a liability category flagged `is_real_estate` must not count as real
estate — confirms the existing `not is_liability` guard in
`real_estate_total`), liquid-total filtering, owner breakdown (joint bucket
grouping + empty-row dropping), category breakdown (zero-amount skip), and
multi-currency holdings in one account.

**Verified**: `pytest` — 11/11 pass, ~1s.

**Side finding for next round**: running the test suite (via
`create_app(TestConfig)`) unexpectedly copied the *real* `app.db` into
`backups/` (`app_20260830_093850_auto.db`) even though tests point at
`sqlite:///:memory:`. Root cause: `app/services/backup.py::db_path()` reads
the hardcoded `app.config.Config.SQLALCHEMY_DATABASE_URI` class attribute
instead of the active `current_app.config`, so it ignores any config
override (test or otherwise). Not harmful (extra backup copy of legitimate
data, once/day guard limits it), but it breaks test isolation and would
silently back up/restore the wrong file under any real config override.
Picking this up next round.

---

## Round 2 — 2026-08-30

**Found**: (carried over from Round 1) `app/services/backup.py::db_path()`
read `app.config.Config.SQLALCHEMY_DATABASE_URI` — the class attribute —
instead of the active app's config, so any config override (test config,
or a future `DATABASE_URL` env-based deployment config) was silently
ignored and it always resolved to the real project's `app.db`.

**Changed**: `db_path()` now reads `current_app.config["SQLALCHEMY_DATABASE_URI"]`.
Verified this is behavior-preserving in production (the real app still
resolves to `D:\...\app.db`, since `Flask.config.from_object` copies the
same class attributes into `app.config` at startup) — the only behavior
change is that a *different* active config (like the test suite's
`sqlite:///:memory:`) is now respected instead of overridden.

**Added tests** (`tests/test_backup.py`): `db_path()` resolves from the
active (test) config, and `backup_database()` is a safe no-op — no file
created, no directory touched — when the active DB has no on-disk file
(the `:memory:` case). Confirmed manually too: `ls backups/` before/after
the full test run showed zero new files (Round 1's fix reproduced the bug
by creating `app_20260830_093850_auto.db`; this round's fix prevents a
repeat).

**Verified**: `pytest` — 13/13 pass (~1.2s). Real app backup path
double-checked via `create_app()` + `db_path()` printing the correct real
`app.db` path.
