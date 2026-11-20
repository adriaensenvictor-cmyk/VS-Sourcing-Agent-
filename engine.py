"""Hidden Gem: evidence-first startup sourcing for the HTGF challenge.

Live adapters: TU Berlin university ventures, Show HN, GitHub.
All sources are public. Unknown funding status is never treated as proof of no VC funding.
Python >= 3.10; requests and beautifulsoup4 required.
"""
from __future__ import annotations

import html
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "HiddenGem-MAINHackathon/0.1 (public startup research)"}
CAMPUS_URL = "https://www.tu.berlin/entrepreneurship/startup-support/tu-startups"
GERMAN_LOCATIONS = (
    "germany", "deutschland", "berlin", "münchen", "munich", "hamburg",
    "köln", "cologne", "frankfurt", "stuttgart", "aachen", "bonn",
    "dresden", "karlsruhe", "darmstadt", "leipzig", "heidelberg",
    "nuremberg", "nürnberg", "erlangen", "freiburg", "bremen",
    "hannover", "göttingen", "potsdam", "jena", "düsseldorf",
    "dortmund", "bochum", "essen", "wuppertal", "ulm", "tübingen",
)
NOISE = re.compile(
    r"\b(homework|course assignment|school assignment|university assignment|"
    r"tutorial project|coding challenge|weekend project|just for fun|"
    r"web agency|marketing agency|consulting agency|portfolio website)\b", re.I
)
PILOT = re.compile(r"\b(pilot|design partner|paying customer|first customer|"
                   r"customer deployment|paid trial|commercial trial|enterprise trial)\b", re.I)
TEAM = re.compile(r"\b(co[- ]founder|founding team|our team|we are a team)\b", re.I)
RESEARCH = re.compile(r"\b(research|phd|university|patent|spin[- ]off|"
                      r"exist.gr.ndungsstipendium|science-based|tapeout)\b", re.I)
PRODUCT = re.compile(r"\b(prototype|mvp|beta|launched|demo|api|software|"
                     r"hardware|robot|semiconductor|platform|tool)\b", re.I)
BUSINESS = re.compile(r"\b(pricing|customers|subscription|b2b|enterprise|"
                      r"commercial|sales|industry|industrial|manufactur)\b", re.I)
SECTORS = [
    ("Industrial / Deep Tech", re.compile(r"semiconductor|eda|robotic|industrial|"
       r"manufactur|chip design|automation|materials|quantum|satellite", re.I)),
    ("Climate / Energy", re.compile(r"climate|energy|renewable|battery|carbon|"
       r"biodivers|geospatial|hydrogen|solar|electricity|grid", re.I)),
    ("Life Sciences", re.compile(r"biotech|medtech|protein|drug discovery|"
       r"medical|diagnostic|life science", re.I)),
    ("Digital Tech", re.compile(r"\b(ai|agents?|software|saas|api|cybersecurity|"
       r"machine learning|developer tools?|data platform)\b", re.I)),
]
GITHUB_QUERIES = ("semiconductor automation", "industrial robotics", "climate software")


def utcnow():
    return datetime.now(timezone.utc)


def get_json(url, params=None, token=None, timeout=12):
    headers = dict(HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.get(url, params=params, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def get_html(url, timeout=12):
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def german_location(value):
    value = (value or "").lower()
    return any(re.search(r"(?<!\w)" + re.escape(city) + r"(?!\w)", value)
               for city in GERMAN_LOCATIONS)


def sector(text):
    for name, pattern in SECTORS:
        if pattern.search(text or ""):
            return name
    return "Other / Review"


def evidence(signal, excerpt, url, observed_at=None):
    return {"signal": signal, "excerpt": str(excerpt)[:300],
            "url": url, "observed_at": observed_at}


def candidate(uid, name, origin, url, description, location="", team="",
              published_at=None, project_url=None, evidence_items=None,
              founder_identified=False, mode="live", cohort=None):
    result = {
        "id": uid, "name": name[:150], "origin": origin, "source_url": url,
        "project_url": project_url or url, "description": description[:2500],
        "location": location or "Needs verification", "team": team,
        "first_observed_at": published_at, "cohort": cohort,
        "sector": sector(name + " " + description), "founder_identified": founder_identified,
        "mode": mode, "funding_status": "Unknown — requires independent diligence",
        "evidence": evidence_items or [], "warnings": [],
        "score": 0, "score_components": {},
    }
    return score_candidate(result)


def score_candidate(lead):
    """Transparent prioritization heuristic; NOT a probability of success."""
    text = " ".join((lead.get("name", ""), lead.get("description", ""),
                     lead.get("team", "")))
    score = {"base": 10}
    warnings = []
    if german_location(lead.get("location", "")):
        score["verified German location"] = 16
    else:
        warnings.append("German operating base requires independent verification")
    if lead.get("founder_identified"):
        score["named team"] = 18
    elif TEAM.search(text):
        score["founder-language clue"] = 5
        warnings.append("Founder identities are not independently established")
    else:
        warnings.append("Project owner may not be a startup founder")
    if lead.get("sector") != "Other / Review":
        score["HTGF technology fit"] = 12
    if PRODUCT.search(text):
        score["product or prototype clue"] = 8
    if BUSINESS.search(text):
        score["commercial intent clue"] = 7
    if PILOT.search(text):
        score["pilot or customer language"] = 10
    if RESEARCH.search(text):
        score["applied research clue"] = 7
    if any(x.get("signal") == "EXIST support" for x in lead.get("evidence", [])):
        score["university venture support"] = 8
    stamp = lead.get("first_observed_at")
    if stamp:
        try:
            days = (utcnow() - datetime.fromisoformat(stamp.replace("Z", "+00:00"))).days
            if 0 <= days <= 180:
                score["recent public trace"] = 7
        except (ValueError, TypeError):
            pass
    if NOISE.search(text):
        score["hobby / agency / assignment risk"] = -35
        warnings.append("Noise filter: hobby, agency or assignment language")
    if not lead.get("founder_identified"):
        warnings.append("Confirm whether this is a venture-backed-startup candidate")
    warnings.append("No automated proof of absent funding; check funding databases manually")
    raw = max(0, min(100, sum(score.values())))
    lead["score"] = min(raw, 68) if not lead.get("founder_identified") else raw
    lead["score_components"] = score
    lead["warnings"] = warnings
    lead["lead_status"] = ("Team identified; needs diligence" if
                           lead.get("founder_identified") else "Project lead; verify startup status")
    return lead


def scan_hackernews(days=180, cities=("Berlin", "Munich"), per_city=80):
    """Search Show HN; require explicitly stated place in the post body."""
    leads = []
    cutoff = int((utcnow() - timedelta(days=days)).timestamp())
    for city in cities:
        data = get_json("https://hn.algolia.com/api/v1/search_by_date", {
            "query": city, "tags": "show_hn", "hitsPerPage": min(per_city, 100),
            "numericFilters": f"created_at_i>{cutoff}",
        })
        for post in data.get("hits", []):
            title = post.get("title") or ""
            if not title.lower().startswith("show hn:"):
                continue
            body = html.unescape(re.sub(r"<[^>]+>", " ", post.get("story_text") or ""))
            body = " ".join(body.split())
            # A mere mention of the city is not proof of team location.
            location_re = re.compile(
                r"(?:based|located|living|working|building)\s+(?:in|out of)\s+"
                + re.escape(city) + r"\b", re.I
            )
            match = location_re.search(body)
            if not match or NOISE.search(title + " " + body):
                continue
            uid = str(post.get("objectID", ""))
            if not uid:
                continue
            hn_url = f"https://news.ycombinator.com/item?id={uid}"
            ev = [evidence("Self-reported location", body[max(0, match.start()-45):match.end()+50], hn_url, post.get("created_at"))]
            for label, regex in (("Founder language", TEAM), ("Pilot/customer", PILOT),
                                 ("Product trace", PRODUCT), ("Commercial intent", BUSINESS)):
                m = regex.search(body)
                if m:
                    ev.append(evidence(label, body[max(0, m.start()-35):m.end()+45],
                                       hn_url, post.get("created_at")))
            leads.append(candidate("hn:" + uid, title[8:].strip(), "Hacker News",
                        hn_url, body, city + ", Germany", published_at=post.get("created_at"),
                        project_url=post.get("url"), evidence_items=ev))
    return deduplicate(leads)


def scan_github(days=365, limit=24, token=None):
    """Recent technical projects with a German owner profile; not all are startups."""
    since = (utcnow() - timedelta(days=days)).date().isoformat()
    token = token or os.environ.get("GITHUB_TOKEN")
    results, seen, profiles = [], set(), {}
    for term in GITHUB_QUERIES:
        query = f'"{term}" in:name,description created:>={since} fork:false'
        response = get_json("https://api.github.com/search/repositories",
                    {"q": query, "sort": "updated", "order": "desc", "per_page": 15}, token)
        for item in response.get("items", []):
            key = item.get("full_name")
            if not key or key in seen or item.get("fork") or item.get("archived"):
                continue
            seen.add(key)
            owner = item.get("owner") or {}
            login = owner.get("login")
            if not login:
                continue
            if login not in profiles:
                profiles[login] = get_json(f"https://api.github.com/users/{login}", token=token)
            owner_data = profiles[login]
            owner_location = owner_data.get("location") or ""
            combined = " ".join([item.get("description") or "", owner_data.get("bio") or ""])
            if not german_location(owner_location):
                continue
            url = item["html_url"]
            ev = [evidence("Owner profile location", owner_location,
                           owner_data.get("html_url") or url, item.get("created_at")),
                  evidence("Public code artifact", item.get("description") or item.get("name"),
                           url, item.get("created_at"))]
            results.append(candidate("github:" + key, item.get("name", key),
                        "GitHub", url, combined, owner_location,
                        published_at=item.get("created_at"), project_url=url,
                        evidence_items=ev))
            if len(results) >= limit:
                return deduplicate(results)
    return deduplicate(results)


def scan_campus(max_profiles=12):
    """Discover TU Berlin 2026 ventures from links on the university directory.

    Do not fabricate results if TU Berlin blocks automated requests.
    2026 is the university listing cohort, not an independently verified founding date.
    """
    soup = get_html(CAMPUS_URL)
    links = {}
    for link in soup.select('a[href*="startups-2026-"]'):
        href = urljoin(CAMPUS_URL, link.get("href", ""))
        if "tu.berlin/" in href and "startups-2026-" in href:
            links[href] = True
    leads = []
    for url in list(links)[:max_profiles]:
        try:
            page = get_html(url)
        except requests.RequestException:
            continue
        h1 = page.find("h1")
        name = h1.get_text(" ", strip=True) if h1 else url.rsplit("-", 1)[-1].title()
        for t in page(["script", "style", "nav", "footer"]):
            t.decompose()
        body = " ".join(page.get_text(" ", strip=True).split())
        if NOISE.search(name):
            continue
        # Site profiles explicitly expose the "Team:" and "Förderung:" sections.
        match = re.search(r"\bTeam:\s*(.{4,260}?)\s*(?:Branche:|Mentor:|Fakultät:|Förderung:)", body, re.I)
        team = match.group(1)[:230] if match else ""
        grant = re.search(r"\bEXIST[- ](?:Gründungsstipendium|Gründerstipendium)\b", body, re.I)
        ev = [evidence("University startup directory (2026 cohort)", name,
                       url)]
        if team:
            ev.append(evidence("Named team on university profile", team, url))
        if grant:
            ev.append(evidence("EXIST support", grant.group(0) + " (public grant, not a VC round)", url))
        leads.append(candidate("campus:" + url.rsplit("/", 1)[-1], name,
                    "TU Berlin", url, body[:1800], "Berlin, Germany",
                    team=team, evidence_items=ev, founder_identified=bool(team),
                    cohort="University listing: 2026"))
    return deduplicate(leads)


def canonical_github(url):
    try:
        parsed = urlparse(url or "")
        if parsed.netloc.lower() not in ("github.com", "www.github.com"):
            return None
        parts = [p.lower() for p in parsed.path.split("/") if p]
        if len(parts) >= 2:
            return "/".join(parts[:2])
    except ValueError:
        pass
    return None


def deduplicate(leads):
    result = {}
    for lead in leads:
        key = canonical_github(lead.get("project_url")) or lead.get("id")
        if key in result:
            prev = result[key]
            urls = {e.get("url") for e in prev["evidence"]}
            prev["evidence"] += [e for e in lead["evidence"] if e.get("url") not in urls]
            if lead.get("founder_identified"):
                prev["founder_identified"] = True
                prev["team"] = lead.get("team") or prev.get("team", "")
            prev["origin"] = prev["origin"] + " + " + lead["origin"]
            score_candidate(prev)
        else:
            result[key] = lead
    return sorted(result.values(), key=lambda x: x["score"], reverse=True)


def run_live(sources=("Campus", "Hacker News", "GitHub"), days=180, token=None):
    leads, errors = [], []
    jobs = (("Campus", lambda: scan_campus()),
            ("Hacker News", lambda: scan_hackernews(days=days)),
            ("GitHub", lambda: scan_github(days=max(180, days), token=token)))
    for name, fn in jobs:
        if name not in sources:
            continue
        try:
            leads.extend(fn())
        except (requests.RequestException, ValueError, KeyError) as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
    return deduplicate(leads), errors


def load_research_snapshot(filename="data/research_snapshot.json"):
    """Research samples are not falsely represented as an automated live scan."""
    with open(filename, encoding="utf-8") as f:
        rows = json.load(f)
    leads = []
    for row in rows:
        ev = [evidence(x["signal"], x["excerpt"], x["url"], x.get("observed_at"))
              for x in row["evidence"]]
        leads.append(candidate(row["id"], row["name"], "Verified research snapshot",
                    row["source_url"], row["description"], row["location"],
                    team=row["team"], project_url=row.get("project_url"),
                    evidence_items=ev, founder_identified=True,
                    mode="research snapshot", cohort=row.get("cohort")))
    return deduplicate(leads)
