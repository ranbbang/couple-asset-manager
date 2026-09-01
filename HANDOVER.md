# HANDOVER

Working notes on **this specific deployment/repo's** real state — accounts,
sensitive-data handling, and open items. `README.md` stays generic (anyone
could clone this and run it); this file is where the "who's actually in this
`app.db` right now and what still needs doing" facts live. Not meant to be
pretty — meant to save the next session (human or agent) from re-deriving
everything in this document from scratch.

*Last verified against the running code and `app.db` on 2026-09-01 — no
code changes since the previous update (`f95c3ba`); re-checked the account/
data state below and refreshed the parts that drift just from normal app
use (see the snapshot-count note).*

---

## 🔴 Sensitive-data handling — read this before touching accounts/import code

This app has run with **one real household's real financial data** during
development (imported from a personal Google Sheet). The rules that came out
of that, which apply to any future work here:

1. **Never write account numbers, card CVCs, or plaintext login passwords
   into code, commits, logs, `WORKLOG.md`, or this file.** The source
   Google Sheet's "공용" tab had exactly this kind of data (joint account
   numbers, a card CVC, and a table of website passwords) — it was
   deliberately excluded from the import entirely. If a future task touches
   that sheet or similar data again, exclude that category of information
   again, don't ask "should I include it," just don't.
2. **Any newly generated login credential (a temp password, an invite code
   tied to a real household, etc.) goes to the user in chat only — never
   into a file.** The two temp passwords generated when the real accounts
   were created (see below) were never written anywhere; they only ever
   existed in that session's chat output. If they've since been lost and
   never changed, the only way back in is a direct DB password reset (see
   "No password-reset flow" below) — not "check the repo for them," they
   were never there.
3. **Never re-fetch the original Google Sheet.** The import is done; the
   real data now lives in `app.db` (git-ignored, never committed). There's
   no standing reason to go back to the sheet, and doing so would just
   re-open the same sensitive-data-handling question for no benefit.
4. **The demo household (`jieun@example.com` / `minjun@example.com`,
   `couple_id=1`) must never be modified, deleted, or have its data mixed
   with the real household's.** It exists purely as seed/demo data for
   anyone cloning this repo (see `seed.py`). All real-data work targets
   `couple_id=2` only.
5. **Before any destructive DB operation** (schema change, bulk edit,
   reseed with `--force`), back up first: `python backup_db.py`, or call
   `app.services.backup.backup_database()` directly. `backups/` is
   git-ignored — it's a local safety net, not a place to hand off data.
6. **This repo (`ranbbang/couple-asset-manager`) is public on GitHub.**
   Anything written into a tracked file (this one included) is world-
   readable the moment it's pushed — treat that as a stricter bar than
   "don't commit secrets," since it also covers things that are merely
   personal (real names, a live invite code) rather than classic
   credentials. The real partners' names below are kept as "Partner A" /
   "Partner B" and the real household's invite code is deliberately left
   out (query the DB directly instead) for exactly this reason.

---

## Current real state of `app.db`

Two households coexist in the same database, deliberately kept apart:

| | Demo household | Real household |
|---|---|---|
| `couple_id` | 1 | 2 |
| Couple name | "지은♥민준네" (seed default) | "우리집" |
| Invite code | `LOVE2026` (public, in `seed.py`) | *(a real, live join code — this repo is public, so it's intentionally not written here; check the DB directly: `Couple.query.get(2).invite_code`)* |
| Users | `jieun@example.com`, `minjun@example.com` — demo, from `seed.py` | Partner A (`songbbang93@gmail.com` — real), Partner B (`yoon.ranyoung@example.com` — **placeholder, not her real email**) |
| Data | Sample accounts (카카오뱅크, AAPL/005930.KS/BTC-USD, etc.) | Real accounts/holdings imported from a Google Sheet export (see `WORKLOG.md`'s intro and the conversation history for the mapping decisions), plus historical `AssetSnapshot`s (4 imported from the sheet, one earlier month; more accrue automatically every time `/dashboard` or `/reports` is opened in a new calendar month — don't hardcode a count here, check `AssetSnapshot.query.filter_by(couple_id=2).count()` if it matters) and a "2026년 목표 순자산" goal |
| Passwords | `demo1234` for both (public, in `README.md`/`seed.py` on purpose) | Temporary, randomly generated at import time, given to the user in chat only (never written to a file — see above). **Unknown to this document.** |

**Open action for the real household**: Partner B's email is still the
`yoon.ranyoung@example.com` placeholder. She should log in and update it (and
her password, if the original temp one is lost) via **계정 설정 → `/auth/account`**
whenever she's ready. Nothing else depends on this being fixed by any
particular time.

### No password-reset ("forgot password") flow exists

`/auth/account` (added this session) lets a logged-in user change their
email/password, but it requires the **current** password to do so — there is
no "I forgot my password" self-service flow (no email sending is wired up
anywhere in this app, on purpose — no external services). If either real
account's temp password is lost before it's changed, the only recovery path
is a direct DB update:
```python
from app import create_app
from app.extensions import db
from app.models import User
app = create_app()
with app.app_context():
    u = User.query.filter_by(email="songbbang93@gmail.com").first()
    u.set_password("<new password, tell the user in chat, don't write it anywhere>")
    db.session.commit()
```
Worth building an actual forgot-password flow eventually (see Open Items).

---

## What this session did (full detail lives in `WORKLOG.md` and `AGENTS.md`)

1. **Imported the real household's data** from a Google Sheet the user
   shared: parsed each tab, mapped values onto this app's
   Couple/User/Category/Asset/Holding/Goal/AssetSnapshot model, explicitly
   excluding the sensitive account-number/CVC/password table (see above).
   Created a **new** Couple/User pair (`couple_id=2`) rather than touching
   the demo household, per the sensitive-data rules above.
2. **Added `/auth/account`** (email/display-name/password self-service,
   current-password gated) — didn't exist before; needed so the real
   household could eventually replace their temp passwords.
3. **Accessibility/resilience hardening pass** — WCAG contrast fix, focus
   rings, chart.js offline fallback, double-submit guard, `.row-between`
   CSS extraction, `aria-pressed` on toggles. (Commits `48cfaae`, `07d1b0e`.)
4. **A 12-round autonomous improvement loop** (self-paced, one round per
   `ScheduleWakeup` cycle, each round committed separately) — see
   `WORKLOG.md` for the full round-by-round writeup. Headline results:
   - **Three real, live bugs found and fixed**: an N+1 query pattern
     (`refresh_prices`: 45→17 SQL queries, measured directly), a negative
     cash-holding amount that silently corrupted every total that summed
     it (no error shown), and a `CategoryForm` validator that WTForms'
     `Optional()` silently prevented from ever running (an asset category
     could be saved with no report group, invisibly dropping its accounts
     out of every report chart).
   - **A test-infrastructure bug found and fixed twice** (once for `fx.py`,
     once for `prices.py`): their on-disk caches weren't isolated from the
     real project's `instance/` directory in tests — reproduced live once
     (the real `instance/fx_cache.json` got overwritten by a test's fake
     value), fixed, then verified fixed.
   - **Test coverage: 0 → 83 tests**, covering every service module
     (`finance`, `goals`, `backup`, `fx`, `prices`) and every route
     blueprint (`assets`, `categories`, `couple`, `goals`, `reports`,
     `main`) that previously had none.
   - **Both `AGENTS.md` files refreshed** — they'd drifted enough to
     actively mislead (referenced a nonexistent function, missing the
     `Holding`/`Category` models and the entire `categories/` blueprint).
5. **`README.md` and this file** — brought up to date with everything
   above; `README.md` covers the app generically, this file covers this
   deployment's specifics.

All 12 loop-round commits plus the earlier two are pushed to
`origin/master` as of this write-up.

---

## Open items / worth a look next session

Things noticed along the way that weren't fixed, either because they needed
a product decision this session didn't have grounds to make on its own, or
because they were lower-value than what got prioritized instead:

- **No forgot-password flow.** See above — currently a direct-DB-write
  recovery only.
- **`Holding.currency` isn't synced for a quote currency outside KRW/USD**
  (`services/prices.py::refresh_holdings`, documented + tested in
  `WORKLOG.md` Round 6 / `tests/test_prices.py`). A foreign-listed ticker
  (e.g. an LSE stock returning GBP from Yahoo) gets its price applied but
  keeps its old currency label. Not acted on because the app doesn't
  expose any currency besides KRW/USD anywhere in its UI yet — revisit if
  that ever changes.
- **A `Goal`'s `linked_category_ids`/`linked_asset_ids` aren't cleaned up
  when the category/asset they point to is deleted.** The link just goes
  silently inert (stops contributing to progress) rather than erroring or
  warning the user their goal quietly lost a data source. Would need a
  product decision on the right UX (warn on delete? auto-unlink and notify?).
- **Editing a category's `is_liability`/`is_real_estate`/`is_liquid` flags
  retroactively reclassifies every existing account in it**, with no
  confirmation step. This is arguably intentional (categories are meant to
  be fully dynamic), but it's easy to accidentally flip a chunk of net
  worth from "asset" to "liability" (or in/out of "부동산 제외 순자산")
  without realizing it. Worth a confirmation dialog if it ever bites someone.
- **`couple.join()` has a narrow TOCTOU race**: two people submitting the
  join form for the same invite code in the same instant could both pass
  the `is_full` check before either commits, landing 3 members in a
  2-person household. Extremely unlikely in practice (this app is used by
  exactly one couple at a time) — noted, not fixed.
- **One imported real-estate deposit figure (10,000,000 KRW, the couple's
  leased residence) is a rough estimate** taken from the source sheet's
  summary row, not an itemized figure — flagged at import time, never
  independently re-verified. Worth a quick check against the real lease
  terms whenever convenient. (Deliberately not naming the property here —
  see the public-repo note above; the asset's name in the app itself is
  enough to find it.)
- **No CI.** Tests exist (`pytest`, 83 passing) but nothing runs them
  automatically on push/PR. Would be a natural next step if this repo ever
  gets a second contributor or a hosted deployment.
