from datetime import date
from unittest import TestCase
from unittest.mock import patch

from bs4 import BeautifulSoup

from discovery_pipeline import run_discovery
from early_sources import FALLING_WALLS, scan_jugend, scan_junior, scan_tum_award
from earliness import comparison_days, public_trace, recent_signal
from founder_signals import founder_history


def html(source):
    return BeautifulSoup(source, "html.parser")


class EarlySourcesTests(TestCase):
    def test_latest_event_roster_preserves_publication_and_pitch_dates_and_funding(self):
        roster = html("""
            <p>Pitch in front of our jury on stage in Berlin on 6 November.</p>
            <div class="paragraph--type--persons-manually"><h2>Finalists 2026</h2>
              <a rel="bookmark" href="/foundation/people/noah-labs">
                <h3 class="node-title">Noah Labs</h3>
                <div class="field--name-field-institution">Germany</div></a></div>
            <div class="paragraph--type--persons-manually"><h2>Finalists 2025</h2>
              <a rel="bookmark" href="/foundation/people/old">
                <h3 class="node-title">Old Finalist</h3>
                <div class="field--name-field-institution">Germany</div></a></div>
        """)
        press = html("""<time datetime="2026-08-06T06:00:30Z"></time>
            <div><h2>FALLING WALLS VENTURE – FINALISTS</h2>
            <p><strong>Noah Labs</strong> – Germany<br><em>Heart monitoring</em></p></div>""")
        with patch("early_sources.get_html", side_effect=lambda url: roster if url == FALLING_WALLS else press):
            outcome = run_discovery(("Falling Walls Venture",), github_limit=0)
        self.assertEqual(outcome["source_status"]["Falling Walls Venture"]["count"], 1)
        row, = outcome["candidates"]
        self.assertEqual(row["earliest_verified_public_signal"]["date"], "2026-08-06")
        self.assertTrue(any(e["signal"] == "Scheduled pitch" and e["excerpt"] == "2026-11-06"
                            for e in row["evidence"]))
        self.assertEqual(row["funding"]["status"], "funded")
        self.assertEqual(outcome["shortlist"], [])

    def test_tum_follows_latest_published_archive_entry(self):
        roster = html('<a href="/result25">2025</a><a href="/result26">2026</a>')
        article = html("""<meta property="article:published_time" content="2026-11-30T12:00:00+01:00">
            <div class="ce-textmedia__content"><h2>First place: New Venture</h2><p>A prototype.</p></div>""")
        with patch("early_sources.get_html", side_effect=[roster, article]) as fetch:
            row, = scan_tum_award([])
        self.assertTrue(fetch.call_args.args[0].endswith("/result26"))
        self.assertEqual(row["title"], "New Venture")
        self.assertEqual(row["milestones"][0]["date"], "2026-11-30")

    def test_school_adapters_capture_project_level_fields_only(self):
        youth = html("""<a class="team-card"><span class="name-label">CLIPRO</span>
                          <span class="team-text">Private Name age 16</span></a>""")
        junior = html("""<time datetime="2026-06-17"></time><div class="article__section--list">
                         <div class="text"><p>Schülerfirma „AeroOne“ (Private Name)</p></div></div>""")
        with patch("early_sources.get_html", side_effect=[youth, junior]):
            projects = scan_jugend([]) + scan_junior([])
        self.assertEqual([row["name"] for row in projects], ["CLIPRO", "AeroOne"])
        self.assertNotIn("Private Name", str(projects))
        self.assertNotIn("school", str(run_discovery((), github_limit=0)).casefold())


class EarlinessTests(TestCase):
    def test_comparison_uses_real_capture_and_exact_publisher_date(self):
        capture = "2026-11-20T18:00:00+00:00"
        self.assertEqual(comparison_days(capture, {"date": "2026-11-19"}), -1)
        self.assertEqual(comparison_days(capture, {"date": "2026-11-21"}), 1)
        self.assertIsNone(comparison_days(capture, {"date": "2026"}))
        self.assertIsNone(comparison_days(None, {"date": "2026-11-21"}))

    def test_public_timing_retains_dossier_links_and_excludes_private_recent_events(self):
        profile = {"dated_signals": [{"observed_at": "2026-01-18", "url": "https://example.org",
                                     "signal": "Public pitch"}]}
        item = {"timeline": [{"date": "2026-10-01", "public_signal": False},
                             {"date": "2027-10-01"}]}
        self.assertEqual(public_trace(item, profile)["date"], "2026-01-18")
        self.assertTrue(recent_signal(item, profile, date(2026, 11, 20)))
        self.assertFalse(recent_signal(item, {}, date(2026, 11, 20)))

    def test_founder_recognizes_history_in_german_and_ignores_current_venture_alias(self):
        rows = founder_history("Alpha", ["Alex Doe"], [
            "Alex Doe gründete zuvor Skylark.", "Alex Doe previously founded Alpha GmbH.",
        ], "https://example.org/team")
        self.assertEqual([row["reference"] for row in rows], ["Skylark"])
