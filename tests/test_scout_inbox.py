"""Evidence diff and review behaviour across distinct scans."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from scout_inbox import ScoutInbox


APP = Path(__file__).resolve().parents[1] / "app.py"
URL = "https://example.org/venture"
LEAD = {"id": "case:one", "title": "Example venture", "source_url": URL,
        "timeline": [{"url": URL, "date": "2025-11-12", "label": "Named at campus event"}]}


def capture(day, lead=LEAD, *, state="ok", shortlisted=True):
    return {"mode": "live", "generated_at": f"2026-11-{day:02}T17:00:00Z",
            "candidates": [lead], "shortlist": [lead] if shortlisted else [],
            "source_status": {"test": {"state": state, "count": 1, "warnings": []}}}


class InboxTests(TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "desk.sqlite3"
        self.store = ScoutInbox(self.path)

    def test_only_new_evidence_opens_watched_lead_once(self):
        self.assertEqual(self.store.record(capture(15))["new_leads"], 1)
        question = self.store.inbox()[0]
        self.store.decide("live", LEAD["id"], "Watch", "Scout", "Wait for a named pilot",
                          "Customer or pilot", through=question["id"])
        draft = {"status": "hypothesis", "type": "pilot", "text": "Seeking pilot customers", "source_url": URL}
        self.assertEqual(self.store.record(capture(16, {**LEAD, "claims": [draft]}))["watch_matches"], 0)
        confirmed = {**draft, "status": "verified", "text": "Customer named in its own press release"}
        changed = {**LEAD, "claims": [confirmed]}
        self.assertEqual(self.store.record(capture(17, changed))["watch_matches"], 1)
        self.assertEqual(self.store.record(capture(18, changed))["watch_matches"], 0)
        self.assertEqual([row["kind"] for row in self.store.inbox()], ["Customer or pilot"])
        self.assertFalse(self.store.record(capture(14))["recorded"])
        self.assertEqual(self.store.first_seen(LEAD["id"]), "2026-11-15T17:00:00+00:00")
        self.assertEqual(ScoutInbox(self.path).decisions("live")[LEAD["id"]]["owner"], "Scout")

    def test_new_shortlist_membership_and_last_working_capture(self):
        self.assertEqual(self.store.record(capture(15, shortlisted=False))["new_leads"], 0)
        self.assertEqual(self.store.record(capture(16))["new_leads"], 1)
        self.assertEqual(self.store.record(capture(17, state="error"))["new_leads"], 0)
        self.assertEqual(self.store.latest_run()["generated_at"], capture(17)["generated_at"])
        self.assertEqual(self.store.latest_run(usable_only=True)["generated_at"], capture(16)["generated_at"])
        with self.assertRaises(ValueError):
            self.store.record({**capture(18), "mode": "research_snapshot"})

    def test_replay_withholds_future_details_until_decision(self):
        with patch.dict("os.environ", {"FIRSTTRACE_DB_PATH": str(self.path)}):
            desk = AppTest.from_file(str(APP)).run()
            desk.selectbox(key="workspace").select("Historical replay").run()
            self.assertFalse(desk.exception)
            self.assertFalse(desk.metric)
            self.assertFalse(any("pre-seed" in text.value for text in desk.markdown))
            desk.radio[0].set_value("Watch")
            next(b for b in desk.button if b.label == "Save decision and reveal").click().run()
            self.assertIn("334 days", [m.value for m in desk.metric])
