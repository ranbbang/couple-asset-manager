"""Seed the database with a demo couple, editable categories, accounts with
holdings (cash + stock tickers), linked goals, and 12 months of snapshots.

Usage:
    python seed.py              First run only: seeds demo data into an empty
                                 database. Refuses to touch a database that
                                 already has real user accounts.
    python seed.py --reset      Wipes ALL existing data and reseeds demo data.
                                 Always backs up app.db first (see backups/),
                                 and asks for interactive confirmation unless
                                 --force is also given.
    python seed.py --reset --force
                                 Same as --reset, but skips the confirmation
                                 prompt (for scripted/non-interactive use).

This script is intentionally non-destructive by default: it will NOT drop
existing data just because you ran it again. A prior version of this script
unconditionally called db.drop_all() on every run, which silently destroyed
real signed-up accounts during routine re-seeding after schema changes.
"""
import argparse
import json
import random
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal

# Windows consoles often default to cp949/cp1252, which can't encode the ⚠️/✅
# characters below and would otherwise crash mid-run. UTF-8 works everywhere.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from app import create_app
from app.extensions import db
from app.models import (
    ActivityLog,
    Asset,
    AssetSnapshot,
    Couple,
    Goal,
    Holding,
    User,
)
from app.services.backup import backup_database
from app.services.categories import create_default_categories
from app.services.snapshots import _compute, month_start

SEED_RATE = Decimal("1350")

# Demo stock prices (set so the seed needs no network; refresh updates them live).
DEMO_PRICES = {
    "AAPL": ("230.00", "USD"),
    "005930.KS": ("78000", "KRW"),   # 삼성전자
    "BTC-USD": ("95000.00", "USD"),
    "TSLA": ("250.00", "USD"),
}


def add_months(d: date, delta: int) -> date:
    m = d.month - 1 + delta
    y = d.year + m // 12
    return date(y, m % 12 + 1, 1)


def seed_snapshots(couple) -> None:
    """12 monthly snapshots ending at the couple's current totals."""
    random.seed(42)
    base = month_start()
    now_c = _compute(couple.assets, SEED_RATE)

    for i in range(12):
        taken_on = add_months(base, i - 11)
        progress = 0.62 + 0.38 * (i / 11)
        wobble = 1.0 if i == 11 else (1 + random.uniform(-0.03, 0.03))
        factor = progress * wobble if i < 11 else 1.0

        cats = {k: float(v) * factor for k, v in now_c["cat_totals"].items()}
        grps = {k: float(v) * factor for k, v in now_c["group_totals"].items()}
        curs = {k: float(v) * factor for k, v in now_c["cur_totals"].items()}
        assets_krw = float(now_c["assets_krw"]) * factor
        liab_krw = float(now_c["liab_krw"]) * factor
        re_krw = float(now_c["re_krw"]) * factor
        net = assets_krw - liab_krw

        db.session.add(AssetSnapshot(
            couple_id=couple.id, taken_on=taken_on,
            total_assets_krw=Decimal(str(round(assets_krw, 2))),
            total_liabilities_krw=Decimal(str(round(liab_krw, 2))),
            net_worth_krw=Decimal(str(round(net, 2))),
            real_estate_krw=Decimal(str(round(re_krw, 2))),
            net_worth_excl_re_krw=Decimal(str(round(net - re_krw, 2))),
            category_totals=json.dumps(cats),
            group_totals=json.dumps(grps),
            currency_totals=json.dumps(curs),
            rate_used=SEED_RATE, created_at=datetime.utcnow(),
        ))


def _existing_accounts_summary() -> list[str]:
    """One line per existing user, for the pre-wipe warning."""
    lines = []
    for u in User.query.order_by(User.id).all():
        couple_name = u.couple.name if u.couple else "(가구 없음)"
        lines.append(f"    #{u.id}  {u.email}  ·  {u.display_name}  ·  {couple_name}")
    return lines


def run(reset: bool, force: bool) -> None:
    app = create_app()
    with app.app_context():
        # create_app() already ran db.create_all(), so this count is safe even
        # on a brand-new database (tables exist but are empty).
        existing_users = User.query.count()

        if existing_users > 0 and not reset:
            print(f"⚠️  데이터베이스에 이미 사용자 계정이 {existing_users}개 있습니다:")
            for line in _existing_accounts_summary():
                print(line)
            print()
            print("아무것도 건드리지 않았습니다. 데모 데이터로 완전히 초기화하려면:")
            print("    python seed.py --reset")
            print("(app.db는 초기화 전에 자동으로 backups/ 에 백업됩니다)")
            sys.exit(1)

        if existing_users > 0 and reset:
            print(f"⚠️  다음 {existing_users}개 계정과 모든 데이터가 삭제됩니다:")
            for line in _existing_accounts_summary():
                print(line)
            print()
            if not force:
                answer = input("정말 초기화하려면 대문자로 RESET 을 입력하세요: ")
                if answer.strip() != "RESET":
                    print("취소되었습니다. 아무것도 변경하지 않았습니다.")
                    sys.exit(1)

            backup_path = backup_database(reason="pre_reset")
            if backup_path:
                print(f"✅ 백업 완료: {backup_path}")
            else:
                print("(백업할 기존 app.db 파일이 없습니다)")

        print("Resetting database...")
        db.drop_all()
        db.create_all()

        couple = Couple(name="지은♥민준네", invite_code="LOVE2026")
        db.session.add(couple)
        db.session.flush()

        create_default_categories(couple)
        db.session.flush()
        cat = {c.name: c for c in couple.categories}

        jieun = User(email="jieun@example.com", display_name="지은", couple_id=couple.id)
        jieun.set_password("demo1234")
        minjun = User(email="minjun@example.com", display_name="민준", couple_id=couple.id)
        minjun.set_password("demo1234")
        db.session.add_all([jieun, minjun])
        db.session.flush()

        now = datetime.utcnow()

        def cash(currency, amount, label=None, order=0):
            return Holding(kind="cash", currency=currency,
                           amount=Decimal(str(amount)), label=label, sort_order=order)

        def stock(ticker, qty, order=0):
            price, cur = DEMO_PRICES[ticker]
            return Holding(kind="stock", currency=cur, ticker=ticker,
                           quantity=Decimal(str(qty)), cached_price=Decimal(price),
                           cached_price_at=now, sort_order=order)

        def account(name, cat_name, holdings, owner=None, institution=None, exclude=False):
            a = Asset(couple_id=couple.id, owner_id=owner.id if owner else None,
                      category_id=cat[cat_name].id, name=name,
                      institution=institution, exclude_from_stats=exclude)
            a.holdings = holdings
            return a

        C_CASH, C_CEQ = "현금", "현금성 투자자산"
        C_MID, C_HIGH = "중위험 투자자산", "고위험 투자자산"
        C_SAFE, C_RE = "노후·안전자산 (연금 등)", "부동산"
        C_PERS, C_DEBT = "개인자산 (용돈·개인지출)", "빚"

        accounts = [
            account("카카오뱅크 입출금", C_CASH, [cash("KRW", 3_200_000)], None, "카카오뱅크"),
            account("토스 생활비 통장", C_CASH, [cash("KRW", 1_450_000)], None, "토스뱅크"),
            account("신한 정기적금", C_CEQ, [cash("KRW", 12_000_000)], None, "신한은행"),
            account("주택청약저축", C_CEQ, [cash("KRW", 6_800_000)], None, "국민은행"),
            account("하나은행 외화예금", C_CEQ, [cash("USD", 5_000)], None, "하나은행"),
            account("채권형 펀드", C_MID, [cash("KRW", 7_000_000)], None, "미래에셋"),
            account("키움 ETF 적립", C_MID, [cash("KRW", 8_200_000)], None, "키움증권"),
            # ★ mixed account: USD cash 예수금 + US stock + KR stock (req 0+1)
            account("토스증권 계좌", C_HIGH, [
                cash("USD", 1_200, "예수금", 0),
                stock("AAPL", 10, 1),
                stock("005930.KS", 5, 2),
            ], jieun, "토스증권"),
            account("업비트", C_HIGH, [stock("BTC-USD", 0.05)], minjun, "업비트"),
            account("지은 IRP", C_SAFE, [cash("KRW", 9_500_000)], jieun, "미래에셋"),
            account("민준 국민연금", C_SAFE, [cash("KRW", 7_300_000)], minjun, "국민연금공단"),
            account("신혼 전세 보증금", C_RE, [cash("KRW", 180_000_000)], None, "OO아파트 전세"),
            account("지은 용돈 통장", C_PERS, [cash("KRW", 400_000)], jieun, "카카오뱅크"),
            account("민준 용돈 통장", C_PERS, [cash("KRW", 350_000)], minjun, "토스뱅크"),
            account("회사 복지포인트 (참고용)", C_PERS, [cash("KRW", 500_000)], jieun, "사내 포인트", exclude=True),
            account("전세자금대출", C_DEBT, [cash("KRW", 120_000_000)], None, "주택금융공사"),
            account("민준 신용카드 대금", C_DEBT, [cash("KRW", 1_800_000)], minjun, "현대카드"),
        ]
        db.session.add_all(accounts)
        db.session.flush()

        # Goals — two linked (auto), one manual fallback.
        goals = [
            Goal(couple_id=couple.id, name="내 집 마련 (자가)", target_amount=Decimal(300_000_000),
                 linked_category_ids=json.dumps([cat[C_RE].id, cat[C_SAFE].id]),
                 linked_asset_ids="[]"),
            Goal(couple_id=couple.id, name="비상금 6개월치", target_amount=Decimal(20_000_000),
                 linked_category_ids=json.dumps([cat[C_CASH].id, cat[C_CEQ].id]),
                 linked_asset_ids="[]"),
            Goal(couple_id=couple.id, name="유럽 신혼여행", target_amount=Decimal(8_000_000),
                 saved_amount=Decimal(3_500_000), stocks_amount=Decimal(0),
                 linked_category_ids="[]", linked_asset_ids="[]"),
        ]
        db.session.add_all(goals)

        feed = [
            (minjun, "민준님이 '지은♥민준네' 가구를 만들었습니다.", "🏡", 6),
            (jieun, "지은님이 가구에 합류했습니다. 💕", "💕", 6),
            (jieun, "지은님이 '신한 정기적금' 자산을 추가했습니다.", "💰", 5),
            (minjun, "민준님이 '전세자금대출' 자산을 추가했습니다.", "💳", 4),
            (jieun, "지은님이 '내 집 마련 (자가)' 목표를 만들었습니다.", "🎯", 3),
            (minjun, "민준님이 '토스증권 계좌'에 주식을 추가했습니다.", "📈", 2),
        ]
        for actor, action, icon, days_ago in feed:
            db.session.add(ActivityLog(couple_id=couple.id, user_id=actor.id, action=action,
                                       icon=icon, created_at=now - timedelta(days=days_ago, hours=2)))

        seed_snapshots(couple)
        db.session.commit()

        print("Seed complete!")
        print("  Invite code : LOVE2026")
        print("  Logins      : jieun@example.com / minjun@example.com  (demo1234)")
        print(f"  Categories  : {len(couple.categories)} (incl. 부동산), accounts: {len(accounts)}")
        stock_n = sum(1 for a in accounts for h in a.holdings if h.kind == 'stock')
        print(f"  Stock holdings: {stock_n}, snapshots: 12 months")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true",
                        help="Wipe all existing data and reseed demo data (backs up app.db first).")
    parser.add_argument("--force", action="store_true",
                        help="With --reset, skip the interactive RESET confirmation prompt.")
    args = parser.parse_args()
    run(reset=args.reset, force=args.force)
