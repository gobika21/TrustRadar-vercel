import unittest

from app import cache


class CacheTests(unittest.TestCase):
    def setUp(self):
        cache._CACHE.clear()

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

    def test_expired_entry_is_not_returned(self):
        cache.store_cached_verification("Some job text", [], "value")
        key = cache._cache_key("Some job text", [])
        cache._CACHE[key] = (0.0, "value")
        self.assertIsNone(cache.get_cached_verification("Some job text", []))


if __name__ == "__main__":
    unittest.main()
