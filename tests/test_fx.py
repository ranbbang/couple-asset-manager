"""Tests for app/services/fx.py.

Previously had zero coverage. Also the reason tests/conftest.py's `app`
fixture now redirects instance_path (see its comment) — this module's
_cache_path() resolves against current_app.instance_path, which without
that redirect is the real project's instance/ directory, shared with the
actually-running app.

fx._memory is a process-wide module global (by design, per its own
docstring — it's meant to survive across requests within one process), so
it's reset before each test here to avoid cross-test leakage.
"""
import json
import time
from unittest.mock import patch

import pytest

from app.services import fx


@pytest.fixture(autouse=True)
def _reset_memory_cache():
    fx._memory["rate"] = None
    fx._memory["fetched_at"] = 0.0
    yield
    fx._memory["rate"] = None
    fx._memory["fetched_at"] = 0.0


def _fake_response(payload: dict):
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    return _Resp()


def test_get_cached_rate_falls_back_to_config_default_when_nothing_cached(app):
    assert fx.get_cached_rate() == app.config["DEFAULT_USD_KRW"]


def test_get_cached_rate_prefers_memory_over_file(app):
    fx._memory["rate"] = 1234.5
    fx._memory["fetched_at"] = time.time()
    assert fx.get_cached_rate() == 1234.5


def test_get_cached_rate_reads_file_cache_when_memory_empty(app):
    fx._cache_path().write_text(
        json.dumps({"rate": 1111.1, "fetched_at": time.time()}), encoding="utf-8"
    )
    assert fx.get_cached_rate() == 1111.1
    # And it should now be promoted into memory too.
    assert fx._memory["rate"] == 1111.1


def test_fetch_live_rate_within_ttl_skips_network(app):
    fx._memory["rate"] = 1400.0
    fx._memory["fetched_at"] = time.time()  # fresh
    with patch("urllib.request.urlopen") as mock_urlopen:
        rate, source = fx.fetch_live_rate()
    mock_urlopen.assert_not_called()
    assert rate == 1400.0
    assert source == "cache"


def test_fetch_live_rate_fetches_and_caches_on_success(app):
    with patch("urllib.request.urlopen", return_value=_fake_response({"rates": {"KRW": 1500.25}})):
        rate, source = fx.fetch_live_rate()
    assert rate == 1500.25
    assert source == "live"
    assert fx._memory["rate"] == 1500.25
    # Persisted to THIS test's isolated instance path, not the real one.
    cached = json.loads(fx._cache_path().read_text(encoding="utf-8"))
    assert cached["rate"] == 1500.25


def test_fetch_live_rate_falls_back_on_network_error(app):
    with patch("urllib.request.urlopen", side_effect=OSError("network down")):
        rate, source = fx.fetch_live_rate()
    assert source == "fallback"
    assert rate == app.config["DEFAULT_USD_KRW"]  # nothing cached yet


def test_fetch_live_rate_falls_back_on_non_positive_rate(app):
    with patch("urllib.request.urlopen", return_value=_fake_response({"rates": {"KRW": 0}})):
        rate, source = fx.fetch_live_rate()
    assert source == "fallback"
    # A bad live value must never get promoted into the cache.
    assert fx._memory["rate"] is None


def test_fetch_live_rate_falls_back_to_last_known_on_error_after_ttl_expiry(app):
    fx._memory["rate"] = 1300.0
    fx._memory["fetched_at"] = time.time() - fx._TTL_SECONDS - 1  # expired
    with patch("urllib.request.urlopen", side_effect=OSError("network down")):
        rate, source = fx.fetch_live_rate()
    assert source == "fallback"
    assert rate == 1300.0  # stale cache beats the config default


def test_real_project_instance_dir_is_never_touched(app, tmp_path):
    """Regression guard for the instance_path fixture fix: run enough fx.py
    activity to definitely write a cache file, then confirm the real
    project's instance/fx_cache.json is untouched."""
    from pathlib import Path

    from app import config as app_config

    real_cache = app_config.BASE_DIR / "instance" / "fx_cache.json"
    before = real_cache.read_bytes() if real_cache.exists() else None

    with patch("urllib.request.urlopen", return_value=_fake_response({"rates": {"KRW": 9999.0}})):
        fx.fetch_live_rate()

    # The test app really did write ITS OWN cache file (proves the test
    # wasn't a no-op), just not the real project's.
    assert (Path(app.instance_path) / "fx_cache.json").exists()

    after = real_cache.read_bytes() if real_cache.exists() else None
    assert before == after
