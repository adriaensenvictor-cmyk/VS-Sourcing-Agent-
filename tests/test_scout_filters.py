from datetime import date
from unittest import TestCase

from scout_filters import (
    ALL_EUROPE, ANYWHERE, GERMANY, OTHER_EUROPE, UNKNOWN_REGION, Formation,
    age_fit, formation_record, funding_stage, lead_stage, location_region, region_matches,
)


SOURCE = 'https://example.org/registry/42'


class ScoutFilterTests(TestCase):
    def test_geography_has_disjoint_views_and_prioritizes_a_reported_country(self):
        assert location_region({'location': 'Berlin, Germany'}) == GERMANY
        assert location_region({'location': 'London, UK'}) == OTHER_EUROPE
        assert location_region({'location': 'Wilmington, DE, USA'}) == UNKNOWN_REGION
        assert location_region({'origin': 'GitHub', 'location': 'Berlin, Germany'}) == UNKNOWN_REGION
        assert location_region({'origin': 'TU Berlin', 'location': 'Berlin, Germany'}) == UNKNOWN_REGION
        assert location_region({'location': 'Paris, Texas, USA'}, {'country': 'Netherlands'}) == OTHER_EUROPE
        assert region_matches(GERMANY, ALL_EUROPE) and region_matches(OTHER_EUROPE, ALL_EUROPE)
        assert not region_matches(GERMANY, OTHER_EUROPE)
        assert not region_matches(UNKNOWN_REGION, ALL_EUROPE)
        assert region_matches(UNKNOWN_REGION, ANYWHERE)


    def test_age_uses_sourced_formation_date_or_year_and_never_grants_or_timeline(self):
        lead = {'first_observed_at': '2026-11-20', 'cohort': '2026', 'evidence': [
            {'signal': 'EXIST support', 'excerpt': 'Grant registration dated 28 April 2026', 'url': SOURCE},
            {'signal': 'Company formation trace', 'excerpt': 'Registration date unknown', 'url': SOURCE,
             'observed_at': '2026-11-20'},
        ]}
        assert formation_record(lead) is None
        assert formation_record(lead, {'founded_on': '2026-04-28'}) is None
        lead['evidence'].append({'signal': 'Company formation trace', 'excerpt': 'Jouly GmbH registration dated 28 April 2026', 'url': SOURCE})
        assert formation_record(lead) == Formation(date(2026, 4, 28), SOURCE)
        assert formation_record({}, {'founded_year': 2024, 'founded_source': SOURCE}) == Formation(2024, SOURCE)


    def test_uncertain_dates_and_age_boundaries(self):
        today = date(2026, 11, 20)
        assert age_fit(Formation(date(2023, 11, 20), SOURCE), 3, today)
        assert age_fit(Formation(date(2023, 11, 19), SOURCE), 3, today) is False
        assert age_fit(Formation(2023, SOURCE), 3, today) is None
        assert age_fit(Formation(2024, SOURCE), 3, today) is True
        assert age_fit(Formation(2022, SOURCE), 3, today) is False
        assert age_fit(Formation(date(2027, 1, 1), SOURCE), 3, today) is None
        assert age_fit(Formation(date(2021, 2, 28), SOURCE), 3, date(2024, 2, 29))


    def test_stage_confidence_and_conflicting_round_labels(self):
        for status in ('No funding found', 'No seed round', 'grant for pre-seed teams', 'raising Seed', 'unknown'):
            assert funding_stage(status) == 'Unverified'
        assert funding_stage('Series B funding') == 'Series B'
        assert funding_stage('Series D') == 'Series C+'
        assert funding_stage('Seed and Series A') == 'Other / review'
        assert lead_stage({'funding_status': 'Unknown'}, {'stage': 'Pre-seed'}) == 'Pre-seed'
