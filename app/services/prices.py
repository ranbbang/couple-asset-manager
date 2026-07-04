"""Stock quote service — fetches current prices from Yahoo Finance (free, no key).

Mirrors the FX service design: live fetch with an in-memory + on-disk cache and
a graceful offline fallback to the last known price. Page loads never block on
the network — they read whatever price is already cached on the Holding row;
the live fetch happens only when the user hits "가격 새로고침" (or on demand).

Tickers follow Yahoo conventions:
    AAPL          US stock
    005930.KS     KOSPI (삼성전자)
    035720.KQ     KOSDAQ
    BTC-USD       crypto
"""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from flask import current_app

# Yahoo's chart endpoint is the most reliable keyless source for a single quote.
CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
_TTL_SECONDS = 60 * 10  # don't re-hit Yahoo for the same ticker within 10 min

# Process-wide memory cache: {ticker: {"price": float, "currency": str, "at": epoch}}
_memory: dict = {}


def _cache_path() -> Path:
    inst = Path(current_app.instance_path)
    inst.mkdir(parents=True, exist_ok=True)
    return inst / "price_cache.json"


def _read_file_cache() -> dict:
    try:
        return json.loads(_cache_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_file_cache(data: dict) -> None:
    try:
        _cache_path().write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass  # best-effort


def _fetch_one(ticker: str, timeout: float = 5.0):
    """Return (price, currency) from Yahoo, or (None, None) on failure."""
    url = CHART_URL.format(ticker=urllib.parse.quote(ticker))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 asset-app"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    result = payload["chart"]["result"][0]
    meta = result["meta"]
    price = meta.get("regularMarketPrice")
    currency = meta.get("currency", "USD")
    if price is None:
        raise ValueError("no price in response")
    return float(price), str(currency)


def fetch_quotes(tickers, timeout: float = 5.0) -> dict:
    """Fetch quotes for a list of tickers, using cache where fresh.

    Returns {ticker_upper: {"price": float, "currency": str, "source": str}}.
    `source` is 'live' | 'cache' | 'fallback'. Never raises — failures fall back
    to the last cached value (memory → file), so the app keeps working offline.
    """
    now = time.time()
    file_cache = None
    out = {}
    for raw in tickers:
        ticker = (raw or "").strip().upper()
        if not ticker:
            continue

        mem = _memory.get(ticker)
        if mem and (now - mem["at"]) < _TTL_SECONDS:
            out[ticker] = {"price": mem["price"], "currency": mem["currency"], "source": "cache"}
            continue

        try:
            price, currency = _fetch_one(ticker, timeout=timeout)
            _memory[ticker] = {"price": price, "currency": currency, "at": now}
            out[ticker] = {"price": price, "currency": currency, "source": "live"}
        except Exception:
            # Fall back to file cache (then memory) for a last-known price.
            if file_cache is None:
                file_cache = _read_file_cache()
            cached = file_cache.get(ticker) or _memory.get(ticker)
            if cached:
                out[ticker] = {"price": cached["price"], "currency": cached["currency"], "source": "fallback"}

    # Persist the freshest memory cache for offline restarts.
    if out:
        snapshot = {t: {"price": v["price"], "currency": v["currency"], "at": _memory.get(t, {}).get("at", now)}
                    for t, v in _memory.items()}
        _write_file_cache(snapshot)
    return out


def refresh_holdings(holdings, timeout: float = 5.0) -> int:
    """Update cached_price/cached_price_at on a list of stock Holdings.

    Returns the number of holdings whose price was updated. Caller commits.
    """
    from datetime import datetime
    from decimal import Decimal

    stock_holdings = [h for h in holdings if h.kind == "stock" and h.ticker]
    tickers = {h.ticker.strip().upper() for h in stock_holdings}
    quotes = fetch_quotes(tickers, timeout=timeout)

    updated = 0
    now = datetime.utcnow()
    for h in stock_holdings:
        q = quotes.get(h.ticker.strip().upper())
        if not q:
            continue
        h.cached_price = Decimal(str(q["price"]))
        # Keep the holding's stored currency in sync with the quote currency.
        if q.get("currency") in ("KRW", "USD"):
            h.currency = q["currency"]
        h.cached_price_at = now
        updated += 1
    return updated
