import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app import rate_limit


def make_request(ip: str, forwarded_for: str | None = None) -> MagicMock:
    request = MagicMock()
    request.client.host = ip
    request.headers = {"x-forwarded-for": forwarded_for} if forwarded_for else {}
    return request


class FakeRedis:
    """Minimal in-memory stand-in for the Upstash Redis client used by rate_limit.py."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}
        self.expire_calls: list[tuple[str, int]] = []

    def incr(self, key: str) -> int:
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    def expire(self, key: str, seconds: int) -> None:
        self.expire_calls.append((key, seconds))


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        self.fake_redis = FakeRedis()
        self._patch = patch("app.rate_limit.get_redis", return_value=self.fake_redis)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()

    def test_allows_requests_under_the_limit(self):
        request = make_request("1.1.1.1")
        for _ in range(rate_limit.MAX_REQUESTS_PER_WINDOW):
            rate_limit.enforce_rate_limit(request)

    def test_blocks_requests_over_the_limit(self):
        request = make_request("2.2.2.2")
        for _ in range(rate_limit.MAX_REQUESTS_PER_WINDOW):
            rate_limit.enforce_rate_limit(request)
        with self.assertRaises(HTTPException) as ctx:
            rate_limit.enforce_rate_limit(request)
        self.assertEqual(ctx.exception.status_code, 429)

    def test_different_ips_have_independent_limits(self):
        request_a = make_request("3.3.3.3")
        request_b = make_request("4.4.4.4")
        for _ in range(rate_limit.MAX_REQUESTS_PER_WINDOW):
            rate_limit.enforce_rate_limit(request_a)
        rate_limit.enforce_rate_limit(request_b)

    def test_sets_expiry_on_first_hit_only(self):
        request = make_request("5.5.5.5")
        for _ in range(3):
            rate_limit.enforce_rate_limit(request)
        self.assertEqual(self.fake_redis.expire_calls, [("ratelimit:5.5.5.5", rate_limit.WINDOW_SECONDS)])

    def test_uses_x_forwarded_for_when_present(self):
        request = make_request("10.0.0.1", forwarded_for="9.9.9.9, 10.0.0.1")
        self.assertEqual(rate_limit._client_ip(request), "9.9.9.9")

    def test_fails_open_when_kv_not_configured(self):
        with patch("app.rate_limit.get_redis", return_value=None):
            request = make_request("6.6.6.6")
            for _ in range(rate_limit.MAX_REQUESTS_PER_WINDOW + 5):
                rate_limit.enforce_rate_limit(request)


if __name__ == "__main__":
    unittest.main()
