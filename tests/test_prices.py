"""Tests for app/services/prices.py — zero coverage before this round.

prices._memory is a process-wide module global by design (same pattern as
fx.py), so it's reset before/after each test to avoid cross-test leakage.
The `app` fixture already redirects instance_path to a tmp_path
subdirectory (see conftest.py / Round 5), so the file cache here never
touches the real project's instance/price_cache.json — verified explicitly
in the last test below the same way Round 5 verified fx.py.
"""
import json
import time
from unittest.mock import patch

import pytest

from app.services import prices


@pytest.fixture(autouse=True)
def _reset_memory_cache():
    prices._memory.clear()
    yield
    prices._memory.clear()


def _fake_response(payload: dict):
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    return _Resp()


def _yahoo_payload(price, currency="USD"):
    return {"chart": {"result": [{"meta": {"regularMarketPrice": price, "currency": currency}}]}}


def test_fetch_quotes_live_success_caches_to_memory_and_file(app):
    with patch("urllib.request.urlopen", return_value=_fake_response(_yahoo_payload(150.5))):
        out = prices.fetch_quotes(["aapl"])  # lowercase in, uppercase out
    assert out == {"AAPL": {"price": 150.5, "currency": "USD", "source": "live"}}
    assert prices._memory["AAPL"]["price"] == 150.5
    cached = json.loads(prices._cache_path().read_text(encoding="utf-8"))
    assert cached["AAPL"]["price"] == 150.5


def test_fetch_quotes_within_ttl_skips_network(app):
    prices._memory["AAPL"] = {"price": 100.0, "currency": "USD", "at": time.time()}
    with patch("urllib.request.urlopen") as mock_urlopen:
        out = prices.fetch_quotes(["AAPL"])
    mock_urlopen.assert_not_called()
    assert out["AAPL"]["source"] == "cache"
    assert out["AAPL"]["price"] == 100.0


def test_fetch_quotes_falls_back_to_file_cache_on_network_error(app):
    prices._cache_path().write_text(
        json.dumps({"AAPL": {"price": 99.0, "currency": "USD", "at": 0}}), encoding="utf-8"
    )
    with patch("urllib.request.urlopen", side_effect=OSError("network down")):
        out = prices.fetch_quotes(["AAPL"])
    assert out["AAPL"] == {"price": 99.0, "currency": "USD", "source": "fallback"}


def test_fetch_quotes_omits_ticker_with_no_cache_and_failed_fetch(app):
    with patch("urllib.request.urlopen", side_effect=OSError("network down")):
        out = prices.fetch_quotes(["UNKNOWNTICKER"])
    assert out == {}


def test_fetch_quotes_skips_blank_tickers(app):
    with patch("urllib.request.urlopen") as mock_urlopen:
        out = prices.fetch_quotes(["", "  ", None])
    mock_urlopen.assert_not_called()
    assert out == {}


def test_fetch_quotes_failed_ticker_keeps_last_known_price_in_file_cache(app):
    """Documented behavior (see the comment above the file-cache write in
    prices.py): a ticker that fails THIS round must not be wiped from the
    persisted file cache — it should keep its previous last-known price so
    a later offline-fallback lookup still finds it."""
    prices._cache_path().write_text(
        json.dumps({"OLDTICKER": {"price": 42.0, "currency": "USD", "at": 0}}),
        encoding="utf-8",
    )

    def fake_urlopen(req, timeout=None):
        # NEWTICKER succeeds; OLDTICKER isn't even requested this round.
        return _fake_response(_yahoo_payload(10.0))

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        prices.fetch_quotes(["NEWTICKER"])

    cached = json.loads(prices._cache_path().read_text(encoding="utf-8"))
    assert cached["NEWTICKER"]["price"] == 10.0
    assert cached["OLDTICKER"]["price"] == 42.0  # untouched, not wiped


def test_refresh_holdings_updates_only_matched_stock_holdings():
    class FakeHolding:
        def __init__(self, kind, ticker=None):
            self.kind = kind
            self.ticker = ticker
            self.cached_price = None
            self.currency = "USD"
            self.cached_price_at = None

    stock_ok = FakeHolding("stock", "AAPL")
    stock_unquotable = FakeHolding("stock", "NOPRICE")
    cash = FakeHolding("cash")
    no_ticker_stock = FakeHolding("stock", ticker=None)

    with patch.object(
        prices, "fetch_quotes",
        return_value={"AAPL": {"price": 200.0, "currency": "KRW", "source": "live"}},
    ):
        updated = prices.refresh_holdings([stock_ok, stock_unquotable, cash, no_ticker_stock])

    assert updated == 1
    assert stock_ok.cached_price == 200.0
    assert stock_ok.currency == "KRW"  # synced from the quote
    assert stock_ok.cached_price_at is not None

    assert stock_unquotable.cached_price is None  # no quote available, untouched
    assert cash.cached_price is None  # never considered (kind != stock)


def test_refresh_holdings_ignores_unsupported_quote_currency():
    """Documents current behavior rather than asserting it's ideal: Yahoo
    can return a currency outside {KRW, USD} (the app's only two supported
    currencies) for a foreign-listed ticker. The price is still applied,
    but the holding's currency label is left as whatever it already was —
    worth revisiting if a stock's home exchange currency ever matters."""
    class FakeHolding:
        kind = "stock"
        ticker = "LSE.L"
        cached_price = None
        currency = "USD"
        cached_price_at = None

    h = FakeHolding()
    with patch.object(
        prices, "fetch_quotes",
        return_value={"LSE.L": {"price": 500.0, "currency": "GBP", "source": "live"}},
    ):
        prices.refresh_holdings([h])
    assert h.cached_price == 500.0
    assert h.currency == "USD"  # unchanged — GBP isn't a supported currency


def test_real_project_instance_dir_is_never_touched(app):
    from pathlib import Path

    from app import config as app_config

    real_cache = app_config.BASE_DIR / "instance" / "price_cache.json"
    before = real_cache.read_bytes() if real_cache.exists() else None

    with patch("urllib.request.urlopen", return_value=_fake_response(_yahoo_payload(1.0))):
        prices.fetch_quotes(["ZZZZ"])

    assert (Path(app.instance_path) / "price_cache.json").exists()
    after = real_cache.read_bytes() if real_cache.exists() else None
    assert before == after
