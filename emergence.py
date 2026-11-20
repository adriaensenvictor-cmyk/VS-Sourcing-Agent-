"""FounderRadar's conservative pre-funding shortlist."""
import argparse
import base64
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from founder_fit import evaluate, review_priority
from founder_signals import founder_history
from linkedin_scout import LINKEDIN_SOURCE
from qualification import detect_intent, merge_candidates, url_key
from sourcing import positive_int

CORE_DISCOVERY_SOURCES = ("TUM Venture Labs", "Show HN", "GitHub", "TU Berlin")
EVENT_SOURCES = ("TUM IDEAward", "Falling Walls Venture")
PROGRAMME_SOURCES = (
    "UnternehmerTUM Incubator", "imec.istart", "BayStartUP roster",
    "Fraunhofer AHEAD", "SpinLab", "RootCamp", "HPI Engine",
) + EVENT_SOURCES
DISCOVERY_SOURCES = CORE_DISCOVERY_SOURCES + PROGRAMME_SOURCES + (LINKEDIN_SOURCE,)

EXIST = "https://portal.mytum.de/jobs/wissenschaftler/NewsArticle_20260806_092633/newsarticle_view"
EUROPE = ("Germany", "France", "Netherlands", "Switzerland", "Austria", "Belgium",
          "Sweden", "Denmark", "Finland", "Norway", "Poland", "Spain", "Italy",
          "Portugal", "Ireland", "United Kingdom", "Czechia", "Estonia")
RISK = re.compile(r"\b(?:weekend project|hobby project|class assignment|school assignment|"
                  r"tutorial repository|agency services|internal pitch project)\b", re.I)
EMPTY_FUNDING = {"status": "unknown", "rounds": [], "reviews": [], "public_support": []}


def github_api(path, **query):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "FounderRadar/1.0"}
    token = os.getenv("FOUNDER_RADAR_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = "https://api.github.com" + path
    if query:
        url += "?" + urlencode(query)
    with urlopen(Request(url, headers=headers), timeout=10) as response:
        return json.load(response)


def repo_links(row):
    links = row.get("links", {}).get("github", [])
    for url in [*links, row.get("project_url"), row.get("source_url")]:
        key = url_key(url)
        if key and key[0] == "github":
            yield key


def activity(commits):
    weeks = defaultdict(set)
    for item in commits:
        author = item.get("author") or {}
        login = author.get("login", "")
        stamp = (item["commit"].get("committer") or {}).get("date")
        if not stamp or not login or author.get("type") == "Bot" or login.endswith("[bot]"):
            continue
        week = date.fromisoformat(stamp[:10]).isocalendar()
        weeks[login].add((week.year, week.week))
    recurring = sorted(login for login, active in weeks.items() if len(active) >= 2)
    return {
        "sampled_commits": len(commits),
        "active_weeks": len(set().union(*weeks.values())),
        "public_contributors": sorted(weeks),
        "recurring_contributors": recurring,
        "sustained_collaboration": len(recurring) >= 2,
        "commit_dates": sorted({
            item["commit"]["committer"]["date"] for item in commits
            if (item["commit"].get("committer") or {}).get("date")
        }),
    }


def github_record(repo, since):
    name = repo["full_name"]
    api = "/repos/" + name
    url = repo["html_url"]
    readme_url = url
    overview = repo.get("description") or ""
    readme = ""
    try:
        document = github_api(api + "/readme")
        readme_url = document.get("html_url") or url
        if document.get("encoding") == "base64":
            readme = base64.b64decode(document["content"]).decode("utf-8", errors="replace")[:40000]
    except (OSError, ValueError, KeyError):
        pass

    coverage = {}
    for endpoint, options in (("commits", {"per_page": 50, "since": since + "T00:00:00Z"}),
                              ("releases", {"per_page": 20})):
        try:
            coverage[endpoint] = github_api(api + "/" + endpoint, **options)
        except (OSError, ValueError):
            coverage[endpoint] = None
    signals = activity(coverage["commits"] or [])
    signals.update(
        repository_url=url, commits_url=url + "/commits", releases_url=url + "/releases",
        commit_sample_available=coverage["commits"] is not None,
        release_sample_available=coverage["releases"] is not None,
        created_at=repo["created_at"], pushed_at=repo.get("pushed_at"),
        topics=repo.get("topics", []), description=overview,
        releases=[{"date": item["published_at"], "url": item["html_url"],
                   "label": f"GitHub release {item.get('tag_name', '')}"}
                  for item in (coverage["releases"] or []) if item.get("published_at") and not item.get("draft")],
    )
    claims = detect_intent(overview, url) + detect_intent(readme, readme_url)
    founders = []
    for match in re.finditer(r"^\s*(?:[-*] )?(?:co-founder|founder)\s*:\s*"
                             r"([^\W\d_]+(?:[ '-][^\W\d_]+){1,5})[ \t]*$", readme, re.I | re.M):
        founders.append({"name": match[1], "role": "Founder (project README)",
                         "source_url": readme_url})
    match = re.search(r"\b(?:company|startup|team)\s+(?:is\s+)?(?:based|headquartered) in\s+("
                      + "|".join(EUROPE) + r")\b", readme, re.I)
    country = next((value for value in EUROPE if match and value.casefold() == match[1].casefold()), None)
    website = repo.get("homepage")
    risk = RISK.search(overview + "\n" + readme)
    flags = [{"reason": risk[0], "source_url": readme_url}] if risk else []
    return {
        "id": "github:" + name.lower(), "title": repo["name"], "description": overview,
        "project_url": website if urlsplit(website or "").scheme in {"http", "https"} else None,
        "source_url": url, "sources": [url], "source": "GitHub", "github_activity": signals,
        "links": {"github": [url]}, "claims": claims, "red_flags": flags, "founders": founders,
        "evidence": founder_history(repo["name"], [person["name"] for person in founders],
                                    readme.splitlines(), readme_url),
        "location": {"country": country, "confidence": "self_reported" if country else "unknown",
                     "source_url": readme_url if country else None},
        "timeline": [{"date": repo["created_at"], "url": url,
                      "label": "GitHub reports repository creation (public visibility at creation unverified)",
                      "public_signal": False}, *signals["releases"]],
    }


def discover_github(existing, limit, warnings=None):
    if not limit:
        return []
    warnings = warnings if warnings is not None else []
    today = datetime.now(timezone.utc).date()
    pushed = (today - timedelta(days=75)).isoformat()
    created = (today - timedelta(days=300)).isoformat()
    repos = {}
    for _, owner, repo in dict.fromkeys(key for lead in existing for key in repo_links(lead)):
        if len(repos) >= limit:
            break
        try:
            item = github_api(f"/repos/{owner}/{repo}")
        except (OSError, ValueError) as error:
            warnings.append(f"Linked repository unavailable ({type(error).__name__}).")
            continue
        if not item.get("private"):
            repos[item["full_name"].lower()] = item
    for keywords in ('"Germany" "early access"', '"Europe" "design partners"'):
        if len(repos) >= limit:
            break
        query = f"{keywords} in:readme created:>{created} pushed:>{pushed} fork:false archived:false"
        try:
            result = github_api("/search/repositories", q=query, sort="updated", per_page=min(5, (limit + 1) // 2))
        except (OSError, ValueError) as error:
            warnings.append(f"Repository search incomplete ({type(error).__name__}).")
            break
        for item in result["items"]:
            repos.setdefault(item["full_name"].lower(), item)
            if len(repos) >= limit:
                break
    records = []
    for item in repos.values():
        try:
            records.append(github_record(item, pushed))
        except (OSError, ValueError, KeyError) as error:
            warnings.append(f"Repository sample unavailable ({type(error).__name__}).")
    if any(not row["github_activity"]["commit_sample_available"]
           or not row["github_activity"]["release_sample_available"] for row in records):
        warnings.append("Some repository commit or release samples are unavailable.")
    return records


def university_lead():
    return {
        "id": "tum:exist-autonomous-trucks-20260806",
        "title": "Autonomous trucks project (team name undisclosed)",
        "description": "TUM recruitment announcement for a business co-founder on an autonomous-trucks project.",
        "source_url": EXIST, "sources": [EXIST], "source": "TUM public EXIST-related announcement",
        "location": {"country": "Germany", "confidence": "ecosystem", "source_url": EXIST},
        "claims": [
            {"type": "hiring", "text": "The team is recruiting a business co-founder.",
             "source_url": EXIST, "status": "verified"},
            {"type": "commercialization", "text": "The team says it is forming a startup and applying for EXIST.",
             "source_url": EXIST, "status": "verified"},
        ],
        "timeline": [{"date": "2026-08-06", "url": EXIST, "label": "Public call for a business co-founder"}],
    }


def origin(row):
    if row.get("location"):
        return row["location"]
    source = row.get("source")
    if row.get("id") == "tum:rapid-resilience":
        return {"country": "Germany", "confidence": "registry",
                "source_url": "https://www.companyhouse.de/Rapid-Resilience-GmbH-Maikammer"}
    if source in {"TUM Venture Labs", "Show HN"} and row.get("location_query"):
        return {"country": "Germany", "confidence": "ecosystem" if source == "TUM Venture Labs" else "self_reported",
                "source_url": row["source_url"]}
    return {"country": None, "confidence": "unknown", "source_url": None}


def score_candidate(claims, founders, activity_rows, earliest, funding, sources):
    verified = {item["type"] for item in claims if item["status"] == "verified"}
    cues = {item["type"] for item in claims} - verified
    commercial = {"incorporation", "launch", "waitlist", "pilot", "hiring", "accelerator", "commercialization"}
    technical = 8 * any(item["releases"] for item in activity_rows)
    technical += 7 * any(item["sustained_collaboration"] for item in activity_rows)
    technical += 5 * ("prototype" in verified | cues)
    return {
        "technical_execution": min(20, technical),
        "founder_team": min(15, 5 * len(founders) + 5 * ("domain_experience" in verified)),
        "commercialization": min(30, 8 * len(verified & commercial) + 3 * len(cues & commercial)),
        "early_stage": 0 if funding == "funded" else 5 * bool(earliest) + 5 * (funding == "no_funding_found"),
        "market_potential": min(15, 8 * ("customer_discovery" in verified) + 7 * ("pilot" in verified)
                                + 4 * ("pilot" in cues)),
        "evidence_quality": min(10, 2 * len({urlsplit(url).hostname for url in sources}) + 2 * bool(verified)
                                + 2 * bool(founders)),
    }


def early_founder_follow_up(rows):
    """A current, sourced venture team can merit a call before launch."""
    for row in rows:
        funding = row.get("funding") or {}
        reviews = funding.get("reviews", [])
        if (row.get("funding_status") in {"pre_seed_financing_reported", "seed_stage_reported"}
                or any(check.get("reported_as") == "pre_seed_financing_reported" for check in reviews)):
            return False
    for row in rows:
        signals = {item["signal"] for item in row.get("evidence", [])}
        sources = set(row.get("source_names") or [row.get("source")])
        if sources.intersection(PROGRAMME_SOURCES) and "Recent programme selection" in signals:
            return True
        if "TUM Venture Labs" in sources and "University team in formation" in signals:
            return True
        if "TU Berlin" in sources and {"Named team on university profile", "EXIST support"} <= signals:
            return True
        if (any(person.get("name") and person.get("source_url") for person in row.get("founders", []))
                and any(claim["type"] == "formation_intent" for claim in row.get("claims", []))):
            return True
    return False


def combine(rows):
    lead = {**rows[0]}
    claims = list({(item["type"], item["source_url"], item["status"]): item
                   for row in rows for item in row.get("claims", [])}.values())
    founders = list({item["name"]: item for row in rows for item in row.get("founders", [])
                     if item.get("source_url")}.values())
    milestones = {(event["date"], event["url"], event["label"]): event
                  for row in rows for event in row.get("timeline", [])}
    timeline = [milestones[key] for key in sorted(milestones)]
    earliest = next((event for event in timeline if event.get("public_signal", True)), None)
    entries = [row.get("funding", EMPTY_FUNDING) for row in rows]
    priority = {"unknown": 0, "no_funding_found": 1, "funded": 2}
    funding = {field: [item for entry in entries for item in entry.get(field, [])]
               for field in ("rounds", "reviews", "public_support")}
    funding["status"] = max((entry["status"] for entry in entries), key=priority.get)
    later_sources = {check["source_url"] for check in funding["reviews"]
                     if check.get("reported_as") == "seed_stage_reported" and check.get("source_url")}
    later_sources.update(row["funding_source"] for row in rows
                         if row.get("funding_status") == "seed_stage_reported" and row.get("funding_source"))
    later = bool(later_sources) or any(row.get("funding_status") == "seed_stage_reported" for row in rows)
    flags = [flag for row in rows for flag in row.get("red_flags", [])]
    flags.extend({"reason": "Seed-stage classification", "source_url": url}
                 for url in sorted(later_sources))
    flags.extend({"reason": "Standalone company intent unclear", "source_url": item["source_url"]}
                 for item in claims if item["type"] == "side_project")

    origins = [origin(row) for row in rows]
    locations = {place["country"] for place in origins if place["country"]}
    confidence = {"unknown": 0, "self_reported": 1, "ecosystem": 2, "registry": 3}
    location = max(origins, key=lambda place: confidence[place["confidence"]])
    if len(locations) > 1:
        location = {"country": None, "confidence": "conflicting", "source_url": None, "observations": origins}
    sources = sorted({url for row in rows for url in row.get("sources", [row["source_url"]])}
                     | {item["source_url"] for item in claims} | {item["source_url"] for item in founders}
                     | {item["url"] for item in timeline})
    activity_rows = []
    for row in rows:
        sample = row.get("github_activity", [])
        activity_rows.extend([sample] if isinstance(sample, dict) else sample)
    scores = score_candidate(claims, founders, activity_rows, earliest, funding["status"], sources)
    website = next((row["project_url"] for row in rows if row.get("project_url")
                    and (key := url_key(row["project_url"])) and key[0] == "website"), None)
    github = next((f"https://github.com/{key[1]}/{key[2]}" for row in rows for key in repo_links(row)), None)
    commercial = [item for item in claims if item["type"] in
                  {"incorporation", "launch", "waitlist", "pilot", "hiring", "accelerator", "commercialization"}]
    missing = [label for value, label in ((founders, "Verified founder names"), (website, "Official website"),
               (github, "Linked repository"), (earliest, "Dated public signal"),
               (location["country"], "European location evidence"),
               (funding["status"] != "unknown", "Funding check"),
               (scores["market_potential"], "Customer or market validation")) if not value]
    filters = []
    if funding["status"] == "funded" or later:
        filters.append("funded_or_later_stage")
    if flags and not later:
        filters.append("project_intent_risk")
    if location["country"] not in EUROPE:
        filters.append("location_outside_scope_or_unverified")
    if not commercial and not early_founder_follow_up(rows):
        filters.append("no_commercialization_evidence")

    primary_source = next((row.get("source") for row in rows if row.get("source")), None)
    evidence = {
        (item["signal"], item["excerpt"], item.get("source_url") or row["source_url"]):
            {**item, "source_url": item.get("source_url") or row["source_url"]}
        for row in rows for item in row.get("evidence", [])
    }
    lead.update(
        source=primary_source, source_names=list(dict.fromkeys(row["source"] for row in rows if row.get("source"))),
        evidence=list(evidence.values()),
        description=next((row["description"] for row in rows if row.get("description")), None),
        sector=next((row["sector"] for row in rows if row.get("sector")), None),
        team=next((row["team"] for row in rows if row.get("team")), None),
        official_website=website, github_url=github, sources=sources, founders=founders, location=location,
        timeline=timeline, earliest_verified_public_signal=earliest, github_activity=activity_rows,
        commercialization_signals=commercial, funding=funding, emergence_dimensions=scores,
        founder_emergence_score=sum(scores.values()), evidence_confidence=scores["evidence_quality"],
        reasons_to_investigate=[item for item in claims if item["status"] == "verified" or item in commercial],
        missing_information=missing, red_flags=flags, shortlist_exclusions=filters,
    )
    return lead


def rank_candidates(rows, limit, *, github_count=0, source_status=None, mode="live"):
    generated_at = datetime.now(timezone.utc)
    candidates = [combine(group) for group in merge_candidates(rows)]
    candidates.sort(
        key=lambda lead: review_priority(lead["location"]["country"],
                                         evaluate([lead], generated_at.date())["score"],
                                         lead["founder_emergence_score"]),
        reverse=True,
    )
    shortlist = [lead for lead in candidates if not lead["shortlist_exclusions"]][:min(10, limit)]
    return {
        "schema_version": 1,
        "mode": mode,
        "generated_at": generated_at.isoformat(),
        "source_status": source_status or {},
        "github_repositories_reviewed": github_count,
        "shortlist": shortlist,
        "manual_review": [lead["id"] for lead in shortlist[:3]],
        "candidates": candidates,
    }


def main():
    # Import at the entry point so the shared scorer is also callable by Streamlit.
    from discovery_pipeline import run_discovery

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-limit", type=int, choices=range(0, 11), default=5)
    parser.add_argument("--limit", type=positive_int, default=10)
    parser.add_argument("--days", type=positive_int, default=365, help="Show HN lookback window")
    parser.add_argument("--tu-berlin", action="store_true", help="Include the TU Berlin directory")
    parser.add_argument("--search-funding", action="store_true", help="Enable the optional Brave funding check")
    args = parser.parse_args()
    key = os.getenv("BRAVE_SEARCH_API_KEY") if args.search_funding else None
    if args.search_funding and not key:
        parser.error("--search-funding requires BRAVE_SEARCH_API_KEY")
    sources = DISCOVERY_SOURCES if args.tu_berlin else tuple(name for name in DISCOVERY_SOURCES if name != "TU Berlin")
    run = run_discovery(sources, args.days, github_limit=args.github_limit, limit=args.limit, api_key=key)
    print(json.dumps(run, ensure_ascii=False, indent=2))
    return int(all(status["state"] == "error" for status in run["source_status"].values()))


if __name__ == "__main__":
    sys.exit(main())
