import unittest
import tempfile
from pathlib import Path

from app.analysis import assert_job_url_accessible, build_recommendation, evidence_to_payload
from app.metrics import build_usage_snapshot
from app.models import Evidence
from app.scoring import evidence_score, pattern_check, score_to_tier
from app.text_utils import domain_from_url, extract_urls, looks_like_job_content, looks_like_valid_jd
from app.uploads import decode_text_upload
from app.verification import build_search_query, rdap_lookup, search_result_severity


ALMUMTAJ_MESSAGE = """Hello Gobika Sekar,

Thank you for your message and for sharing your information with us.

We would like to arrange a short online discussion to better understand your background and availability.

Discussion Schedule
Date: 01 JULY
Time: Between 10:00 AM and 4:00 PM (UAE Time)
Mode: Online

Interview information is available at:
https://www.almumtajllc.com/

Once we receive your availability, we will share the meeting timing with you.

Thank you for your time and cooperation.

Regards,
Coordination Team
"""


class TrustRadarScoringTests(unittest.TestCase):
    def test_vague_interview_invite_gets_pattern_score(self):
        score, findings = pattern_check(ALMUMTAJ_MESSAGE)
        ids = {finding["id"] for finding in findings}

        self.assertIn("website_instead_of_meeting_link", ids)
        self.assertIn("date_missing_year", ids)
        self.assertIn("missing_role", ids)
        self.assertIn("generic_signature", ids)
        self.assertGreaterEqual(score, 40)

    def test_vague_interview_message_with_no_details_needs_verification(self):
        score, findings = pattern_check("Hello, you are invited for an interview tomorrow")
        ids = {finding["id"] for finding in findings}

        self.assertIn("missing_role", ids)
        self.assertIn("insufficient_verifiable_detail", ids)
        tier, tier_level = score_to_tier(score)
        self.assertEqual(tier_level, "medium")

    def test_detailed_short_post_does_not_trigger_insufficient_detail(self):
        score, findings = pattern_check(
            "We are hiring a Product Designer at Lumen Studio, standard interview process, "
            "salary $90k-$110k, apply via careers page."
        )
        ids = {finding["id"] for finding in findings}

        self.assertNotIn("insufficient_verifiable_detail", ids)

    def test_negated_upfront_fee_is_not_flagged(self):
        score, findings = pattern_check(
            "We are pleased to offer you a position. Please note this role requires no upfront payment."
        )
        ids = {finding["id"] for finding in findings}

        self.assertNotIn("upfront_fee", ids)

    def test_unnegated_upfront_fee_is_still_flagged(self):
        score, findings = pattern_check(
            "To secure your position, please pay a $150 registration fee for training materials."
        )
        ids = {finding["id"] for finding in findings}

        self.assertIn("upfront_fee", ids)

    def test_refundable_deposit_via_gift_card_is_caught_without_llm(self):
        score, findings = pattern_check(
            "Congratulations! You have been selected for a Data Entry position. To finalize your "
            "onboarding, kindly send a refundable deposit of $200 via gift card to secure your "
            "laptop shipment. Reply within 2 hours or the offer expires."
        )
        ids = {finding["id"] for finding in findings}

        self.assertIn("upfront_fee", ids)
        self.assertIn("gift_card_payment", ids)
        self.assertIn("urgency", ids)
        self.assertGreaterEqual(score, 50)

    def test_gift_card_signing_bonus_is_not_critical_but_still_surfaced(self):
        score, findings = pattern_check(
            "We're excited to offer you the role! As a welcome gift, you'll receive a $100 gift "
            "card on your first day."
        )
        ids = {finding["id"] for finding in findings}

        self.assertNotIn("gift_card_payment", ids)
        self.assertIn("gift_card_mentioned", ids)
        self.assertLess(score, 24)

    def test_looks_like_job_content_rejects_unrelated_text(self):
        self.assertFalse(looks_like_job_content("Rate limit test message for verification purposes only, unique marker xyz123."))
        self.assertFalse(looks_like_job_content("The weather today is sunny with a light breeze."))

    def test_looks_like_job_content_accepts_job_keywords(self):
        self.assertTrue(looks_like_job_content("We are hiring a Product Designer for a full-time role."))
        self.assertTrue(looks_like_job_content(ALMUMTAJ_MESSAGE))

    def test_looks_like_job_content_accepts_email_or_url_even_without_keywords(self):
        self.assertTrue(looks_like_job_content("Reach me at scammer@example.com for more."))
        self.assertTrue(looks_like_job_content("See https://example.com/offer for details."))

    def test_looks_like_job_content_rejects_generic_role_or_offer_mentions(self):
        self.assertFalse(
            looks_like_job_content(
                "We're excited to offer you the role! As a welcome gift, you'll receive a "
                "$100 gift card on your first day."
            )
        )

    def test_looks_like_valid_jd_rejects_vague_interview_notice(self):
        self.assertFalse(looks_like_valid_jd("Hello, you are invited for an interview tomorrow"))

    def test_looks_like_valid_jd_rejects_generic_role_offer_with_gift_card(self):
        self.assertFalse(
            looks_like_valid_jd(
                "We're excited to offer you the role! As a welcome gift, you'll receive a "
                "$100 gift card on your first day."
            )
        )

    def test_looks_like_valid_jd_accepts_role_and_salary_detail(self):
        self.assertTrue(
            looks_like_valid_jd(
                "We are hiring a Product Designer at Lumen Studio. Standard interview process, "
                "salary $90k-$110k, apply via the careers page."
            )
        )

    def test_looks_like_valid_jd_accepts_email_or_url(self):
        self.assertTrue(looks_like_valid_jd("Reach me at scammer@example.com for more."))
        self.assertTrue(looks_like_valid_jd("See https://example.com/offer for details."))

    def test_targeted_scam_search_result_is_high_severity(self):
        detail = (
            "Top results: Mumtaj Co. Job Scam Alert: Be Cautious of Fake Job Offers "
            "(https://www.linkedin.com/posts/example) | almumtajllc.com Reviews: "
            "Is this site a scam or legit? (https://www.scam-detector.com/validator/almumtajllc-com-review/)"
        )

        self.assertEqual(search_result_severity("almumtajllc.com company recruitment scam", detail), "high")

    def test_almumtaj_case_no_longer_scores_lower_risk(self):
        pattern_score, _ = pattern_check(ALMUMTAJ_MESSAGE)
        live_score = evidence_score(
            [
                Evidence(
                    "URL reachability",
                    "checked",
                    "HTTP 200 from almumtajllc.com; title: Gulf Jobs 2026 - Dubai & Qatar Jobs, Salary, Visa Guide",
                    "https://www.almumtajllc.com/",
                    "medium",
                ),
                Evidence(
                    "Web search",
                    "found",
                    "Top results: Mumtaj Co. Job Scam Alert: Be Cautious of Fake Job Offers",
                    "almumtajllc.com company recruitment scam",
                    "high",
                ),
            ]
        )

        tier, tier_level = score_to_tier(pattern_score + live_score)
        self.assertIn(tier_level, {"high", "critical"})
        self.assertIn(tier, {"High risk", "Likely scam"})

    def test_micro1_warning_search_results_raise_risk(self):
        detail = (
            "Top results: Beware of micro1: a job scam using AI - LinkedIn "
            "(https://www.linkedin.com/posts/example) | The Micro1 Deception: "
            "Inside the AI Recruitment Trap (https://example.com/micro1) | "
            "Micro1 - Dangerous scam - personal data theft warning "
            "(https://www.glassdoor.com/Reviews/example)"
        )

        self.assertEqual(search_result_severity("micro1.ai company recruitment scam", detail), "high")

        tier, tier_level = score_to_tier(
            evidence_score(
                [
                    Evidence("Domain registration", "not_found", "No parseable RDAP record found.", "micro1.ai", "high"),
                    Evidence("Web search", "found", detail, "micro1.ai company recruitment scam", "high"),
                ]
            )
        )
        self.assertEqual(tier_level, "high")
        self.assertEqual(tier, "High risk")

    def test_ats_hosted_jobs_search_by_employer_not_platform(self):
        query = build_search_query(
            "",
            ["https://jobs.lever.co/decilegroup/7d7b7ea2-765a-4604-85f0-8d7df7da1b74"],
            [],
        )

        self.assertEqual(query, "decilegroup company recruitment scam")

    def test_workday_jobs_search_by_tenant_employer(self):
        query = build_search_query(
            "",
            [
                "https://riministreet.wd1.myworkdayjobs.com/RiminiStreet/job/Dubai-UAE/Forward-Deployed-Engineer--Agentic-AI-_R-102256"
            ],
            [],
        )

        self.assertEqual(query, "riministreet company recruitment scam")

    def test_generic_reputation_pages_are_not_high_without_scam_claims(self):
        detail = (
            "Top results: lever.co Reviews: Is this site a scam or legit? - Scam Detector "
            "| Lever Reviews | Read Customer Service Reviews of lever.co"
        )

        self.assertEqual(search_result_severity("lever.co company recruitment scam", detail), "medium")

    def test_company_name_query_can_match_warning_results(self):
        detail = "Top results: Avetta - Warning! Avoid this company at all cost they are a scam!"

        self.assertEqual(search_result_severity("avetta company recruitment scam", detail), "high")

    def test_about_company_heading_builds_clean_search_query(self):
        query = build_search_query("About Rimini Street, Inc.\n\nWe are actively seeking an engineer.", [], [])

        self.assertEqual(query, "Rimini Street recruitment scam")

    def test_text_uploads_can_be_decoded_for_analysis(self):
        self.assertIn("Rimini Street", decode_text_upload("About Rimini Street, Inc.".encode("utf-8")))

    def test_markdown_link_text_does_not_create_invalid_url(self):
        urls = extract_urls("[http://www.riministreet.com](http://www.riministreet.com/)")

        self.assertIn("http://www.riministreet.com", urls)
        self.assertIn("http://www.riministreet.com/", urls)
        self.assertNotIn("http://www.riministreet.com](http://www.riministreet.com/", urls)
        self.assertIsNone(domain_from_url("http://www.riministreet.com](http://www.riministreet.com/"))

    def test_dead_posting_link_needs_verification(self):
        tier, tier_level = score_to_tier(
            evidence_score(
                [
                    Evidence("URL reachability", "checked", "HTTP 404 from jobs.lever.co", "https://jobs.lever.co/example", "medium"),
                ]
            )
        )

        self.assertEqual(tier_level, "low")
        self.assertEqual(tier, "Lower risk")

    def test_generic_search_warning_still_flags_as_medium(self):
        detail = (
            "Top results: info.riministreet.com Reviews | scam, legit or safe check | Scamadviser "
            "(https://www.scamadviser.com/check-website/info.riministreet.com) | "
            "Scammers impersonate well-known companies, recruit for fake jobs on LinkedIn "
            "(https://consumer.ftc.gov/example)"
        )

        self.assertEqual(search_result_severity("riministreet.com company recruitment scam", detail), "medium")

    def test_search_results_with_no_scam_language_are_info(self):
        detail = "Top results: Rimini Street | Official careers page (https://www.riministreet.com/careers)"

        self.assertEqual(search_result_severity("riministreet.com company recruitment scam", detail), "info")

    def test_generic_scam_warning_search_result_leaves_lower_risk_tier(self):
        tier, tier_level = score_to_tier(
            evidence_score(
                [
                    Evidence(
                        "Web search",
                        "found",
                        "Top results: Scammers impersonate well-known companies, recruit for fake jobs on LinkedIn",
                        "lumen studio company recruitment scam",
                        "medium",
                    ),
                ]
            )
        )

        self.assertNotEqual(tier, "Lower risk")
        self.assertIn(tier_level, {"medium", "high", "critical"})

    def test_failed_live_checks_do_not_create_scam_score(self):
        tier, tier_level = score_to_tier(
            evidence_score(
                [
                    Evidence("URL reachability", "failed", "Could not fetch URL: ConnectTimeout", "https://example.com", "medium"),
                    Evidence("Domain registration", "failed", "RDAP lookup failed: ConnectTimeout", "example.com", "medium"),
                    Evidence("Web search", "failed", "Search failed: ConnectTimeout", "example company recruitment scam", "medium"),
                ]
            )
        )

        self.assertEqual(tier_level, "low")
        self.assertEqual(tier, "Lower risk")

    def test_inaccessible_submitted_job_url_raises_access_error(self):
        with self.assertRaisesRegex(Exception, "could not access the job posting URL"):
            assert_job_url_accessible(
                "https://example.com/private-job",
                [
                    Evidence(
                        "URL reachability",
                        "failed",
                        "Could not fetch URL: ReadTimeout",
                        "https://example.com/private-job",
                        "medium",
                    )
                ],
            )

    def test_blocked_submitted_job_url_raises_access_error(self):
        with self.assertRaisesRegex(Exception, "could not access the job posting URL"):
            assert_job_url_accessible(
                "https://example.com/private-job",
                [
                    Evidence(
                        "URL reachability",
                        "blocked",
                        "HTTP 403 from example.com; page appears blocked or requires browser verification",
                        "https://example.com/private-job",
                        "medium",
                    )
                ],
            )

    def test_accessible_submitted_job_url_does_not_raise_access_error(self):
        assert_job_url_accessible(
            "https://www.d4insight.com/jobopening/full-stack-developer-awa-platform/",
            [
                Evidence(
                    "URL reachability",
                    "checked",
                    "HTTP 200 from d4insight.com",
                    "https://www.d4insight.com/jobopening/full-stack-developer-awa-platform/",
                    "info",
                )
            ],
        )

    def test_recommendation_labels_are_action_oriented(self):
        self.assertEqual(build_recommendation("low")["label"], "Likely safe to apply")
        self.assertEqual(build_recommendation("medium")["label"], "Apply with caution")
        self.assertEqual(build_recommendation("high")["label"], "Do not engage yet")
        self.assertEqual(build_recommendation("critical")["label"], "Don't apply to this")

    def test_evidence_payload_extracts_source_links(self):
        payload = evidence_to_payload(
            Evidence(
                "Web search",
                "found",
                "Top results: Warning post (https://example.com/warning) | Review page (https://example.com/review)",
                "example company recruitment scam",
                "high",
            )
        )

        self.assertEqual(payload["links"][0]["url"], "https://example.com/warning")
        self.assertEqual(payload["links"][1]["url"], "https://example.com/review")

    def test_usage_snapshot_reports_request_deltas(self):
        from app import metrics

        before = metrics.METRICS.copy()
        metrics.METRICS["url_fetches"] += 2
        metrics.METRICS["dns_lookups"] += 1
        usage = build_usage_snapshot(before)

        self.assertEqual(usage["url_fetches"], 2)
        self.assertEqual(usage["dns_lookups"], 1)

    def test_sqlite_history_round_trip(self):
        from app import storage

        with tempfile.TemporaryDirectory() as tmpdir:
            original_data_dir = storage.DATA_DIR
            original_db_path = storage.DB_PATH
            storage.DATA_DIR = Path(tmpdir)
            storage.DB_PATH = storage.DATA_DIR / "history.sqlite3"
            try:
                storage.save_analysis(
                    {
                        "id": "entry-1",
                        "createdAt": "2026-07-25T08:00:00+00:00",
                        "label": "example.com",
                        "input": {"text": "", "linkUrl": "https://example.com", "files": []},
                        "result": {"score": 0, "tier": "Lower risk", "tier_level": "low"},
                    }
                )

                entries = storage.list_analyses()
                self.assertEqual(entries[0]["id"], "entry-1")
                self.assertEqual(storage.get_analysis("entry-1")["label"], "example.com")

                storage.clear_analyses()
                self.assertEqual(storage.list_analyses(), [])
            finally:
                storage.DATA_DIR = original_data_dir
                storage.DB_PATH = original_db_path


if __name__ == "__main__":
    unittest.main()
