import csv
import io
import json
import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from dashboard_data import ROOT, dashboard_rows, export_csv, export_json, load_demo_run
from emergence import rank_candidates
from fit_analysis import cache_key, request_analysis
from qualification import qualify
from founder_fit import FOUNDER, VENTURE, evaluate

TODAY = date(2026, 11, 20)
URL = "https://example.org/review"


def fact(criterion, direction="supports", **extra):
    return {"criterion": criterion, "text": "Synthetic test evidence for " + criterion,
            "subject": "Test team", "source_url": URL, "status": "verified",
            "direction": direction, **extra}


def grade(*observations, **row):
    return evaluate([{"fit_evidence": observations, **row}], TODAY)


class FitTests(unittest.TestCase):
    def test_founder_can_offset_immature_product(self):
        result = grade(*(fact(k) for k in FOUNDER), fact("technical_feasibility", "limits"))
        self.assertEqual(result["founder"]["score"], 100)
        self.assertEqual(result["venture"]["score"], 0)
        self.assertTrue(result["assessment"].startswith("Founder-led"))
        self.assertEqual(result["score"], 100)

    def test_venture_can_offset_inexperience_or_unknown_team(self):
        for founder in ([], [fact("operating_experience", "limits")]):
            result = grade(*founder, *(fact(k) for k in VENTURE))
            self.assertEqual(result["founder"]["score"], 0 if founder else None)
            self.assertEqual(result["venture"]["score"], 100)
            self.assertTrue(result["assessment"].startswith("Venture-led"))

    def test_dual_strength_and_sparse_evidence(self):
        both = grade(*(fact(k) for k in (*FOUNDER, *VENTURE)))
        self.assertEqual(both["assessment"], "Strong on both dimensions")
        self.assertEqual(both["score"], 100)
        sparse = grade(fact("domain_expertise"), fact("technical_feasibility"))
        self.assertIsNone(sparse["score"])

    def test_weak_requires_actual_counterevidence(self):
        weak = grade(*(fact(k, "limits") for k in (*FOUNDER, *VENTURE)))
        self.assertEqual(weak["score"], 0)
        self.assertIn("Low priority", weak["assessment"])
        empty = grade(founders=[{"name": "Test person", "role": "PhD at famous university", "source_url": URL}])
        self.assertIsNone(empty["founder"]["score"])
        self.assertIsNone(empty["score"])

    def test_conflicts_across_records_and_duplicate_budget(self):
        pos = fact("built_technology")
        result = evaluate([{"fit_evidence": [pos, pos]}, {"fit_evidence": [
            {**pos, "direction": "limits", "source_url": URL + "/other"}]}], TODAY)
        self.assertEqual(result["founder"]["conflicts"], ["built_technology"])
        self.assertIsNone(result["score"])
        self.assertEqual(len(result["evidence"]), 2)
        self.assertEqual(grade(pos, pos)["founder"]["score"], 20)

    def test_hypothesis_unattributed_future_and_nonpublic_evidence(self):
        result = grade(fact("domain_expertise", subject=""), fact("pilot", status="hypothesis"),
                       fact("built_technology", source_url="file:///example"),
                       fact("operating_experience", reviewed_on="2027-01-01"),
                       claims=[{"type": "pilot", "text": "Pilot mentioned", "source_url": URL, "status": "hypothesis"}])
        self.assertEqual(result["evidence"], [])

    def test_university_review_and_ignored_trace_dates(self):
        row = {"source": "TU Berlin", "timeline": [{"date": "2008-01-01", "label": "First article"}],
               "github_activity": {"created_at": "2007-01-01"}}
        for facts in ([], [fact("unincorporated")]):
            result = grade(*facts, **row)["three_year_eligibility"]
            self.assertEqual(result["status"], "unknown")
            self.assertTrue(result["university_review"])
            self.assertEqual("unincorporated" in result["reason"], bool(facts))

    def test_qualified_secondary_profile_and_observations_survive_merge(self):
        source = {"id": "one", "source_url": URL, "evidence": [], "linkedin": {"public_links": []}}
        secondary = {**source, "id": "two", "source_url": "https://www.tum-venture-labs.de/teams/rapid-resilience/",
                     "fit_evidence": [fact("operating_experience")]}
        result = evaluate([qualify([source, secondary])], TODAY)
        self.assertIn("domain_expertise", result["founder"]["strengths"])
        self.assertIn("operating_experience", result["founder"]["strengths"])
        self.assertEqual(result["three_year_eligibility"]["formation_date"], "2026-09-22")

    def test_attributed_reviewed_claims_outside_curated_profiles(self):
        result = grade(founders=[{"name": "Example Person", "source_url": URL}], claims=[{
            "type": "domain_experience", "text": "Example Person researched the product's failure mode.",
            "status": "verified", "source_url": URL}])
        self.assertEqual(result["founder"]["score"], 20)
        self.assertEqual(result["evidence"][0]["subject"], "Example Person")

    def test_exact_anniversary_future_and_partial_dates(self):
        for stamp, status in (("2023-11-20", "within_three_years"), ("2023-11-19", "older_than_three_years"),
                              ("2027-01-01", "unknown"), ("2024", "unknown")):
            self.assertEqual(grade(fact("legal_formation", date=stamp))["three_year_eligibility"]["status"], status)
        leap = {"fit_evidence": [fact("legal_formation", date="2024-02-29")]}
        self.assertEqual(evaluate([leap], date(2027, 2, 28))["three_year_eligibility"]["status"], "within_three_years")
        self.assertEqual(evaluate([leap], date(2027, 3, 1))["three_year_eligibility"]["status"], "older_than_three_years")

    def test_conflicting_formation_records(self):
        for other in (fact("unincorporated"), fact("legal_formation", date="2023-01-01")):
            result = grade(fact("legal_formation", date="2024-01-01"), other)["three_year_eligibility"]
            self.assertEqual(result["status"], "unknown")
            self.assertIn("Conflicting", result["reason"])

    def test_legacy_golden_scores_ranks_and_dimensions(self):
        original = json.loads((ROOT / "research/founder-shortlist.json").read_text())["shortlist"]
        run = rank_candidates(original, 10)
        expected = [(r["id"], r["emergence_dimensions"], r["founder_emergence_score"]) for r in original]
        self.assertEqual([(r["id"], r["emergence_dimensions"], r["early_signal_score"]) for r in run["shortlist"]],
                         expected)
        self.assertTrue(all(r["early_signal_score"] == r["founder_emergence_score"] for r in run["candidates"]))

    def test_real_snapshot_ui_and_exports(self):
        with patch("emergence.datetime") as clock:
            clock.now.return_value = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
            run = load_demo_run()
        rows = dashboard_rows(run)
        simra = next(row for row in rows if row["name"] == "Simra AI")
        fit = simra["founder_venture_fit"]
        self.assertTrue(fit["assessment"].startswith("Founder-led"))
        self.assertIn("Holger Niessner", {item.get("subject") for item in fit["evidence"]})
        self.assertEqual(json.loads(export_json(run, [simra]))["candidates"][0]["founder_venture_fit"], fit)
        self.assertEqual(json.loads(next(csv.DictReader(io.StringIO(export_csv([simra]))))["founder_venture_fit"]), fit)
        jouly = next(row for row in rows if row["name"] == "Jouly")
        self.assertEqual(jouly["founder_venture_fit"]["three_year_eligibility"]["formation_date"], "2026-04-28")

    def test_absent_key_and_cached_ai_request(self):
        fit = grade(fact("research_contribution"))
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}), patch("fit_analysis.urlopen") as post:
            self.assertIsNone(request_analysis(fit))
            post.assert_not_called()
        self.assertNotEqual(cache_key(fit), cache_key(grade()))
        response = {"priority": "founder", "evidence_id": 0, "question": "expertise"}
        api_reply = {"choices": [{"message": {"content": json.dumps(response)}}]}
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"}), patch("fit_analysis.urlopen") as post:
            post.return_value.__enter__.return_value = io.BytesIO(json.dumps(api_reply).encode())
            self.assertEqual(request_analysis(fit), response)
            payload = json.loads(post.call_args.args[0].data)
            self.assertTrue(payload["response_format"]["json_schema"]["strict"])

    def test_invalid_model_response(self):
        fit = grade(fact("research_contribution"))
        bad = {"priority": "founder", "evidence_id": 99, "question": "expertise"}
        body = {"choices": [{"message": {"content": json.dumps(bad)}}]}
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"}), patch("fit_analysis.urlopen") as post:
            post.return_value.__enter__.return_value = io.BytesIO(json.dumps(body).encode())
            with self.assertRaises(ValueError):
                request_analysis(fit)

    def test_streamlit_analysis_requires_click_and_survives_api_error(self):
        with (patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"}),
              patch("fit_panel.request_analysis") as ask, patch("emergence.datetime") as clock):
            clock.now.return_value = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
            app = AppTest.from_file(str(ROOT / "app.py")).run()
            app.radio[0].set_value("Verified research snapshot")
            app.sidebar.button[0].click().run()
            app.selectbox[0].select("tu-berlin:research:simra").run()
            ask.assert_not_called()
            ask.side_effect = OSError("offline")
            ai_button = lambda: next(b for b in app.button if "AI diligence" in b.label)
            ai_button().click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any("AI assessment unavailable" in warning.value for warning in app.warning))
            ask.side_effect = None
            ask.return_value = {"priority": "venture", "evidence_id": 0, "question": "product"}
            ai_button().click().run()
            app.run()
            self.assertTrue(ai_button().disabled)
            self.assertEqual(ask.call_count, 2)
