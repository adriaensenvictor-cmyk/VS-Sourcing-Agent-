"""Rank live German startup leads from TUM Venture Labs and Show HN.

python3 radar.py --json
python3 radar.py --limit 5 --days 365
"""

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode

from qualification import github_release_events, merge_candidates, public_funding_search, qualify
from sourcing import positive_int

ROOT = Path(__file__).resolve().parent

# Public cross-checks for leads reviewed during the challenge.
REVIEWED = {
    "tum:rapid-resilience": {
        "founder": "Jan Boeckmann",
        "profile": "https://de.linkedin.com/in/jan-boeckmann-29a84b191",
        "project_url": "https://rapid-resilience.de/",
        "funding_status": "unverified",
        "milestones": [{
            "date": "2025-07-16",
            "label": "Presented at Munich Startup Festival",
            "url": "https://www.munich-startup.de/en/110579/impact-area-at-the-munich-startup-festival/",
        }],
    },
    "tum:foresaight-ai": {
        "founder": "Laura Mati",
        "profile": "https://ch.linkedin.com/in/laura-mati-198a2858",
        "project_url": "https://www.foresaight.ai/",
        "funding_status": "public_support_reported",
        "funding_source": "https://www.foresaight.ai/",
    },
    "tum:fusix-biotech": {
        "profile": "https://www.linkedin.com/company/fusix-biotech/",
        "funding_status": "pre_seed_financing_reported",
        "funding_source": "https://fusixbiotech.de/about/",
    },
    "47221710": {
        "funding_status": "vc_round_reported",
        "funding_source": "https://minit.games/minit-games-emerges-from-stealth/",
        "milestones": [{
            "date": "2026-03-16",
            "label": "Round confirmed by company's legal advisers",
            "url": "https://www.goerg.de/de/aktuelles/veroeffentlichungen/16-03-2026/goerg-beraet-startup-minit-games-bei-pre-seed-finanzierungsrunde",
        }],
    },
    "tum:puray": {
        "profile": "https://www.linkedin.com/company/puray-germany/",
        "funding_status": "seed_stage_reported",
        "funding_source": "https://berlinscienceweek.com/100-science-start-ups-to-watch",
        "milestones": [{
            "date": "2020",
            "label": "SCE Strascheg Award reported on the company page",
            "url": "https://www.linkedin.com/company/puray-germany/",
        }],
    },
    "tum:imuveo": {
        "founder": "Dario Gosmann",
        "profile": "https://de.linkedin.com/in/dariogosmann",
        "funding_status": "grant_reported",
        "funding_source": "https://www.linkedin.com/company/imuveo/",
    },
}

WEIGHTS = {
    "Academic origin": 3,
    "Founding team": 2,
    "Team signal mentioned": 2,
    "Product validation": 3,
    "Early project stage": 3,
    "Prototype or launch mentioned": 3,
    "Customer or pilot mentioned": 1,
    "Commercial signal mentioned": 1,
    "Standalone company intent unclear": -3,
}


def collect(script, *options, warnings=None):
    result = subprocess.run(
        [sys.executable, str(ROOT / script), "--json", *options],
        capture_output=True,
        text=True,
        check=True,
        timeout=150,
    )
    if result.stderr:
        if warnings is None:
            print(result.stderr.rstrip(), file=sys.stderr)
        else:
            warnings.extend(result.stderr.strip().splitlines())
    return json.loads(result.stdout)


def enrich(lead):
    reviewed = REVIEWED.get(lead["id"], {})
    lead.update(reviewed)
    lead.setdefault("source", "Show HN")
    lead.setdefault("funding_status", "unverified")
    lead["milestones"] = list(lead.get("milestones", []))
    if lead.get("published_at"):
        lead["milestones"].append({
            "date": lead["published_at"],
            "label": "Show HN publication",
            "url": lead["source_url"],
        })

    lead["milestones"].sort(key=lambda event: event["date"])

    linkedin = list(lead.get("links", {}).get("linkedin", []))
    if reviewed.get("profile") and reviewed["profile"] not in linkedin:
        linkedin.append(reviewed["profile"])
    keywords = " ".join(filter(None, [reviewed.get("founder"), lead["title"], "founder"]))
    lead["linkedin"] = {
        "public_links": linkedin,
        "search_url": "https://www.linkedin.com/search/results/all/?" + urlencode({"keywords": keywords}),
    }
    weighted = {
        item["signal"]: WEIGHTS[item["signal"]]
        for item in lead["evidence"]
        if item["signal"] in WEIGHTS
    }
    if "founder" in reviewed and not {"Founding team", "Team signal mentioned"} & weighted.keys():
        weighted["Public founder profile reviewed"] = 2
    funding_penalties = {
        "pre_seed_financing_reported": -2,
        "seed_stage_reported": -4,
        "vc_round_reported": -6,
    }
    if lead["funding_status"] in funding_penalties:
        weighted["Financing or later stage reported"] = funding_penalties[lead["funding_status"]]
    lead["score_breakdown"] = weighted
    lead["score"] = sum(weighted.values())
    return lead


def rank_rows(leads, *, skip_github_releases=False, api_key=None):
    groups = merge_candidates(sorted(map(enrich, leads), key=lambda lead: lead["score"], reverse=True))
    with ThreadPoolExecutor(max_workers=4) as executor:
        def evaluate(group):
            releases = [] if skip_github_releases else github_release_events(group)
            check = public_funding_search(group[0], api_key) if api_key else None
            return qualify(group, releases, check)

        ranked = list(executor.map(evaluate, groups))
    ranked.sort(key=lambda lead: (lead["funding"]["status"] != "funded", lead["score"]), reverse=True)
    return ranked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=positive_int, default=10)
    parser.add_argument("--days", type=positive_int, default=365, help="Show HN lookback window")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--source-json", action="append", type=Path, default=[],
                        help="Import extra university or GitHub leads in the collector JSON format")
    parser.add_argument("--skip-github-releases", action="store_true",
                        help="Skip live GitHub enrichment")
    parser.add_argument("--search-funding", action="store_true", help="Search web funding signals via Brave Search API")
    args = parser.parse_args()
    api_key = os.environ.get("BRAVE_SEARCH_API_KEY")
    if args.search_funding and not api_key:
        parser.error("--search-funding requires BRAVE_SEARCH_API_KEY")

    leads = []
    successful = 0
    with ThreadPoolExecutor(max_workers=2) as executor:
        jobs = {
            "TUM Venture Labs": executor.submit(collect, "campus.py", "--limit", "100"),
            "Show HN": executor.submit(collect, "sourcing.py", "--days", str(args.days), "--limit", "100"),
        }
        for source, job in jobs.items():
            try:
                leads.extend(job.result())
            except subprocess.CalledProcessError as error:
                print(f"{source}: {error.stderr.strip() or 'collector failed'}", file=sys.stderr)
            except (subprocess.TimeoutExpired, ValueError) as error:
                print(f"{source}: {error}", file=sys.stderr)
            else:
                successful += 1
    for path in args.source_json:
        try:
            imported = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(imported, list) or any(
                not isinstance(item, dict) or not {"id", "title", "source_url", "evidence"} <= item.keys()
                for item in imported
            ):
                raise ValueError("expected an array of collector leads")
        except (OSError, ValueError) as error:
            parser.error(f"{path}: {error}")
        leads.extend(imported)
        successful += 1
    if not successful:
        return 1

    results = rank_rows(
        leads, skip_github_releases=args.skip_github_releases,
        api_key=api_key if args.search_funding else None,
    )
    results = results[:args.limit]
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    elif not results:
        print("No leads matched.")
    else:
        for lead in results:
            print(f'[{lead["score"]}] {lead["title"]} | {lead["funding"]["status"]}')
            print(f'    {lead["source_url"]}')
            for url in lead["linkedin"]["public_links"]:
                print(f"    LinkedIn: {url}")
            if not lead["linkedin"]["public_links"]:
                print(f'    LinkedIn search: {lead["linkedin"]["search_url"]}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
