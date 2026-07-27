import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException

from app import rate_limit


def make_request(ip: str, forwarded_for: str | None = None) -> MagicMock:
    request = MagicMock()
    request.client.host = ip
    request.headers = {"x-forwarded-for": forwarded_for} if forwarded_for else {}
    return request


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        rate_limit._HITS.clear()

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

    def test_old_hits_outside_window_are_forgotten(self):
        request = make_request("5.5.5.5")
        for _ in range(rate_limit.MAX_REQUESTS_PER_WINDOW):
            rate_limit.enforce_rate_limit(request)
        rate_limit._HITS["5.5.5.5"] = [0.0] * rate_limit.MAX_REQUESTS_PER_WINDOW
        rate_limit.enforce_rate_limit(request)

    def test_uses_x_forwarded_for_when_present(self):
        request = make_request("10.0.0.1", forwarded_for="9.9.9.9, 10.0.0.1")
        self.assertEqual(rate_limit._client_ip(request), "9.9.9.9")


if __name__ == "__main__":
    unittest.main()
