"""Offline interaction checks for the normal dashboard entry point."""
from pathlib import Path
from unittest import TestCase

from streamlit.testing.v1 import AppTest

from profile_evidence import CAMPUS_ROOT, profile_for


APP = Path(__file__).resolve().parents[1] / "app.py"


class DashboardTests(TestCase):
    def test_filter_shortlist_and_retrospective(self):
        desk = AppTest.from_file(str(APP)).run()
        self.assertFalse(desk.exception)
        desk.selectbox(key="inbox_age").select("Any age").run()
        desk.selectbox(key="inbox_region").select("Other Europe").run()
        desk.multiselect(key="inbox_stage").set_value(["Pre-seed"]).run()
        self.assertEqual(desk.radio(key="selected_lead").options, ["Constellate Proteomics"])
        desk.toggle[0].set_value(True).run()
        self.assertIn("334 days", [metric.value for metric in desk.metric])
        desk.button(key="save-research:constellate").click().run()
        desk.checkbox(key="show_shortlist").check().run()
        self.assertEqual(desk.radio(key="selected_lead").value, "research:constellate")
        desk.button(key="save-research:constellate").click().run()
        self.assertTrue(any("shortlist has no matches" in message.value for message in desk.info))
        self.assertFalse(desk.exception)

    def test_mode_change_clears_snapshot_and_unknowns_stay_reviewable(self):
        desk = AppTest.from_file(str(APP)).run()
        desk.sidebar.radio[0].set_value("Live discovery").run()
        self.assertFalse(desk.exception)
        self.assertFalse(any(r.label == "Open a dossier" for r in desk.radio))
        desk.sidebar.radio[0].set_value("Verified research snapshot").run()
        desk.text_input(key="inbox_query").set_value("no-such-company").run()
        next(b for b in desk.button if b.label == "Review all source hits").click().run()
        self.assertEqual(len(desk.radio(key="selected_lead").options), 4)
        self.assertFalse(desk.exception)

    def test_live_profile_lookup_requires_matching_campus_record(self):
        lead = {"id": "campus:foo", "origin": "TU Berlin", "name": "Jouly",
                "source_url": CAMPUS_ROOT + "startups-2026-jouly/"}
        self.assertEqual(profile_for(lead)["country"], "Germany")
        lead["source_url"] = "https://example.com/jouly"
        self.assertEqual(profile_for(lead), {})
