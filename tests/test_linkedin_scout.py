from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from dashboard_data import dashboard_rows
from discovery_pipeline import run_discovery
from linkedin_scout import LINKEDIN_SOURCE, PUBLIC_POST, post_url, submitted_post
from scout_inbox import ScoutInbox


POST = "https://de.linkedin.com/posts/alex-doe-new-company-activity-12345-abcde?trk=share"
APP = str(Path(__file__).resolve().parents[1] / "app.py")


class LinkedInScoutTests(TestCase):
    def test_requires_a_real_linkedin_post_path(self):
        for value in ("https://www.linkedin.com/in/alex-doe/",
                      "https://www.linkedin.com.evil.example/posts/demo",
                      "https://www.linkedin.com@evil.example/posts/demo",
                      "https://www.linkedin.com:9999/posts/demo"):
            self.assertIsNone(post_url(value))
        self.assertEqual(post_url(POST), "https://www.linkedin.com/posts/alex-doe-new-company-activity-12345-abcde")

    def test_permalink_aliases_do_not_create_duplicate_startups(self):
        params = ("Alex Doe", "Example Venture", "Germany", "Looking for a co-founder", "New industrial software venture.")
        first = submitted_post(POST, *params)
        alias = submitted_post("https://www.linkedin.com/feed/update/urn:li:activity:12345/", *params)
        self.assertEqual(first["id"], alias["id"])
        with TemporaryDirectory() as folder:
            store = ScoutInbox(Path(folder) / "scout.sqlite3")
            store.save_linkedin_lead(first)
            store.save_linkedin_lead(alias)
            self.assertEqual(len(store.linkedin_leads()), 1)

    def test_user_submission_enters_engine_as_early_evidence_not_a_verified_grade(self):
        record = submitted_post(POST, "Alex Doe", "Example Venture", "Germany", "Looking for a co-founder",
                                "Alex Doe previously worked at Celonis. Industrial software concept.",
                                posted_on=date(2026, 11, 20))
        run = run_discovery((LINKEDIN_SOURCE,), linkedin_leads=[record])
        self.assertEqual(run["source_status"][LINKEDIN_SOURCE]["count"], 1)
        row = dashboard_rows(run, shortlist_only=True)[0]
        self.assertTrue(row["early_follow_up"])
        self.assertEqual(row["funding_status"], "unknown")
        self.assertEqual(row["evidence"][0]["signal"], PUBLIC_POST)
        self.assertIsNone(row["founder_venture_fit"]["score"])
        self.assertTrue(any(e.get("reference") == "Celonis" for e in row["evidence"]))

    def test_workspace_can_save_a_linkedin_source(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "scout.sqlite3"
            with patch.dict("os.environ", {"FIRSTTRACE_DB_PATH": str(path)}):
                desk = AppTest.from_file(APP).run()
                desk.selectbox(key="workspace").select("LinkedIn scouting").run()
                desk.selectbox(key="employer_group").select("Global technology and AI").run()
                self.assertIn("Google DeepMind", desk.selectbox(key="employer_search").options)
                fields = {"Public LinkedIn post link": POST, "Founder name": "Alex Doe",
                          "Venture or project": "Example Venture"}
                for field in desk.text_input:
                    if field.label in fields:
                        field.set_value(fields[field.label])
                desk.text_area[0].set_value("A concept for German industry.")
                desk.button[0].click().run()
                self.assertFalse(desk.exception)
                self.assertEqual(ScoutInbox(path).linkedin_leads()[0]["title"], "Example Venture")
