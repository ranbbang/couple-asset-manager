"""SQLAlchemy models.

Relationships:
    Couple 1—* User        (a household has up to two partners)
    Couple 1—* Asset
    Couple 1—* Goal
    Couple 1—* ActivityLog
    User   1—* Asset       (owner; NULL owner == jointly owned)
"""
from datetime import datetime
from decimal import Decimal

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager

MAX_MEMBERS = 2  # a "couple" household


class Couple(db.Model):
    """A shared household joining two partners."""

    __tablename__ = "couples"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, default="우리집")
    invite_code = db.Column(db.String(16), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    members = db.relationship("User", back_populates="couple")
    categories = db.relationship(
        "Category",
        back_populates="couple",
        cascade="all, delete-orphan",
        order_by="Category.sort_order, Category.id",
    )
    assets = db.relationship(
        "Asset", back_populates="couple", cascade="all, delete-orphan"
    )
    goals = db.relationship(
        "Goal", back_populates="couple", cascade="all, delete-orphan"
    )
    activities = db.relationship(
        "ActivityLog",
        back_populates="couple",
        cascade="all, delete-orphan",
        order_by="ActivityLog.created_at.desc()",
    )

    @property
    def is_full(self) -> bool:
        return len(self.members) >= MAX_MEMBERS

    def partner_of(self, user):
        """Return the other member, or None if the user is solo so far."""
        for member in self.members:
            if member.id != user.id:
                return member
        return None


class User(UserMixin, db.Model):
    """An authenticated partner."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    couple_id = db.Column(db.Integer, db.ForeignKey("couples.id"), nullable=True)
    couple = db.relationship("Couple", back_populates="members")

    owned_assets = db.relationship("Asset", back_populates="owner")

    # --- password helpers -------------------------------------------------
    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    @property
    def has_couple(self) -> bool:
        return self.couple_id is not None


class Category(db.Model):
    """A fully user-editable asset category, scoped to one household.

    Each category carries its own presentation (icon/color), whether it is a
    liability, and which fixed report group it rolls up into (for trend charts).
    """

    __tablename__ = "categories"
    __table_args__ = (
        db.UniqueConstraint("couple_id", "name", name="uq_category_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    couple_id = db.Column(
        db.Integer, db.ForeignKey("couples.id"), nullable=False, index=True
    )
    name = db.Column(db.String(60), nullable=False)
    icon = db.Column(db.String(8), nullable=False, default="•")
    color = db.Column(db.String(9), nullable=False, default="#9DBE8A")
    is_liability = db.Column(db.Boolean, nullable=False, default=False)
    # One of REPORT_GROUP_KEYS (cash/investment/safe/personal), or NULL for debt.
    report_group = db.Column(db.String(20), nullable=True)
    # When true, assets in this category are real estate (excluded from the
    # "부동산 제외 순자산" figures on the dashboard and reports).
    is_real_estate = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    couple = db.relationship("Couple", back_populates="categories")
    assets = db.relationship("Asset", back_populates="category")

    @property
    def asset_count(self) -> int:
        return len(self.assets)


class Asset(db.Model):
    """An account that holds one or more holdings (cash and/or stocks).

    A simple cash account has a single cash holding; a brokerage account can mix
    cash (KRW/USD) and stock holdings (ticker + quantity). The account's value is
    the sum of its holdings, converted to the KRW base currency.
    """

    __tablename__ = "assets"

    id = db.Column(db.Integer, primary_key=True)
    couple_id = db.Column(
        db.Integer, db.ForeignKey("couples.id"), nullable=False, index=True
    )
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    category_id = db.Column(
        db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True
    )

    name = db.Column(db.String(120), nullable=False)
    institution = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.String(500), nullable=True)
    # When true, this account is omitted from all totals, charts, and snapshots.
    exclude_from_stats = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    couple = db.relationship("Couple", back_populates="assets")
    owner = db.relationship("User", back_populates="owned_assets")
    category = db.relationship("Category", back_populates="assets")
    holdings = db.relationship(
        "Holding",
        back_populates="asset",
        cascade="all, delete-orphan",
        order_by="Holding.sort_order, Holding.id",
    )

    @property
    def is_liability(self) -> bool:
        return bool(self.category and self.category.is_liability)

    @property
    def is_real_estate(self) -> bool:
        return bool(self.category and self.category.is_real_estate)

    @property
    def category_name(self) -> str:
        return self.category.name if self.category else "-"

    @property
    def owner_label(self) -> str:
        return self.owner.display_name if self.owner else "공동"

    def value_krw(self, rate) -> Decimal:
        """Total account value in KRW (sum of holdings at the given USD rate)."""
        return sum((h.value_krw(rate) for h in self.holdings), Decimal(0))

    def native_by_currency(self) -> dict:
        """{'KRW': Decimal, 'USD': Decimal} native value totals (no conversion)."""
        out = {}
        for h in self.holdings:
            out[h.currency] = out.get(h.currency, Decimal(0)) + h.value_native
        return out

    @property
    def currencies(self) -> list:
        """Distinct currencies present in this account, in stable order."""
        seen = []
        for h in self.holdings:
            if h.currency not in seen:
                seen.append(h.currency)
        return seen


class Holding(db.Model):
    """One line inside an account: cash in a currency, or a stock position.

    kind == 'cash'   → value = amount (in `currency`)
    kind == 'stock'  → value = quantity * cached_price (priced in `currency`)
    Stock prices are fetched from a free quote API and cached on the row so the
    app works offline and page loads never block on the network.
    """

    __tablename__ = "holdings"

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(
        db.Integer, db.ForeignKey("assets.id"), nullable=False, index=True
    )
    kind = db.Column(db.String(8), nullable=False, default="cash")
    currency = db.Column(db.String(3), nullable=False, default="KRW")

    # cash
    amount = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    label = db.Column(db.String(60), nullable=True)  # e.g. "예수금"

    # stock
    ticker = db.Column(db.String(24), nullable=True)
    quantity = db.Column(db.Numeric(18, 4), nullable=True)
    cached_price = db.Column(db.Numeric(18, 4), nullable=True)
    cached_price_at = db.Column(db.DateTime, nullable=True)

    sort_order = db.Column(db.Integer, nullable=False, default=0)

    asset = db.relationship("Asset", back_populates="holdings")

    @property
    def is_stock(self) -> bool:
        return self.kind == "stock"

    @property
    def value_native(self) -> Decimal:
        """Holding value in its own currency."""
        if self.kind == "stock":
            qty = self.quantity or Decimal(0)
            price = self.cached_price or Decimal(0)
            return Decimal(str(qty)) * Decimal(str(price))
        return Decimal(str(self.amount or 0))

    def value_krw(self, rate) -> Decimal:
        from .constants import CUR_USD

        native = self.value_native
        if self.currency == CUR_USD:
            return native * Decimal(str(rate))
        return native

    @property
    def display_name(self) -> str:
        if self.kind == "stock":
            return self.ticker or "종목"
        return self.label or "현금"

    @property
    def symbol(self) -> str:
        from .constants import currency_symbol

        return currency_symbol(self.currency)


class Goal(db.Model):
    """A shared savings goal."""

    __tablename__ = "goals"

    id = db.Column(db.Integer, primary_key=True)
    couple_id = db.Column(
        db.Integer, db.ForeignKey("couples.id"), nullable=False, index=True
    )

    name = db.Column(db.String(120), nullable=False)
    target_amount = db.Column(db.Numeric(16, 2), nullable=False, default=0)
    # Manual fallback amounts (used when no assets/categories are linked).
    saved_amount = db.Column(db.Numeric(16, 2), nullable=False, default=0)
    stocks_amount = db.Column(db.Numeric(16, 2), nullable=False, default=0)
    # JSON arrays of linked category ids and asset ids. When non-empty, current
    # progress is auto-computed from the live value of those assets/categories.
    linked_category_ids = db.Column(db.Text, nullable=False, default="[]")
    linked_asset_ids = db.Column(db.Text, nullable=False, default="[]")

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    couple = db.relationship("Couple", back_populates="goals")

    # --- link helpers -----------------------------------------------------
    @property
    def category_id_list(self) -> list:
        import json
        try:
            return [int(x) for x in json.loads(self.linked_category_ids or "[]")]
        except (ValueError, TypeError):
            return []

    @property
    def asset_id_list(self) -> list:
        import json
        try:
            return [int(x) for x in json.loads(self.linked_asset_ids or "[]")]
        except (ValueError, TypeError):
            return []

    @property
    def is_linked(self) -> bool:
        return bool(self.category_id_list or self.asset_id_list)

    @property
    def manual_amount(self) -> Decimal:
        """Manual fallback progress = cash saved + stocks held."""
        return (self.saved_amount or Decimal(0)) + (self.stocks_amount or Decimal(0))


class ActivityLog(db.Model):
    """An append-only feed of household activity."""

    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    couple_id = db.Column(
        db.Integer, db.ForeignKey("couples.id"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    action = db.Column(db.String(255), nullable=False)
    # Optional extra line, e.g. an amount change: "₩5,000,000 → ₩5,500,000".
    detail = db.Column(db.String(255), nullable=True)
    icon = db.Column(db.String(8), nullable=False, default="•")
    created_at = db.Column(
        db.DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    couple = db.relationship("Couple", back_populates="activities")
    actor = db.relationship("User")


class AssetSnapshot(db.Model):
    """A monthly point-in-time snapshot of a couple's finances.

    All monetary columns are stored in the KRW base currency (USD assets are
    converted at `rate_used`) so historical trends are directly comparable.
    Per-category and per-currency detail are kept as small JSON blobs to keep
    the schema stable as categories evolve, and to scale to many months cheaply
    (one compact row per couple per month).
    """

    __tablename__ = "asset_snapshots"
    __table_args__ = (
        db.UniqueConstraint("couple_id", "taken_on", name="uq_snapshot_month"),
    )

    id = db.Column(db.Integer, primary_key=True)
    couple_id = db.Column(
        db.Integer, db.ForeignKey("couples.id"), nullable=False, index=True
    )
    # First day of the month this snapshot represents.
    taken_on = db.Column(db.Date, nullable=False, index=True)

    net_worth_krw = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    total_assets_krw = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    total_liabilities_krw = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    # Real-estate value, and net worth with real estate excluded (req: 부동산 제외).
    real_estate_krw = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    net_worth_excl_re_krw = db.Column(db.Numeric(18, 2), nullable=False, default=0)

    # JSON: {category_name: krw}, {report_group: krw}, {currency: native}.
    category_totals = db.Column(db.Text, nullable=False, default="{}")
    group_totals = db.Column(db.Text, nullable=False, default="{}")
    currency_totals = db.Column(db.Text, nullable=False, default="{}")

    rate_used = db.Column(db.Numeric(12, 4), nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    couple = db.relationship("Couple")


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))
