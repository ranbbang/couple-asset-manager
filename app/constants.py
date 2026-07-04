"""Domain constants — currencies, report groups, and default categories.

Categories are now stored per-couple in the `categories` table (fully editable:
add / remove / reorder / rename / recolor / set liability + report group). The
values here are only the DEFAULTS used to seed a new household and the fixed set
of analytical report groups that categories roll up into.
"""

# --- Currencies -----------------------------------------------------------
CUR_KRW = "KRW"
CUR_USD = "USD"
CURRENCIES = [CUR_KRW, CUR_USD]

CURRENCY_SYMBOL = {CUR_KRW: "₩", CUR_USD: "$"}
CURRENCY_LABEL = {CUR_KRW: "₩ 원 (KRW)", CUR_USD: "$ 달러 (USD)"}


def currency_symbol(currency: str) -> str:
    return CURRENCY_SYMBOL.get(currency, "")


# --- Report groups (fixed analytical buckets) -----------------------------
# Every asset category maps to ONE of these (liabilities map to none). They
# drive the Asset Reports trend charts and stay stable as categories change.
REPORT_GROUPS = {
    "cash":       {"label": "현금성 자산",      "color": "#9DBE8A"},
    "investment": {"label": "투자 자산",        "color": "#A99BD6"},
    "safe":       {"label": "노후·안전 자산",   "color": "#C8B66E"},
    "personal":   {"label": "개인 자산",        "color": "#D8A86A"},
}
REPORT_GROUP_KEYS = list(REPORT_GROUPS)


def report_group_label(key: str) -> str:
    meta = REPORT_GROUPS.get(key)
    return meta["label"] if meta else "-"


# --- Default categories (seed a new household) ----------------------------
# name, icon, color, is_liability, report_group, is_real_estate, sort_order
DEFAULT_CATEGORIES = [
    {"name": "현금", "icon": "💵", "color": "#9DBE8A",
     "is_liability": False, "report_group": "cash", "is_real_estate": False, "sort_order": 0},
    {"name": "현금성 투자자산", "icon": "💰", "color": "#7FA9B8",
     "is_liability": False, "report_group": "cash", "is_real_estate": False, "sort_order": 1},
    {"name": "중위험 투자자산", "icon": "📊", "color": "#A99BD6",
     "is_liability": False, "report_group": "investment", "is_real_estate": False, "sort_order": 2},
    {"name": "고위험 투자자산", "icon": "🚀", "color": "#E0997F",
     "is_liability": False, "report_group": "investment", "is_real_estate": False, "sort_order": 3},
    {"name": "노후·안전자산 (연금 등)", "icon": "🏛️", "color": "#C8B66E",
     "is_liability": False, "report_group": "safe", "is_real_estate": False, "sort_order": 4},
    {"name": "부동산", "icon": "🏡", "color": "#B8956A",
     "is_liability": False, "report_group": "safe", "is_real_estate": True, "sort_order": 5},
    {"name": "개인자산 (용돈·개인지출)", "icon": "🪙", "color": "#D8A86A",
     "is_liability": False, "report_group": "personal", "is_real_estate": False, "sort_order": 6},
    {"name": "빚", "icon": "💳", "color": "#D98C77",
     "is_liability": True, "report_group": None, "is_real_estate": False, "sort_order": 7},
]

# Holding kinds (a stock account can hold cash + tickers together).
HOLDING_CASH = "cash"
HOLDING_STOCK = "stock"

# Fallback presentation when a category is missing (defensive template use).
DEFAULT_META = {"icon": "•", "color": "#9aa0b4"}
