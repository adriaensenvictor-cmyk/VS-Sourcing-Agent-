"""Evidence and identity rules for the sourcing radar."""

import json
import re
from datetime import date
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

RAPID = "https://www.tum-venture-labs.de/teams/rapid-resilience/"
RAPID_REGISTER = "https://www.companyhouse.de/Rapid-Resilience-GmbH-Maikammer"

REVIEWS = {
    "tum:rapid-resilience": {
        "founders": [{"name": "Jan Boeckmann", "role": "Founder", "source_url": RAPID,
                      "linkedin_url": "https://de.linkedin.com/in/jan-boeckmann-29a84b191"}],
        "milestones": [{"date": "2026-09-22", "label": "Company registration published",
                        "url": RAPID_REGISTER}],
        "claims": [
            ("incorporation", "Rapid Resilience GmbH is listed as registered.", RAPID_REGISTER),
            ("customer_discovery", "The founder interviewed municipalities about flood mitigation.", RAPID),
            ("domain_experience", "The founder researched flood mitigation during his TUM doctorate.", RAPID),
        ],
        "funding_review": {
            "checked_on": "2026-11-20",
            "outcome": "no_funding_found",
            "queries": [
                '"Rapid Resilience" "Jan Boeckmann" Finanzierung VC funding seed round investment',
                '"Rapid Resilience" "Jan Boeckmann" investor fundraising startup round',
            ],
            "sources": [RAPID, RAPID_REGISTER, "https://rapid-resilience.de/"],
            "scope": "Public search for a disclosed external investment round. Coverage is incomplete.",
        },
    },
    "tum:foresaight-ai": {
        "founders": [
            {"name": "Julian Gruber", "role": "Co-founder", "source_url": "https://www.foresaight.ai/de/imprint"},
            {"name": "Laura Mati", "role": "Co-founder", "source_url": "https://ch.linkedin.com/in/laura-mati-198a2858",
             "linkedin_url": "https://ch.linkedin.com/in/laura-mati-198a2858"},
        ],
        "claims": [("incorporation", "The company imprint identifies foresAIght.ai GmbH.",
                    "https://www.foresaight.ai/de/imprint")],
    },
}

SIGNALS = {
    "Academic origin": "domain_experience",
    "Founding team": "team",
    "Team signal mentioned": "team",
    "Product validation": "pilot",
    "Prototype or launch mentioned": "prototype",
    "Standalone company intent unclear": "side_project",
}

# Conservative cues. Text matches are hypotheses until reviewed.
INTENT_PATTERNS = {
    "incorporation": r"\b(?:incorporated|registered (?:our|the) company)\b",
    "launch": r"\b(?:we launched|now available|public beta|went live)\b",
    "waitlist": r"\b(?:join (?:our|the) (?:waitlist|waiting list)|sign up for early access)\b",
    "pilot": r"\b(?:pilot customers?|paying customers?|signed (?:our|a) pilot)\b",
    "hiring": r"\b(?:we(?:'re| are) hiring|open positions)\b",
    "accelerator": r"\b(?:accepted into|joined)\b.{0,45}\b(?:accelerator|incubator)\b",
    "commercialization": r"\b(?:go.to.market|commercial launch|licensing agreement|paid plans?)\b",
    "prototype": r"\b(?:working prototype|research.validated prototype|pre.alpha|proof.of.concept)\b",
}


def url_key(url):
    parts = urlsplit(url or "")
    host = (parts.hostname or "").lower().removeprefix("www.")
    path = parts.path.strip("/")
    if parts.scheme not in {"https", "http"} or not host:
        return None
    if host == "github.com":
        components = path.lower().split("/")
        if len(components) >= 2:
            return ("github", components[0], components[1].removesuffix(".git"))
        return None
    if host in {"linkedin.com", "medium.com", "youtube.com", "news.ycombinator.com", "tum-venture-labs.de"} or host.endswith(".linkedin.com"):
        return None
    return ("website", host, path)


def merge_candidates(leads):
    """Join records on exact project URLs or GitHub repository identity."""
    groups = []
    for lead in leads:
        github = lead.get("links", {}).get("github", [])
        keys = {key for url in [lead.get("project_url"), *github] if (key := url_key(url))}
        matches = [group for group in groups if keys & group[0]]
        group = (keys, [lead])
        for other in matches:
            keys.update(other[0])
            group[1].extend(other[1])
            groups.remove(other)
        groups.append(group)
    return [records for _, records in groups]


def claim(kind, text, url, status):
    return {"type": kind, "text": text, "source_url": url, "status": status}


def detect_intent(text, url):
    signals = []
    for kind, pattern in INTENT_PATTERNS.items():
        match = re.search(pattern, text, re.I)
        if match:
            excerpt = text[max(0, match.start() - 65):match.end() + 65]
            signals.append(claim(kind, excerpt, url, "hypothesis"))
    return signals


def github_release_events(records):
    repositories = set()
    for record in records:
        for url in [record.get("project_url"), *record.get("links", {}).get("github", [])]:
            key = url_key(url)
            if key and key[0] == "github":
                repositories.add(key[1:])
    events = []
    for owner, repo in sorted(repositories)[:3]:
        endpoint = f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/releases?per_page=30"
        try:
            request = Request(endpoint, headers={"Accept": "application/vnd.github+json",
                                                 "User-Agent": "Victor-Startup-Sourcing/1.0"})
            with urlopen(request, timeout=5) as response:
                releases = json.load(response)
        except (OSError, ValueError):
            continue
        for release in releases:
            if release.get("published_at") and release.get("html_url") and not release.get("draft"):
                events.append({"date": release["published_at"], "url": release["html_url"],
                               "label": f"GitHub release {release.get('tag_name', '')}".strip()})
    return events



def public_funding_search(record, api_key):
    name = re.split(r" [–—] |, ", record["title"], maxsplit=1)[0]
    queries = [f'"{name}" funding raised investment round', f'"{name}" Finanzierung Finanzierungsrunde']
    checked = {"checked_on": date.today().isoformat(), "queries": queries, "sources": [],
               "scope": "Brave web index, up to ten results per query; coverage is incomplete.",
               "outcome": "unknown"}
    for query in queries:
        endpoint = "https://api.search.brave.com/res/v1/web/search?" + urlencode({"q": query, "count": 10})
        request = Request(endpoint, headers={"X-Subscription-Token": api_key, "Accept": "application/json"})
        try:
            with urlopen(request, timeout=8) as response:
                result = json.load(response)
            if result.get("type") != "search":
                return checked
            if result.get("web", {}).get("results", []):
                return checked | {"sources": list(dict.fromkeys(
                    hit["url"] for hit in result["web"]["results"] if hit.get("url")
                )), "scope": checked["scope"] + " Search hits require human review."}
        except (OSError, ValueError):
            return checked
    checked["outcome"] = "no_funding_found"
    return checked


def qualify(records, release_events=(), search_review=None):
    lead = dict(records[0])
    claims, founders, timeline, reviews, grants, rounds = [], [], [], [], [], []
    sources, linkedin = [], []
    evidence = []
    links = {"github": [], "linkedin": []}
    for record in records:
        url = record["source_url"]
        review = REVIEWS.get(record["id"], {})
        sources.append(url)
        for platform in links:
            links[platform].extend(record.get("links", {}).get(platform, []))
        for field in ("project_url", "description", "sector", "team", "cohort"):
            if not lead.get(field) and record.get(field):
                lead[field] = record[field]
        key = url_key(record.get("project_url"))
        if key and key[0] == "github":
            links["github"].append(record["project_url"])
        linkedin.extend(record["linkedin"]["public_links"])
        evidence.extend({**item, "source_url": url} for item in record["evidence"])
        founders.extend(person for person in record.get("founders", []) if person.get("name") and person.get("source_url"))
        founders.extend(review.get("founders", []))
        if record.get("founder") and not review.get("founders") and record.get("profile"):
            founders.append({"name": record["founder"], "role": "Founder",
                             "source_url": record["profile"], "linkedin_url": record["profile"]})
        for kind, text, source in review.get("claims", []):
            claims.append(claim(kind, text, source, "verified"))
        for item in record["evidence"]:
            text = item["excerpt"]
            kind = SIGNALS.get(item["signal"])
            if kind:
                claims.append(claim(kind, text, url, "hypothesis"))
            for signal, pattern in INTENT_PATTERNS.items():
                if signal != kind and re.search(pattern, text, re.I):
                    claims.append(claim(signal, text, url, "hypothesis"))
        claims.extend(record.get("intent_cues", []))
        timeline.extend(record.get("milestones", []))
        timeline.extend(review.get("milestones", []))
        funding = record.get("funding_status")
        funding_url = record.get("funding_source")
        if funding_url and funding in {"vc_round_reported", "seed_stage_reported", "pre_seed_financing_reported"}:
            check = {"source_url": funding_url, "reported_as": funding}
            # A stage label or unspecified pre-seed financing alone does not establish an equity round.
            (rounds if funding == "vc_round_reported" else reviews).append(check)
        if funding_url and funding in {"grant_reported", "public_support_reported"}:
            grants.append({"source_url": funding_url, "reported_as": funding})
        check = review.get("funding_review")
        if check:
            reviews.append(check)

    if search_review:
        reviews.append(search_review)
    status = "funded" if rounds else "unknown"
    if not rounds and any(review.get("outcome") == "no_funding_found" for review in reviews):
        if not any(review.get("reported_as") for review in reviews):
            status = "no_funding_found"

    timeline.extend(release_events)
    entries = {}
    for event in timeline:
        try:
            value = event["date"]
            normalized = date.fromisoformat(value[:10]) if len(value) >= 10 else date(int(value), 1, 1)
        except (KeyError, TypeError, ValueError):
            continue
        if event.get("url"):
            entries[(normalized, event["url"], event["label"])] = event
    timeline = [entries[key] for key in sorted(entries)]
    first = next(iter(timeline), None)

    founder_names = {person["name"]: person for person in founders}
    verified = {item["type"] for item in claims if item["status"] == "verified"}
    kinds = {item["type"] for item in claims}
    dimensions = {
        "founder_quality": min(5, 2 * bool(founder_names) + 2 * ("domain_experience" in verified) + ("team" in kinds)),
        "entrepreneurial_intent": min(5, 2 * len(verified & INTENT_PATTERNS.keys()) +
                                      len((kinds - verified) & INTENT_PATTERNS.keys())),
        "commercial_potential": min(5, 2 * ("customer_discovery" in verified) + 2 * ("pilot" in kinds) +
                                    bool(kinds & {"launch", "waitlist", "commercialization"})),
        "earliness": 0 if status == "funded" else min(5, 2 * bool(first) + 2 * (status == "no_funding_found") +
                                                     ("prototype" in kinds)),
        "evidence_confidence": min(5, len(set(sources)) + len({item["source_url"] for item in claims
                                                               if item["status"] == "verified"}) +
                                   bool(founder_names)),
    }
    lead.update(
        sources=list(dict.fromkeys(sources)), links={key: list(dict.fromkeys(urls)) for key, urls in links.items()},
        evidence=evidence, claims=list({(item["type"], item["source_url"], item["status"]): item for item in claims}.values()),
        founders=list(founder_names.values()), timeline=timeline, earliest_verified_public_signal=first,
        funding={"status": status, "rounds": rounds, "public_support": grants, "reviews": reviews},
        scores=dimensions, score=sum(dimensions.values()), score_breakdown=dimensions,
    )
    lead["linkedin"] = {**lead["linkedin"], "public_links": list(dict.fromkeys(linkedin))}
    if len(records) > 1:
        lead["source_record_urls"] = list(dict.fromkeys(sources))
    observations = [item for record in records for item in record.get("fit_evidence", [])]
    if observations:
        lead["fit_evidence"] = observations
    return lead
