import unittest
from datetime import date, timedelta
from copy import deepcopy

from pre_vc import assess
from student_watchlist import refresh

TODAY = date(2026, 11, 20)
URL = "https://example.org/team"


class PresentationTests(unittest.TestCase):
    def setUp(self):
        self.row = {"id": "test", "source_url": URL}
        self.review = {"identity_url": URL,
            "stage": {"kind": "first_pilot", "date": "2026-09-20", "summary": "First trial", "url": URL},
            "declaration": {"kind": "no_prior_vc", "issuer": "founder", "date": "2026-11-01",
                            "summary": "Founder explicitly disclosed no prior VC.", "url": URL},
            "cross_check": {"kind": "no_public_vc_found", "independent": True, "date": "2026-11-19",
                            "summary": "Scoped investment check", "url": "https://independent.example/project"}}

    def run_gate(self, **row):
        return assess(self.row | row, {"test": self.review}, TODAY)

    def test_positive_case_with_grant_and_all_three_sources(self):
        out = self.run_gate(funding={"public_support": ["grant"]})
        self.assertEqual(out["status"], "present")
        self.assertEqual(set(out["evidence"]), {"stage", "declaration", "cross_check"})

    def test_negative_search_alone_is_research(self):
        del self.review["declaration"]
        self.assertEqual(self.run_gate(funding={"status": "no_funding_found"})["status"], "watch")

    def test_known_financing_overrides_otherwise_positive_record(self):
        for record in ({"funding": {"status": "funded"}}, {"funding": {"rounds": [{"source_url": URL}]}},
                       {"shortlist_exclusions": ["funded_or_later_stage"]}, {"formation_date": "2021-01-01"}):
            self.assertEqual(self.run_gate(**record)["status"], "excluded")
        self.assertEqual(self.run_gate(funding={"reviews": [{"reported_as": "pre_seed_financing_reported"}]})["status"], "watch")
        self.review["cross_check"]["kind"] = "prior_vc"
        self.assertEqual(self.run_gate()["status"], "excluded")

    def test_stale_future_missing_or_unrelated_evidence(self):
        good = deepcopy(self.review)
        for field, change in (("stage", {"date": str(TODAY - timedelta(days=181))}),
                              ("declaration", {"date": str(TODAY - timedelta(days=91))}),
                              ("cross_check", {"date": str(TODAY - timedelta(days=31))}),
                              ("stage", {"kind": "award"}), ("stage", {"date": "2027-01-01"}),
                              ("declaration", {"issuer": "blog"}), ("cross_check", {"independent": False}),
                              ("cross_check", {"date": "2026-10-31"}), ("cross_check", {"url": URL})):
            self.review = deepcopy(good)
            self.review[field].update(change)
            self.assertEqual(self.run_gate()["status"], "watch", (field, change))
        self.review = good
        self.assertEqual(self.run_gate(source_url="https://example.org/unrelated")["status"], "watch")

    def test_reviewed_students_remain_available_for_verification(self):
        run = refresh()
        self.assertEqual(run["presentation_ids"], [])
        self.assertEqual(len(run["student_watchlist"]), 5)
