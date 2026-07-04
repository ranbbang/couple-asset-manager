"""USD->KRW exchange-rate service.

Fetches the live rate from a free, no-key public API (open.er-api.com) and
caches it. The cache is twofold:
  * in-process memory (fast path, valid for `_TTL` seconds)
  * a small JSON file under the Flask instance folder (survives restarts and
    provides the offline fallback)

If every source fails, we fall back to `DEFAULT_USD_KRW` from config. No paid
APIs are used and the app remains fully functional offline.
"""
import json
import time
import urllib.request
from pathlib import Path

from flask import current_app

UPSTREAM_URL = "https://open.er-api.com/v6/latest/USD"
_TTL_SECONDS = 60 * 60  # refresh the live rate at most once per hour

# Process-wide memory cache: {"rate": float, "fetched_at": epoch_seconds}.
_memory = {"rate": None, "fetched_at": 0.0}


def _cache_path() -> Path:
    inst = Path(current_app.instance_path)
    inst.mkdir(parents=True, exist_ok=True)
    return inst / "fx_cache.json"


def _default_rate() -> float:
    return float(current_app.config.get("DEFAULT_USD_KRW", 1350.0))


def _read_file_cache():
    try:
        data = json.loads(_cache_path().read_text(encoding="utf-8"))
        return float(data["rate"]), float(data.get("fetched_at", 0.0))
    except Exception:
        return None, 0.0


def _write_file_cache(rate: float, fetched_at: float) -> None:
    try:
        _cache_path().write_text(
            json.dumps({"rate": rate, "fetched_at": fetched_at}), encoding="utf-8"
        )
    except Exception:
        pass  # cache write is best-effort


def get_cached_rate() -> float:
    """Return the best rate we already know, WITHOUT any network call.

    Used for server-side rendering (dashboard, snapshots) so page loads never
    block on the network. Order: memory -> file -> config default.
    """
    if _memory["rate"]:
        return _memory["rate"]
    rate, fetched_at = _read_file_cache()
    if rate:
        _memory["rate"] = rate
        _memory["fetched_at"] = fetched_at
        return rate
    return _default_rate()


def fetch_live_rate(timeout: float = 4.0):
    """Return (rate, source) where source is 'live' | 'cache' | 'fallback'.

    Honours the TTL: if the memory cache is fresh, returns it without a request.
    On network failure, returns the last cached value (or config default).
    """
    now = time.time()
    if _memory["rate"] and (now - _memory["fetched_at"]) < _TTL_SECONDS:
        return _memory["rate"], "cache"

    try:
        req = urllib.request.Request(UPSTREAM_URL, headers={"User-Agent": "asset-app"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        rate = float(payload["rates"]["KRW"])
        if rate <= 0:
            raise ValueError("non-positive rate")
        _memory["rate"] = rate
        _memory["fetched_at"] = now
        _write_file_cache(rate, now)
        return rate, "live"
    except Exception:
        return get_cached_rate(), "fallback"
