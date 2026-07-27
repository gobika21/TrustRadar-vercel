import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app import cache, rate_limit, storage
from app.main import app


class AnalyzeEndpointTests(unittest.TestCase):
    def setUp(self):
        rate_limit._HITS.clear()
        cache._CACHE.clear()
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_patch = patch.object(storage, "DB_PATH", Path(self._tmp_dir.name) / "test.sqlite3")
        self._db_patch.start()
        self._verify_patch = patch("app.main.verify_live", new=AsyncMock(return_value=[]))
        self._verify_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self._verify_patch.stop()
        self._db_patch.stop()
        self._tmp_dir.cleanup()

    def test_vague_message_with_no_scam_signal_is_blocked_before_scoring(self):
        response = self.client.post(
            "/api/analyze", data={"text": "Hello, you are invited for an interview tomorrow"}
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("enough detail to review", response.json()["detail"])

    def test_valid_jd_passes_the_gate_and_returns_a_full_result(self):
        response = self.client.post(
            "/api/analyze",
            data={
                "text": (
                    "We are hiring a Product Designer at Lumen Studio. Standard interview process, "
                    "salary $90k-$110k, apply via the careers page."
                )
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("tier", body)
        self.assertIn("score", body)
        self.assertIn("pattern_findings", body)

    def test_weak_scam_signal_without_jd_detail_is_still_blocked(self):
        response = self.client.post(
            "/api/analyze",
            data={
                "text": (
                    "We're excited to offer you the role! As a welcome gift, you'll receive a "
                    "$100 gift card on your first day."
                )
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_strong_scam_signal_bypasses_the_jd_gate_and_is_scored(self):
        response = self.client.post(
            "/api/analyze",
            data={"text": "Please pay the training fee using a gift card to start work."},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertGreaterEqual(body["score"], 45)
        self.assertIn(body["tier_level"], {"high", "critical"})

    def test_instant_offer_with_no_process_bypasses_the_jd_gate_and_is_scored(self):
        response = self.client.post(
            "/api/analyze",
            data={
                "text": (
                    "Congrats, you got the job! Send a $100 gift card today to confirm your "
                    "start date."
                )
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        ids = {finding["id"] for finding in body["pattern_findings"]}
        self.assertIn("instant_offer_no_process", ids)
        self.assertNotEqual(body["tier"], "Lower risk")

    def test_vague_offer_with_company_and_salary_but_no_role_is_blocked(self):
        response = self.client.post(
            "/api/analyze",
            data={
                "text": (
                    "welcome, you got offer from trust radar company with salary of 2000 AED, "
                    "please join on Aug,2026"
                )
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        ids = {finding["id"] for finding in body["pattern_findings"]}
        self.assertIn("instant_offer_no_process", ids)
        self.assertNotEqual(body["tier"], "Lower risk")

    def test_url_only_submission_bypasses_the_jd_gate(self):
        response = self.client.post("/api/analyze", data={"job_url": "https://example.com/careers/12345"})
        self.assertEqual(response.status_code, 200)

    def test_history_round_trip_after_a_successful_analysis(self):
        analyze_response = self.client.post(
            "/api/analyze",
            data={
                "text": (
                    "We are hiring a Product Designer at Lumen Studio. Standard interview process, "
                    "salary $90k-$110k, apply via the careers page."
                )
            },
        )
        self.assertEqual(analyze_response.status_code, 200)

        history_response = self.client.get("/api/history")
        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(len(history_response.json()), 1)

        clear_response = self.client.delete("/api/history")
        self.assertEqual(clear_response.status_code, 200)
        self.assertEqual(self.client.get("/api/history").json(), [])


if __name__ == "__main__":
    unittest.main()
