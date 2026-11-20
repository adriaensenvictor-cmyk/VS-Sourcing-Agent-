"""Bounded, public Show HN queries for European ventures and former operators."""
import argparse
import html
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from qualification import detect_intent, url_key
from sourcing import positive_int

SOURCE = "European launches & alumni (Show HN)"
EMPLOYERS = ("Goldman Sachs", "Jane Street", "Citadel Securities", "Citadel", "OpenAI", "Anthropic")
PLACES = {"Berlin": "Germany", "Munich": "Germany", "Paris": "France", "London": "United Kingdom",
          "Amsterdam": "Netherlands", "Zurich": "Switzerland", "Stockholm": "Sweden",
          "Helsinki": "Finland", "Warsaw": "Poland", "Madrid": "Spain", "Vienna": "Austria"}
PLACES.update({country: country for country in list(PLACES.values())})
COUNTRIES = {place.casefold(): country for place, country in PLACES.items()}
PLACE = "|".join(map(re.escape, sorted(PLACES, key=len, reverse=True)))
ORG = "|".join(map(re.escape, EMPLOYERS))
BASE = re.compile(r"\b(?:(?:we(?: are|'re)|our (?:company|startup|team) is)"
                  r"(?: a (?:small |new )?(?:\w+ ){0,2}(?:firm|team|startup|company))?"
                  r" (?:based|headquartered) in (?P<after>" + PLACE + r")"
                  r"|we(?: are|'re) a (?P<before>" + PLACE + r")[- ]based (?:\w+ ){0,2}(?:team|startup|company))\b", re.I)
FORMER = re.compile(r"\b(?:I (?:left|used to work (?:at|for)|previously worked (?:at|for)|"
                    r"formerly worked (?:at|for))|I(?: am|'m) (?:an? )?(?:former (?:\w+ ){1,3}at|ex-)|"
                    r"(?:(?<=^)|(?<=[.!?] ))Previously (?:I )?(?:used to work|worked) at)"
                    r"\s*(?P<employer>" + ORG + r")\b", re.I)
BUILT = re.compile(r"\b(?:I|we)(?:'ve| have)? (?:just )?(?:built|created|developed|launched|started|"
                   r"(?:have |'ve )?been building|(?:am|are) building)\b", re.I)
SOURCE_URL = "https://news.ycombinator.com/item?id="
# The model-provider names alone mostly find API users. Query the departure wording.
QUERIES = ("Goldman Sachs", "Jane Street", "Citadel", "left OpenAI", "left Anthropic",
           "previously worked at OpenAI", "previously worked at Anthropic", "ex-OpenAI", "ex-Anthropic",
           "Berlin", "Munich", "London", "Paris", "Amsterdam", "Zurich", "Stockholm", "Helsinki", "Warsaw", "Madrid", "Vienna")


def search(**params):
    url = "https://hn.algolia.com/api/v1/search_by_date?" + urlencode(params)
    with urlopen(Request(url, headers={"User-Agent": "FirstTrace/1.0"}), timeout=6) as response:
        return json.load(response)["hits"]


def post_body(post):
    return " ".join(html.unescape(re.sub("<[^>]+>", " ", post.get("story_text") or "")).split()).replace("’", "'")


def project_link(post):
    url = post.get("url") or ""
    try:
        parsed = urlsplit(url)
        if parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username:
            return url
    except ValueError:
        pass
    return None


def post_date(post):
    try:
        value = datetime.fromisoformat(post["created_at"].replace("Z", "+00:00"))
    except (KeyError, ValueError, AttributeError):
        return None
    return value if value.tzinfo else None


def location_in(body, source):
    matches = list(BASE.finditer(body))
    countries = {COUNTRIES[(m["before"] or m["after"]).casefold()]
                 for m in matches}
    if len(countries) == 1:
        return {"country": countries.pop(), "confidence": "self_reported", "source_url": source,
                "excerpt": matches[0][0]}
    return {"country": None, "confidence": "unknown", "source_url": source if matches else None,
            "excerpt": " / ".join(m[0] for m in matches) or None}


def candidate(post):
    title = post.get("title") or ""
    uid = str(post.get("objectID") or "")
    author = post.get("author") or ""
    if not title.lower().startswith("show hn:") or not uid.isdigit() or not re.fullmatch(r"[\w-]{1,32}", author):
        return None
    url = SOURCE_URL + uid
    body = post_body(post)
    former = FORMER.search(body)
    location = location_in(body, url)
    if not (former or location["country"]) or not post_date(post) or not BUILT.search(body):
        return None
    evidence = []
    if former:
        employer = next(e for e in EMPLOYERS if e.casefold() == former["employer"].casefold())
        evidence.append({"kind": "former_employer", "subject": author, "name": employer, "text": former[0],
                         "source_url": url, "status": "author_self_report", "date": post["created_at"]})
    cues = detect_intent(body, url)
    if re.search(r"\b(?:we (?:raised|closed)|our (?:seed|series [a-e]) round)\b", body, re.I):
        flags = [{"reason": "Possible disclosed financing · verify before pre-round outreach", "source_url": url}]
    else:
        flags = []
    return {"id": uid, "title": title.split(":", 1)[1].strip(), "source": SOURCE, "source_url": url,
            "sources": [url], "project_url": project_link(post), "description": body[:350], "location": location,
            "claims": cues, "funding_status": "unknown", "hn_author": author, "career_evidence": evidence, "red_flags": flags,
            "timeline": [{"date": post["created_at"], "label": "Show HN publication", "url": url}]}


def previous_projects(row):
    stamp = datetime.fromisoformat(row["timeline"][0]["date"].replace("Z", "+00:00"))
    author = row["hn_author"]
    posts = search(tags=f"show_hn,author_{author}", hitsPerPage=20, numericFilters=f"created_at_i<{int(stamp.timestamp())}")
    seen_urls = {url_key(row.get("project_url"))}
    seen_names = {row["title"].casefold()}
    prior = []
    for post in posts:
        title = post.get("title") or ""
        uid = str(post.get("objectID") or "")
        url = project_link(post)
        if post.get("author") != author or not uid.isdigit() or not title.lower().startswith("show hn:"):
            continue
        name = title.split(":", 1)[1].strip()
        body = post_body(post)
        built = BUILT.search(body)
        published = post_date(post)
        key = url_key(url)
        if (not key or key in seen_urls or name.casefold() in seen_names or not built
                or published is None or published >= stamp or uid == row["id"]):
            continue
        seen_urls.add(key)
        seen_names.add(name.casefold())
        prior.append({"kind": "prior_project", "name": name, "subject": author,
                      "status": "same_account_self_report", "source_url": SOURCE_URL + uid, "project_url": url,
                      "text": body[max(0, built.start()-12):built.end()+110], "date": post.get("created_at")})
        if len(prior) == 3:
            break
    return prior


def discover(warnings, days=365):
    cutoff = int(datetime.now(timezone.utc).timestamp()) - days * 86400
    rows = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = [pool.submit(search, query=query, tags="show_hn", hitsPerPage=100,
                            numericFilters=f"created_at_i>{cutoff}", typoTolerance="false") for query in QUERIES]
        successful = 0
        for job in jobs:
            try:
                posts = job.result()
                successful += 1
            except (OSError, ValueError, KeyError):
                warnings.append("Some founder or regional queries were unavailable.")
                continue
            for post in posts:
                row = candidate(post)
                if row:
                    rows[row["id"]] = row
    if not successful:
        raise OSError("No successful Show HN search")
    ordered = sorted(rows.values(), key=lambda r: (bool(r["career_evidence"]), r["timeline"][0]["date"]), reverse=True)
    for row in ordered[:6]:
        try:
            row["career_evidence"].extend(previous_projects(row))
        except (OSError, ValueError, KeyError):
            warnings.append("Some author project histories were unavailable.")
    return ordered


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=positive_int, default=365)
    args = parser.parse_args()
    warnings = []
    status = "ok"
    try:
        rows = discover(warnings, args.days)
        if warnings:
            status = "partial"
    except OSError:
        rows = []
        status = "error"
        warnings.append("Show HN searches unavailable.")
    print(json.dumps({"source": SOURCE, "status": status, "generated_at": datetime.now(timezone.utc).isoformat(),
                      "warnings": list(dict.fromkeys(warnings)), "research_candidates": rows},
                     indent=2, ensure_ascii=False))
    return int(status == "error")


if __name__ == "__main__":
    raise SystemExit(main())
