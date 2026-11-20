"""Connect the existing source adapters to the authoritative shortlist."""
import subprocess
from concurrent.futures import ThreadPoolExecutor

from emergence import DISCOVERY_SOURCES, EVENT_SOURCES, PROGRAMME_SOURCES, discover_github, rank_candidates, university_lead
from linkedin_scout import LINKEDIN_SOURCE
from qualification import detect_intent
from radar import collect, rank_rows


def campus_record(row):
    """Translate TU Berlin input to the existing radar collector contract."""
    url = row["source_url"]
    return {
        "id": "tu-berlin:" + row["id"],
        "title": row["name"],
        "source": "TU Berlin",
        "source_url": url,
        "description": row["description"],
        "sector": row["sector"],
        "team": row["team"],
        "cohort": row.get("cohort"),
        "project_url": row["project_url"] if row["project_url"] != url else None,
        "location": {"country": "Germany", "confidence": "ecosystem", "source_url": url},
        "evidence": [
            {**item, "source_url": item["url"]}
            for item in row["evidence"]
        ],
        "intent_cues": detect_intent(row["description"], url),
    }


def load_campus(warnings):
    # Keep the existing standard-library CLI usable without dashboard dependencies.
    from engine import scan_campus

    return [
        campus_record(row) for row in scan_campus(warnings=warnings)
        if not row["name"].casefold().startswith("exist women")
    ]


def source_result(loader):
    warnings = []
    try:
        rows = loader(warnings)
    except (OSError, ValueError, KeyError, ImportError, subprocess.SubprocessError) as error:
        return [], {"state": "error", "count": 0,
                    "warnings": [f"Source unavailable ({type(error).__name__})."]}
    return rows, {"state": "partial" if warnings else "ok", "count": len(rows),
                  "warnings": list(dict.fromkeys(warnings))}


def load_programme(name, warnings):
    if name in EVENT_SOURCES:
        from early_sources import EVENT_READERS

        return EVENT_READERS[name](warnings)

    from programmes import READERS

    return READERS[name](warnings)


def run_discovery(sources=DISCOVERY_SOURCES, days=365, *, github_limit=5, limit=10, api_key=None,
                  linkedin_leads=()):
    """Collect independently, retain source diagnostics, and let PR #3 rank."""
    loaders = {
        "TUM Venture Labs": lambda warnings: collect("campus.py", "--limit", "100", warnings=warnings),
        "Show HN": lambda warnings: collect(
            "sourcing.py", "--days", str(days), "--limit", "100", warnings=warnings,
        ),
        "TU Berlin": load_campus,
    }
    for name in PROGRAMME_SOURCES:
        loaders[name] = lambda warnings, programme=name: load_programme(programme, warnings)
    rows = []
    status = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        jobs = {name: executor.submit(source_result, loader)
                for name, loader in loaders.items() if name in sources}
        for name, job in jobs.items():
            found, status[name] = job.result()
            rows.extend(found)

    qualified = rank_rows(rows, skip_github_releases=True, api_key=api_key)
    if LINKEDIN_SOURCE in sources:
        qualified.extend(linkedin_leads)
        status[LINKEDIN_SOURCE] = {"state": "ok" if linkedin_leads else "skipped",
                                   "count": len(linkedin_leads), "warnings": []}
    if "TUM Venture Labs" in sources:
        qualified.append({**university_lead(), "record_provenance": "reviewed public reference"})
    github_rows = []
    if "GitHub" in sources and github_limit:
        github_rows, status["GitHub"] = source_result(
            lambda warnings: discover_github(qualified, github_limit, warnings=warnings),
        )
    elif "GitHub" in sources:
        status["GitHub"] = {"state": "skipped", "count": 0, "warnings": []}

    # Preserve website matching while also accepting a standalone repository identity.
    for row in github_rows:
        row["project_url"] = row.get("project_url") or row["source_url"]

    return rank_candidates(
        qualified + github_rows, limit, github_count=len(github_rows), source_status=status,
    )
