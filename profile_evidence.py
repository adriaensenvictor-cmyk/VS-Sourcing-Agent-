"""Analyst-checked public profile evidence for the dashboard, keyed by source lead ID.

Year-only dates retain their original precision. Dated signals use the date of the
public event or publication, which may precede the analyst's actual discovery.
"""

SIMRA_PROFILE = "https://www.linkedin.com/company/simra-tech/"
JOULY_PROFILE = "https://www.linkedin.com/company/jouly-ai/"
CONSTELLATE_PROFILE = "https://www.linkedin.com/company/constellate-proteomics"
CONSTELLATE_TEAM = "https://www.constellate.pro/constellate-about.html"
CONSTELLATE_ROUND = "https://www.graduate.nl/insights/new-pre-seed-investment-constellate-proteomics"
GERMAN_REGISTER = "https://www.unternehmensregister.de/en"
TERRATASK_PRESS = "https://drive.google.com/drive/folders/1zhiooyFYS9aWUQbOTuUOaaYyk6rEu24Q"

PROFILE_EVIDENCE = {
    "research:simra": {
        "logo_path": "static/logos/simra.png",
        "country": "Germany",
        "founded_year": 2026,
        "founded_source": SIMRA_PROFILE,
        "logo_url": "https://www.simratech.com/favicon-96x96.png",
        "founders": [
            {"name": "Dr.-Ing. Amir Mabhout", "role": "CEO", "linkedin_url": "https://de.linkedin.com/in/amirmabhout"},
            {"name": "Holger Niessner", "role": "CTO"},
        ],
        "sources": [
            {"label": "Simra team and product", "url": "https://www.simratech.com/"},
            {"label": "Berlin address in company imprint", "url": "https://www.simratech.com/impressum/"},
            {"label": "Company-reported founding year and headquarters", "url": SIMRA_PROFILE},
        ],
        "dated_signals": [
            {"signal": "OpenADA public release announcement", "observed_at": "2026-07-20",
             "excerpt": "Simra published its open-source interface between design agents and chip-design tools.",
             "url": "https://www.simratech.com/blog/openada-open-source/"},
            {"signal": "Reproducible chip-design benchmark", "observed_at": "2026-09-12",
             "excerpt": "The team published version 0.1 of TapeoutBench with thirteen chip-design tasks.",
             "url": "https://tapeoutbench.simratech.com/v0.1/"},
        ],
    },
    "research:terratask": {
        "logo_path": "static/logos/terratask.png",
        "country": "Germany",
        "logo_url": "https://drive.google.com/thumbnail?id=1UHfmtoJ0GrnZk-ppubm56T_-_Cfzllup&sz=w200",
        "founders": [
            {"name": "Johnny Benjes", "role": "CEO", "linkedin_url": "https://de.linkedin.com/in/johnny-benjes-876b771b6"},
            {"name": "Linda Ochwada", "role": "CTO", "linkedin_url": "https://de.linkedin.com/in/ochwada-l-66630a36"},
            {"name": "Michael Eiden", "role": "CDO", "linkedin_url": "https://de.linkedin.com/in/michael-eiden"},
        ],
        "sources": [
            {"label": "Team and roles", "url": "https://www.terratask.de/uber-uns"},
            {"label": "Berlin address in company imprint", "url": "https://www.terratask.de/impressum"},
            {"label": "Official press kit and logo", "url": TERRATASK_PRESS},
        ],
        "dated_signals": [
            {"signal": "Pilot with the municipality of Wandlitz", "observed_at": "2026-10-14",
             "excerpt": "Smart City Berlin listed the founder and a Wandlitz representative in a session on their green-space pilot.",
             "url": "https://smart-city-berlin.de/events/scc2026"},
        ],
    },
    "research:jouly": {
        "logo_path": "static/logos/jouly.png",
        "country": "Germany",
        "founded_year": 2025,
        "founded_source": JOULY_PROFILE,
        "logo_url": "https://jouly.ai/favicon.png?v=2",
        "founders": [
            {"name": "Tim Wiebelhaus", "role": "Co-founder and CEO", "linkedin_url": "https://www.linkedin.com/in/tim-wiebelhaus/"},
            {"name": "Sebastian Otzen", "role": "Co-founder and CTO", "linkedin_url": "https://www.linkedin.com/in/sebastian-otzen/"},
            {"name": "Robin Beer", "role": "Head of Energy Intelligence"},
        ],
        "financials": [
            {"label": "Search for Jouly GmbH · Charlottenburg HRB 286719 B", "url": GERMAN_REGISTER},
        ],
        "sources": [
            {"label": "Company-reported founding year", "url": JOULY_PROFILE},
            {"label": "Company imprint and register number", "url": "https://jouly.ai/impressum"},
            {"label": "Team and founder profiles", "url": "https://jouly.ai/"},
        ],
        "dated_signals": [
            {"signal": "Founders named in a university consulting project", "observed_at": "2026-01-30",
             "excerpt": "HWR Berlin named both Jouly founders in a report on student teams working on market-entry strategy, before the GmbH was registered.",
             "url": "https://www.hwr-berlin.de/aktuelles/neuigkeit/detail/studierende-beraten-startups"},
            {"signal": "Founder interview with VDI Wissensforum", "observed_at": "2026-10-30",
             "excerpt": "Sebastian Otzen outlined Jouly’s approach to energy optimisation for industrial plants.",
             "url": "https://www.vdi-wissensforum.de/wissen/wie-koennen-industrieunternehmen-ihr-energiesystem-intelligent-optimieren/"},
        ],
    },
    "research:constellate": {
        "logo_path": "static/logos/constellate.png",
        "country": "Netherlands",
        "founded_year": 2025,
        "founded_source": CONSTELLATE_PROFILE,
        "logo_url": "https://www.constellate.pro/apple-touch-icon.png",
        "stage": "Pre-seed",
        "stage_source": CONSTELLATE_ROUND,
        "founders": [
            {"name": "Carlos de Lannoy", "role": "Co-founder and CEO", "linkedin_url": "https://linkedin.com/in/cvdelannoy"},
            {"name": "Dennis de Beeld", "role": "Co-founder and CBO", "linkedin_url": "https://linkedin.com/in/dennis-de-beeld"},
            {"name": "Arian Khoshchin", "role": "Co-founder and head of marketing", "linkedin_url": "https://linkedin.com/in/arian-khoshchin"},
        ],
        "financials": [
            {"label": "Search for filed accounts at the Dutch Chamber of Commerce", "url": "https://www.kvk.nl/en/filing/checking-your-financial-statements/"},
        ],
        "sources": [
            {"label": "Founder profiles and company milestones", "url": CONSTELLATE_TEAM},
            {"label": "Company-reported founding year and headquarters", "url": CONSTELLATE_PROFILE},
            {"label": "Pre-seed announcement from Graduate Ventures", "url": CONSTELLATE_ROUND},
        ],
    },
}

SOURCE_GUIDE = [
    {"label": "Helmholtz spin-offs", "url": "https://www.helmholtz.de/assets/helmholtz_gemeinschaft/Bilder/Transfer/2026_Webseite_Liste_Ausgr%C3%BCndungen_der_Helmholtz-Gemeinschaft.pdf",
     "use": "Find German research spin-offs by founding year, home institute, city and sector in the March 2026 roster."},
    {"label": "CORDIS projects and results", "url": "https://cordis.europa.eu/projects/en",
     "use": "Follow EU research partners from grant to demonstrator. Project pages and downloadable datasets identify participants and deliverables."},
    {"label": "TED procurement notices", "url": "https://ted.europa.eu/en/",
     "use": "Check whether a public buyer names the startup in an award notice. Match the legal entity and distinguish an award from a call for bids."},
    {"label": "German Company Register", "url": GERMAN_REGISTER,
     "use": "Search by legal name and register number for registration history and available accounts. Some deposited documents require login and a fee."},
]


# Live campus rows use a different ID. Match only the specific university page
# that was reviewed for this company, never its display name or a shared domain.
CAMPUS_ROOT = "https://www.tu.berlin/entrepreneurship/startup-support/tu-startups/container-profile/"
CAMPUS_PROFILES = {
    CAMPUS_ROOT + "startups-2026-simra-ai": "research:simra",
    CAMPUS_ROOT + "startups-2026-terratask": "research:terratask",
    CAMPUS_ROOT + "startups-2026-jouly": "research:jouly",
}


def profile_for(item):
    profile_id = item["id"]
    if item.get("origin") == "TU Berlin":
        profile_id = CAMPUS_PROFILES.get((item.get("source_url") or "").rstrip("/"))
    return PROFILE_EVIDENCE.get(profile_id, {})
