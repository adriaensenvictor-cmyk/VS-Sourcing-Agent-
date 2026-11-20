import json
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from student_watchlist import BRUCHSAL, GEN, GERMAN_FINAL, KOSICE, REGIONAL, refresh

ROOT = Path(__file__).resolve().parents[1]
STAND = "https://expo.gen-e.eu/expo/17902a16-ee88-45f2-be00-bc43b314858f"


def gen_card(name, href, level="Upper-Secondary", country="Slovakia"):
    return (f'<a class="winner-tile" href="{href}"><b class="winner-name">{name}</b>'
            f'<b class="winner-level">{level}</b><b class="winner-country">{country}</b></a>')


def feeds():
    return {
        GEN: (gen_card("Lipigo", STAND) * 2
              + gen_card("Same name", "https://expo.gen-e.eu/expo/team-a")
              + gen_card("Same name", "https://expo.gen-e.eu/expo/team-b")
              + gen_card("University venture", STAND + "-uni", "University")
              + gen_card("Invalid link", "https://example.com/expo/team")),
        GERMAN_FINAL: '<a class="team-card" href="/finale-2026/heuwind"><span class="name-label">Heuwind</span>'
                      '<span class="team-text"><strong>Handelslehranstalt Bruchsal</strong></span></a>',
        REGIONAL: '<main><time datetime="2026-05-22"></time><p>Das Team „WonderBall“ vom Lichtenstern Gymnasium</p></main>',
        KOSICE: '<table><tr><td><h3><a href="/novinky/2026/lipigo-new">LIPIGO update</a></h3></td></tr></table>',
        BRUCHSAL: '<rss><channel><item><title>Heuwind presents</title><pubDate>Fri, 27 Mar 2026 08:51:45 +0000</pubDate>'
                  '<link>https://www.handelslehranstalt-bruchsal.de/2026/pitch/</link></item></channel></rss>',
    }


class StudentWatchTests(unittest.TestCase):
    def test_snapshot_is_offline_and_separates_source_claims(self):
        run = refresh(fetcher=lambda _: self.fail("offline mode fetched the network"))
        rows = {r["name"]: r for r in run["student_watchlist"]}
        self.assertEqual(set(rows), {"AeroOne", "Heuwind Lagertechnik", "Moore UB", "LIPIGO", "GlioScope"})
        self.assertTrue(all(p["funding_status"] == "unknown" and p["formation_date"] is None for p in rows.values()))
        self.assertTrue(all(s["url"].startswith("https://") for p in rows.values() for s in p["signals"]))
        news = rows["AeroOne"]["signals"]
        self.assertEqual({s["basis"] for s in news if s["kind"] == "customer_report"}, {"local_reporting", "team_self_report"})
        scheduled = next(s for s in rows["LIPIGO"]["signals"] if s["kind"] == "scheduled_event")
        self.assertEqual(scheduled["scheduled_for"], "2026-11-25")

    def test_rosters_filter_and_deduplicate_by_identity(self):
        run = refresh(live=True, fetcher=feeds().__getitem__)
        self.assertEqual(run["status"], "ok")
        rows = run["student_watchlist"]
        self.assertEqual(len(rows), 8)
        self.assertEqual(sum(r["name"] == "Same name" for r in rows), 2)
        lipigo = next(p for p in rows if p["name"] == "LIPIGO")
        self.assertEqual(len(lipigo["observations"]), 2)
        new_entry = next(p for p in rows if p["name"] == "WonderBall")
        self.assertEqual(new_entry["signals"], [])
        self.assertEqual(new_entry["observations"][0]["date"], "2026-05-22")

    def test_comparison_and_partial_source_recovery(self):
        data = feeds()
        first = refresh(live=True, fetcher=data.__getitem__)
        before = json.dumps(first)
        data[KOSICE] = data[KOSICE].replace("lipigo-new", "lipigo-retail").replace("LIPIGO update", "LIPIGO retail news")
        data[GEN] = "<html>unrecognized</html>"
        second = refresh(live=True, previous=first, fetcher=data.__getitem__)
        self.assertEqual(json.dumps(first), before)
        self.assertEqual(second["status"], "partial")
        self.assertEqual(second["sources"][GEN]["status"], "error")
        self.assertEqual(len(second["student_watchlist"]), len(first["student_watchlist"]))
        self.assertEqual(second["changes"], [{"project_id": "student:lipigo",
                         "url": "https://www.gympos.sk/novinky/2026/lipigo-retail", "change": "new_listing"}])
        data[GEN] = feeds()[GEN]
        third = refresh(live=True, previous=second, fetcher=data.__getitem__)
        self.assertEqual(third["changes"], [])
        self.assertEqual(third["status"], "ok")

    def test_all_sources_unavailable_keep_reviewed_projects(self):
        def offline(url):
            raise OSError("offline")
        result = refresh(live=True, fetcher=offline)
        self.assertEqual(result["status"], "error")
        self.assertEqual(len(result["student_watchlist"]), 5)

    def test_streamlit_page_snapshot_live_filter_and_download(self):
        app = AppTest.from_file(str(ROOT / "pages/Student_projects.py")).run()
        self.assertFalse(app.exception)
        self.assertFalse(app.subheader)
        app.toggle[0].set_value(True).run()
        app.selectbox[0].select("Slovakia").run()
        self.assertTrue(any("Scheduled for 2026-11-25" in x.value for x in app.caption))
        with patch("student_watchlist.fetch", side_effect=AssertionError("unexpected fetch")), patch(
                "student_watchlist.refresh", return_value=refresh(live=True, fetcher=feeds().__getitem__)):
            app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("download_button")), 1)
