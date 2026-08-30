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

---

## Round 3 — 2026-08-30

**Found**: `app/assets/routes.py::refresh_prices()` built its holdings list
from `current_user.couple.assets[*].holdings` — a classic N+1 (1 query for
the assets list, then 1 more per asset the first time its `.holdings` is
touched). Confirmed directly against the real household's data (Couple 2,
29 assets, read-only `SELECT`s only) with a query-count harness: **30
queries** for that access pattern vs **2** with `selectinload`. The same
`couple.assets` pattern also showed up in `services/snapshots.py::capture_snapshot()`
(called by every asset write **and** by every `/reports` page load, via
`refresh_current_month`) and in `services/goals.py::current_amount()` /
`goals/routes.py::_populate_links()`.

**Changed**:
- `assets/routes.py::refresh_prices()` — eager-loads assets+holdings via
  `selectinload` instead of the lazy `couple.assets` relation.
- `services/snapshots.py::capture_snapshot()` — same fix; benefits every
  caller (`refresh_current_month`, the direct `capture_snapshot` call in
  reports) without changing their signatures.
- `services/goals.py::current_amount/progress_pct/goal_view` — signature
  changed from `(goal, couple, rate, ...)` to `(goal, assets, rate, ...)`,
  so callers pass an already-loaded list instead of the function touching
  `couple.assets` itself. Updated both call sites: `main/routes.py::dashboard()`
  (already had `assets` in scope) and `goals/routes.py::index()` (added its
  own eager-loaded fetch, matching the pattern in `assets/routes.py::index()`).

**Honest results, not just the theory**: built an integration test
(`tests/test_query_counts.py`) hitting `/dashboard`, `/goals/`, and
`/assets/refresh-prices` through the real Flask test client with 15 assets
+ 3 category-linked goals, counting actual SQL statements before vs. after
each fix:
  - `refresh_prices`: **45 → 17** — the clean, unambiguous win; nothing else
    in that request path had already warmed the identity map.
  - `/dashboard`: **10 → 10**, no change — `dashboard()` already ran its own
    eager-loaded assets query *before* calling `goal_view`, which happened
    to populate every asset's `holdings`/`category` in the SQLAlchemy
    identity map first, so the old `couple.assets` access wasn't actually
    N+1-ing on its own in this path — it was riding on someone else's
    eager load. Kept the explicit-assets version anyway: it's the correct,
    self-contained interface and doesn't depend on another module having
    already warmed the cache.
  - `/goals/`: **2 → 5** — went *up*, not down, at this scale (adds one
    fixed `selectinload` round trip that the old lazy path didn't always
    pay for locally). Kept for the same reason as dashboard, and because
    `services/goals.py` no longer needs a live `Couple` ORM object at all
    (see `tests/test_goals_service.py`, which unit-tests it with plain
    lists) — a real testability win independent of the query count.

Recorded this plainly instead of writing up three matching "before/after"
wins, because two of the three didn't hold up the way the initial theory
predicted, and that's worth knowing for the next N+1 hunt in this codebase:
identity-map caching from an *unrelated* earlier query in the same request
can mask a lazy-relationship access that looks identical to one that
genuinely does N+1 in isolation.

**Also found & fixed** (uncovered while building the integration tests
above): `tests/conftest.py`'s `members` fixture used `@test.local` email
addresses. `.local` is an IANA-reserved TLD, and `email_validator` — which
WTForms' `Email()` validator calls even with `check_deliverability=False`
— rejects it outright as "a special-use or reserved name." Every
`_login()`-style test using that fixture was silently failing at the login
form and asserting on the *login page*, not the page under test — the
query-count assertions were passing vacuously against near-zero query
counts. Switched to `@example.com` (RFC 2606, and what the app's own seed
data already uses) and added a `_login()` helper that hard-asserts
"로그아웃" appears in the response, so a broken login can never again pass
silently. Also switched `tests/conftest.py`'s `app` fixture from
`sqlite:///:memory:` to a `tmp_path`-backed file DB while investigating
this, since an in-memory DB isn't visible across the separate connection a
live test-client request can open — a second, independent trap for the
same class of "test silently does nothing" failure. Neither of these
affected Round 1/2's tests (pure function calls within one session), only
the new HTTP-level ones.

**Verified**: `pytest` — 22/22 pass (~3-6s). Sanity-checked
`services/snapshots.report_data()` against the real household (Couple 2)
post-fix with no errors.

---

## Round 4 — 2026-08-30

**Found**: `assets/routes.py::_parse_holdings()` parsed a cash holding's
amount with `_dec()` and only skipped a row if it was exactly `0` with no
label — a negative amount (e.g. a typo'd `-50000`) was accepted as-is, no
error, no warning. Confirmed the actual damage with the test below before
writing the fix: it silently produced `"assets": -1.0` in the account's own
overview JSON payload, quietly shrinking every total that sums holdings
(account value, category breakdown, dashboard net worth) — the wrong
number ships with no visible sign anything failed. There's no modeled
concept of "negative cash" in this schema; a debt belongs in the 빚
category as its own positive amount.

**Changed**: `_parse_holdings()` now raises a `NegativeAmountError` (with a
message naming the offending row) when a cash amount is negative; `create()`
and `edit()` in `assets/routes.py` catch it and re-render the form with a
flash error instead of silently saving. Stock quantities already had an
equivalent guard (`qty <= 0: continue`) — this brings cash amounts in line.

**Verified**: `tests/test_assets_routes.py` (3 tests) — posts a negative
amount to `/assets/new` and confirms no Asset is created and the error
message shows; confirms a positive amount still saves normally (regression
guard); confirms editing an existing asset with a negative amount is also
rejected and leaves the original holding untouched. Checked these tests
actually catch the bug, not just pass vacuously: reverted the routes.py
change and re-ran — 2 of 3 failed exactly as expected, with the failure
output showing the real pre-fix payload
(`"assets": -1.0, "byCategory": {"1": -1.0}`), confirming both the bug and
that the test suite catches it. Full suite: `pytest` — 25/25 pass.

---

## Round 5 — 2026-08-30

**Found**: `services/fx.py` and `services/prices.py` cache to a JSON file
under `current_app.instance_path`. Flask defaults `instance_path` to a
fixed `<project_root>/instance/` directory — nothing in `TestConfig`
touches it. Any test that reaches `fx.py` (directly, or indirectly through
a route — `dashboard`, `goals/`, and `refresh-prices` all call
`fx.get_cached_rate()`) reads and can **overwrite the real app's live**
`instance/fx_cache.json`.

**Proved it wasn't theoretical** before fixing: saved the real file's exact
bytes (`{"rate": 1383.118493, ...}`), reverted the fixture change, ran just
the one new test that exercises a successful live-fetch-and-cache path —
the real `instance/fx_cache.json` came back as `{"rate": 1500.25, ...}`
(the test's fake value). Restored the real file's original bytes
immediately after confirming. This was a real, reproducible bug in the
test setup, not a hypothetical.

**Changed**: `tests/conftest.py`'s `app` fixture now reassigns
`application.instance_path` to a `tmp_path` subdirectory right after
`create_app()`. Reassigning the plain attribute post-construction is
sufficient — nothing else in Flask caches a separate copy of it.

**Added tests** (`tests/test_fx.py`, 9 tests — `fx.py` had zero coverage
before this): cache precedence (memory > file > config default), TTL
honored (mocked `urlopen` never called within TTL), successful live fetch
updates memory + file cache, network-error fallback, non-positive-rate
guard (a bad live value must not get promoted into the cache), stale
cache preferred over the config default after TTL expiry, and an explicit
regression test that runs real fx.py activity and diffs the real project's
`instance/fx_cache.json` before/after (asserting no change) while also
asserting the *test's own* isolated cache file *was* written (so the test
isn't a no-op either way).

**Verified**: `pytest` — 34/34 pass (~10s, includes network mocking via
`unittest.mock.patch` — no real network calls). Confirmed
`instance/fx_cache.json`'s real content is byte-identical before and after
the full suite run.

---

## Round 6 — 2026-08-30

**Found**: `services/prices.py` (stock quote fetch/cache/fallback, and the
`refresh_holdings()` that actually mutates Holding rows) had zero test
coverage — the second half of the same "the two network services have no
tests" gap Round 5 started closing for `fx.py`.

**Added tests** (`tests/test_prices.py`, 9 tests): live fetch caches to
memory + file; TTL skip (mocked `urlopen` asserted never called); file-cache
fallback on network error; a ticker with no cache and a failed fetch is
correctly *omitted* from the result (not a crash, not a bogus zero);
blank/`None` tickers are skipped without ever touching the network; a
ticker that fails to fetch keeps its previously-cached price in the merged
file-cache write instead of being wiped (the exact behavior the comment
above that code claims, now actually asserted); `refresh_holdings()` only
updates stock holdings with a resolvable quote and leaves cash holdings /
un-ticker'd stocks / unquotable tickers untouched; and — following Round
5's finding — an explicit before/after diff of the real project's
`instance/price_cache.json`, confirming the isolated `instance_path` fixture
from Round 5 already covers this service too (no new isolation bug found
here, but worth checking rather than assuming).

**Also documented, not changed**: `refresh_holdings()` only syncs a
holding's stored currency to the quote's currency when that currency is
`KRW` or `USD` (the app's only two supported currencies) — for a
foreign-listed ticker where Yahoo returns e.g. `GBP`, the price is still
applied but the currency label is silently left as whatever it was before,
which would misrepresent the value if it's ever meaningfully different
from KRW/USD terms. Added a test that pins down and names this behavior
explicitly rather than changing it — the app doesn't currently expose any
other currency in its UI, so there's no clear product intent to act on
without asking; flagging it here for whoever adds non-KRW/USD support.

**Verified**: `pytest` — 43/43 pass (~10s). Confirmed both
`instance/price_cache.json` and `instance/fx_cache.json` byte-identical
before/after this round's test run.

---

## Round 7 — 2026-08-30

**Found a real, currently-live bug** while writing `tests/test_categories_routes.py`
(no coverage before this round): `CategoryForm.report_group`'s intended
rule — "an asset (non-liability) category must have a report group" —
never actually ran. The field had `validators=[Optional()]`, and
`Optional()` raises `StopValidation` on empty input, which skips every
later validator for that field **including** the form's own
`validate_report_group()` method (WTForms treats `validate_<field>` as
just another validator appended to that field's chain). Confirmed with a
minimal WTForms repro outside the app before touching anything: with
`Optional()` present, the custom validator's own print statement never
ran; with it removed, it ran every time. Real consequence: a category
could be saved as an asset category with `report_group = None`, silently
excluding every account in it from all report-group aggregation
(`services/snapshots.py::_compute()`'s `group_totals` only adds a category
`if cat.report_group in group_totals`) — the category's money would still
count in total assets but vanish from every report chart and from the
target-allocation feature, with no error anywhere.

**Changed**: `app/categories/forms.py` — removed `Optional()` from
`report_group`'s validators (kept the field itself un-required at the
WTForms level; `validate_report_group()` already correctly allows an empty
value for liability categories and rejects it otherwise).

**Verified the fix both ways**: minimal WTForms-only repro before touching
app code (validator visibly skipped with `Optional()`, ran without it);
then `tests/test_categories_routes.py` (8 tests: duplicate-name rejection,
the report-group requirement itself, liability categories correctly
exempted, cross-household 404 on edit, delete blocked as last category,
delete blocked with assets and no reassign target, delete+reassign
succeeds, move swaps sort_order) — reverted just the forms.py fix and
reran the report-group test alone: failed exactly as expected (category
saved anyway, no error shown). Restored the fix.

**Checked for existing damage**: queried every `Category` row in the real
`app.db` (both the demo household and the real Couple 2) for an asset
category with no report group — none found, so no existing data needs
correcting; this was a bug nobody had hit yet, not one already skewing the
real household's reports.

**Verified**: `pytest` — 51/51 pass (~15s).

---

## Round 8 — 2026-08-30

**Checked for the same bug shape elsewhere first** (per the process note):
grepped every `*/forms.py` for `def validate_<field>` methods — only two
exist in the whole codebase. `validate_report_group` (Round 7, now fixed).
The other, `AccountForm.validate_new_password` (added earlier this
session), uses `Length(min=0, max=128)` on the field, not `Optional()` —
`Length` never raises `StopValidation`, only `ValidationError` on an
out-of-range value, and `min=0` never fails for an empty string, so the
chain always reaches the custom validator. Confirmed directly rather than
just reading the code: called `AccountForm.validate()` with an empty
`new_password` (no error raised, correct — empty means "don't change it")
and with a 5-character one (correctly rejected with the "8자 이상" message).
No second instance of Round 7's bug exists.

**Added tests** (`tests/test_couple_routes.py`, 8 tests —
`app/couple/routes.py` had zero coverage before this round): creating a
household seeds all 8 default categories; a blank household name falls
back to "우리집"; joining with an invalid invite code is rejected and
leaves the user without a couple; joining with a valid code links the
user and updates `couple_id`; joining a couple that already has 2 members
is rejected (server-side, not just hidden in the UI); the monthly-expense
setting rejects a negative value, correctly clears on a blank submission,
and accepts a comma-formatted amount (e.g. `2,500,000`). No bug found
here — all 8 passed on the first run against the existing code; this
round is pure coverage, following Round 6's pattern rather than Round 7's.

**Verified**: `pytest` — 59/59 pass (~20s).

---

## Round 9 — 2026-08-30

**Added tests** (`tests/test_reports_routes.py`, 6 tests —
`app/reports/routes.py` had zero coverage before this round): target
allocation saves partial percentages (blank fields skipped), rejects a
combined total over 100%, rejects a non-numeric value, rejects an
out-of-range percentage; manually recording a snapshot creates exactly one
`AssetSnapshot` for the current month; CSV export contains the expected
month and figures.

**One test wrong, not the code**: `test_export_csv_contains_snapshot_history`
initially asserted the net-worth column would be comma-formatted
(`"1,000,000"`) — it isn't; `export_csv()` writes that column as a plain
`round(float(...))` int with `csv.writer`, and only the separate
"카테고리별 상세" column applies `:,`-formatting per the route's own code.
Fixed the test's expectation rather than the route, since the actual
behavior is internally consistent (spreadsheet apps read a plain numeric
column correctly; the detail column is free text, where the comma is just
for human readability) and nothing depends on the omitted case.

**Verified**: `pytest` — 65/65 pass (~24s). No source bug found this round
— pure coverage, like Round 6 and Round 8.
