import unittest
from unittest.mock import patch

from app import cache


class FakeRedis:
    """Minimal in-memory stand-in for the Upstash Redis client used by cache.py."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self.set_calls: list[tuple[str, int | None]] = []

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value
        self.set_calls.append((key, ex))


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.fake_redis = FakeRedis()
        self._patch = patch("app.cache.get_redis", return_value=self.fake_redis)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()

    def test_miss_then_hit(self):
        self.assertIsNone(cache.get_cached_verification("Some job text", []))
        cache.store_cached_verification("Some job text", [], ("findings", "evidence"))
        self.assertEqual(cache.get_cached_verification("Some job text", []), ("findings", "evidence"))

    def test_key_is_case_and_whitespace_insensitive(self):
        cache.store_cached_verification("  Some Job Text  ", ["https://Example.com"], "cached")
        self.assertEqual(cache.get_cached_verification("some job text", ["https://example.com"]), "cached")

    def test_different_urls_are_different_cache_entries(self):
        cache.store_cached_verification("same text", ["https://a.com"], "a")
        self.assertIsNone(cache.get_cached_verification("same text", ["https://b.com"]))

    def test_blank_text_is_never_cached(self):
        cache.store_cached_verification("   ", [], "value")
        self.assertIsNone(cache.get_cached_verification("   ", []))

    def test_store_sets_ttl_on_the_kv_entry(self):
        cache.store_cached_verification("Some job text", [], "value")
        self.assertEqual(self.fake_redis.set_calls, [(cache._cache_key("Some job text", []), cache.TTL_SECONDS)])

    def test_returns_none_when_kv_not_configured(self):
        with patch("app.cache.get_redis", return_value=None):
            cache.store_cached_verification("Some job text", [], "value")
            self.assertIsNone(cache.get_cached_verification("Some job text", []))


if __name__ == "__main__":
    unittest.main()
