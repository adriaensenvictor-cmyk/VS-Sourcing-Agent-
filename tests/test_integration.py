"""Shared contract and Streamlit integration checks using pinned research data."""
import csv
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from dashboard_data import dashboard_rows, export_csv, export_json, public_trace_age
from discovery_pipeline import campus_record, run_discovery, source_result
from emergence import rank_candidates
from engine import load_research_snapshot
from qualification import qualify

ROOT = Path(__file__).resolve().parents[1]


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.run = json.loads((ROOT / "research/founder-shortlist.json").read_text())
        self.run.update(mode="live", source_status={})
        self.run["candidates"] = list(self.run["shortlist"])

    def test_adapter_preserves_engine_ranking_evidence_and_funding(self):
        rows = dashboard_rows(self.run, shortlist_only=True)
        self.assertEqual([row["id"] for row in rows], [row["id"] for row in self.run["shortlist"]])
        for original, row in zip(self.run["shortlist"], rows):
            self.assertEqual(row["score"], original["founder_emergence_score"])
            self.assertEqual(row["timeline"], original["timeline"])
            self.assertEqual(row["evidence_confidence"], original["evidence_confidence"])
            self.assertEqual(row["funding"], original["funding"])
            self.assertEqual(row["sources"], original["sources"])
        self.assertIn("scoped review", rows[0]["funding_label"])
        self.assertIn("Unknown", rows[1]["funding_label"])

    def test_exports_keep_filtered_funding_and_canonical_json(self):
        row = dashboard_rows(self.run)[0]
        payload = json.loads(export_json(self.run, [row]))
        self.assertEqual(payload["shortlist"], self.run["shortlist"][:1])
        self.assertEqual(payload["candidates"][0]["location"]["country"], "Germany")
        self.assertEqual(payload["manual_review"], [row["id"]])
        table = list(csv.DictReader(io.StringIO(export_csv([row]))))
        self.assertEqual(table[0]["funding_status"], "no_funding_found")
        self.assertEqual(table[0]["earliest_public_date"], row["earliest_public_date"])
        self.assertEqual(json.loads(table[0]["source_urls"]), row["sources"])
        self.assertEqual(json.loads(table[0]["founder_evidence"]), row["founders"])
        self.assertEqual(json.loads(table[0]["timeline"]), row["timeline"])
        self.assertEqual(json.loads(table[0]["claims"]), row["claims"])
        self.assertEqual(json.loads(table[0]["funding_review"]), row["funding"])
        guarded = list(csv.DictReader(io.StringIO(export_csv([{**row, "name": "=1+1"}]))))
        self.assertEqual(guarded[0]["name"], "'=1+1")

    def test_public_trace_age_retains_date_precision(self):
        self.assertEqual(public_trace_age("2025-07-16", "2026-11-20T14:00:00Z"),
                         "16 months since earliest public trace")
        self.assertEqual(public_trace_age("2025", "2026-11-20"), "Year-only evidence (2025)")
        self.assertEqual(public_trace_age(None, "2026-11-20"), "No dated public trace")
        self.assertEqual(public_trace_age("2027-01-01", "2026-11-20"), "Public trace age unavailable")

    def test_funded_candidate_is_visible_for_diligence_and_excluded_from_shortlist(self):
        candidate = self.run["shortlist"][0]
        funded = {**candidate, "funding": {"status": "funded", "rounds": [
            {"source_url": candidate["source_url"]}]}}
        run = rank_candidates([funded], limit=10)
        self.assertEqual(dashboard_rows(run, shortlist_only=True), [])
        row = dashboard_rows(run)[0]
        self.assertEqual(row["funding_label"], "Funding round reported")
        self.assertIn("funded_or_later_stage", row["shortlist_exclusions"])

    def test_seed_evidence_retained_after_source_merge_excludes_candidate(self):
        candidate = self.run["shortlist"][0]
        candidate = {**candidate, "funding": {"status": "unknown", "reviews": [
            {"source_url": candidate["source_url"], "reported_as": "seed_stage_reported"}]}}
        run = rank_candidates([candidate], limit=10)
        self.assertFalse(run["shortlist"])
        self.assertIn("funded_or_later_stage", run["candidates"][0]["shortlist_exclusions"])

    def test_repository_link_from_secondary_record_survives_qualification(self):
        url = "https://example.org/project"
        repo = "https://github.com/example/project"
        row = {"id": "example", "source_url": url, "project_url": url,
               "evidence": [], "linkedin": {"public_links": []}}
        linked = {**row, "id": "extra", "links": {"github": [repo]}}
        self.assertEqual(qualify([row, linked])["links"]["github"], [repo])

    def test_source_failure_keeps_successful_tu_berlin_data(self):
        row = campus_record(load_research_snapshot(ROOT / "data/research_snapshot.json")[0])
        with patch("discovery_pipeline.collect", side_effect=subprocess.TimeoutExpired("campus", 5)):
            with patch("discovery_pipeline.load_campus", return_value=[row]):
                run = run_discovery(("TUM Venture Labs", "TU Berlin"))
        self.assertEqual(run["source_status"]["TUM Venture Labs"]["state"], "error")
        self.assertEqual(run["source_status"]["TU Berlin"]["state"], "ok")
        self.assertIn(row["id"], {candidate["id"] for candidate in run["candidates"]})

    def test_warnings_keep_partial_source_results(self):
        def load(warnings):
            warnings.append("Some results unavailable")
            return [{"id": "example"}]
        rows, status = source_result(load)
        self.assertEqual(rows, [{"id": "example"}])
        self.assertEqual(status["state"], "partial")

    def test_app_consumes_authoritative_shortlist_and_keeps_snapshot_mode(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db_path = patch.dict("os.environ", {"FIRSTTRACE_DB_PATH": str(Path(tmp.name) / "inbox.sqlite3")})
        db_path.start()
        self.addCleanup(db_path.stop)
        app = AppTest.from_file(str(ROOT / "app.py")).run()
        with patch("discovery_pipeline.run_discovery", return_value=self.run) as run:
            app.button[0].click().run()
            run.assert_called_once()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "3")
        self.assertIn("Rapid Resilience", [heading.value for heading in app.header])
        self.assertTrue(any("Company age is unverified" in entry.value for entry in app.caption))
        self.assertTrue(any("Jan Boeckmann" in entry.value for entry in app.text))
        self.assertTrue(any("Munich Startup Festival" in entry.value for entry in app.text))
        self.assertEqual(len(app.get("download_button")), 3)
        app.radio(key="data_mode").set_value("Verified research snapshot").run()
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("DEMO RESEARCH MODE" in warning.value for warning in app.warning))
        self.assertEqual(app.metric[0].value, "3")
