from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch

from bs4 import BeautifulSoup

from campus import read_team
from dashboard_data import dashboard_rows
from emergence import rank_candidates
from incubator_directory import read_centres
from programmes import scan_rootcamp


URL = "https://example.org/prospect"
SOURCE = "Fraunhofer AHEAD"


def prospect(**fields):
    lead = {"id": "one", "title": "Example venture", "description": "Industrial analytics concept",
            "source": SOURCE, "source_url": URL,
            "location": {"country": "Germany", "confidence": "ecosystem", "source_url": URL}}
    lead.update(fields)
    return lead


class EarlyDiscoveryTests(TestCase):
    def test_recent_programme_team_qualifies_without_mvp_or_commercial_claim(self):
        lead = prospect(evidence=[{"signal": "Recent programme selection", "excerpt": "Selected founding project"}])
        run = rank_candidates([lead], 10)
        self.assertEqual(len(run["shortlist"]), 1)
        row = dashboard_rows(run)[0]
        self.assertTrue(row["early_follow_up"])
        self.assertEqual(row["commercialization_signals"], [])

    def test_funded_and_unverified_location_still_excluded_from_shortlist(self):
        evidence = [{"signal": "Recent programme selection", "excerpt": "Selected founding project"}]
        funded = prospect(evidence=evidence, funding={"status": "funded", "rounds": [{"source_url": URL}]})
        location_unknown = prospect(evidence=evidence, location={"country": None, "confidence": "unknown"})
        pre_seed_report = prospect(evidence=evidence, funding={
            "status": "unknown", "reviews": [{"reported_as": "pre_seed_financing_reported", "source_url": URL}]})
        for lead, reason in ((funded, "funded_or_later_stage"),
                             (location_unknown, "location_outside_scope_or_unverified"),
                             (pre_seed_report, "no_commercialization_evidence")):
            run = rank_candidates([lead], 10)
            self.assertFalse(run["shortlist"])
            self.assertIn(reason, run["candidates"][0]["shortlist_exclusions"])

    def test_tum_captures_attributed_research_team_without_product(self):
        html = b"""<main><h1>Alpha</h1><dt>Founders</dt><dd>Alex Doe</dd>
                <p>Our doctoral research is the basis of a new venture.</p></main>"""
        with patch("campus.download", return_value=html):
            team = read_team(("https://www.tum-venture-labs.de/teams/alpha/", None))
        self.assertIn("University team in formation", {entry["signal"] for entry in team["evidence"]})
        self.assertEqual(team["founders"][0]["name"], "Alex Doe")

    def test_dated_rootcamp_selection_is_independent_of_company_founding(self):
        html = """<p id="hubspot-author_data">Aug 24, 2026, 3:06:26 PM</p>
                <span><h2>This is RootCamp Batch 8</h2><h3>Alpha | Germany</h3>
                <p>Research spin-off idea</p><h2>Upcoming events</h2></span>"""
        with patch("programmes.get_html", return_value=BeautifulSoup(html, "html.parser")):
            with patch("programmes.datetime", wraps=datetime) as clock:
                clock.now.return_value = datetime(2026, 11, 20, tzinfo=timezone.utc)
                row = scan_rootcamp([])[0]
        self.assertEqual(row["location"]["country"], "Germany")
        self.assertEqual(row["milestones"][0]["date"], "2026-08-24")
        self.assertIn("Recent programme selection", {entry["signal"] for entry in row["evidence"]})

    def test_national_directory_exposes_only_centre_information(self):
        html = """<div class="mitglied-standort"><span class="mitglied-standort-titel">Alpha Centre</span>
                <div class="mitglied-standort-inhalt"><p>Private contact marker</p>
                <a title="Routenplaner" href="https://example.org/map">12345 Berlin</a>
                <a href="https://example.org">Website</a></div></div>"""
        with patch("incubator_directory.get_html", return_value=BeautifulSoup(html, "html.parser")):
            self.assertEqual(read_centres(), [{"Centre": "Alpha Centre", "Address": "12345 Berlin",
                                               "Website": "https://example.org"}])
