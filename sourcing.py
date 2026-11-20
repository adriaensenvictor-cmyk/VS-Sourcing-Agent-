"""Find early German startup leads from public Show HN posts.

Usage: python3 sourcing.py --days 180 --limit 10
       python3 sourcing.py --city Berlin --city Munich --json
Python 3.9+, standard library only. Results are leads for manual review.
"""

import argparse
import html
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

CITIES = ("Berlin", "Munich", "München", "Hamburg", "Cologne", "Frankfurt", "Germany")
FOUNDER = r"\b(?:we|our team|my co[- ]founder and I|I)\s+(?:are\s+based|work|live|build|are building|started|launched)\s+(?:out of\s+|in\s+|from\s+)"
SIGNALS = {
    "Customer or pilot mentioned": r"\b(?:customers?|pilot users?|design partners?)\b",
    "Commercial signal mentioned": r"\b(?:paid plans?|pricing|paying customers?|early access)\b",
    "Team signal mentioned": r"\b(?:co[- ]founders?|founding team|our team)\b",
    "Prototype or launch mentioned": r"\b(?:beta|prototype|MVP|just launched)\b",
}
NOISE = r"\b(?:weekend project|school assignment|university assignment|course assignment|for fun)\b"


def fetch(city, cutoff):
    query = urlencode({
        "query": city, "tags": "show_hn", "hitsPerPage": 100,
        "numericFilters": f"created_at_i>{cutoff}", "typoTolerance": "false",
    })
    request = Request(
        f"https://hn.algolia.com/api/v1/search_by_date?{query}",
        headers={"User-Agent": "Victor-Startup-Sourcing/1.0"},
    )
    with urlopen(request, timeout=12) as response:
        return json.load(response)["hits"]


def assess(post, city):
    title = post.get("title") or ""
    body = html.unescape(re.sub(r"<[^>]+>", " ", post.get("story_text") or ""))
    body = " ".join(body.split())
    if not title.lower().startswith("show hn:") or re.search(NOISE, title + " " + body, re.I):
        return None
    location_pattern = (
        r"(?:" + FOUNDER + r"|\b(?:based in|headquartered in|team from)\s+|\bI(?:'m| am)\s+(?:currently\s+)?working\b[^.!?]{0,65}\bin\s+)"
        + re.escape(city) + r"\b"
    )
    location = re.search(location_pattern, body, re.I)
    if not location:
        return None
    evidence = [{
        "signal": "Location wording",
        "excerpt": body[max(0, location.start() - 35):location.end() + 50],
    }]
    score = 3
    for signal, pattern in SIGNALS.items():
        match = re.search(pattern, body, re.I)
        if match:
            score += 1
            evidence.append({
                "signal": signal,
                "excerpt": body[max(0, match.start() - 35):match.end() + 35],
            })
    concern = re.search(r"\b(?:internal pitch project|side project|in my spare time)\b", body, re.I)
    if concern:
        score -= 1
        evidence.append({
            "signal": "Standalone company intent unclear",
            "excerpt": body[max(0, concern.start() - 35):concern.end() + 35],
        })
    project_url = post.get("url") or ""
    if urlsplit(project_url).scheme not in {"https", "http"}:
        project_url = None
    points = post.get("points") or 0
    return {
        "id": post["objectID"],
        "title": title[len("Show HN:"):].strip(),
        "location_query": city,
        "published_at": post["created_at"],
        "source_url": f'https://news.ycombinator.com/item?id={post["objectID"]}',
        "project_url": project_url,
        "hn_points": points,
        "score": score,
        "evidence": evidence,
    }


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", action="append", help="Location to search, repeatable")
    parser.add_argument("--days", type=positive_int, default=180)
    parser.add_argument("--limit", type=positive_int, default=10)
    parser.add_argument("--json", action="store_true", help="Output a JSON array")
    args = parser.parse_args()
    cities = list(dict.fromkeys(args.city or CITIES))
    cutoff = int((datetime.now(timezone.utc) - timedelta(days=args.days)).timestamp())
    leads = {}
    successful_queries = 0
    with ThreadPoolExecutor(max_workers=min(len(cities), 5)) as executor:
        jobs = {city: executor.submit(fetch, city, cutoff) for city in cities}
        for city, job in jobs.items():
            try:
                posts = job.result()
            except (OSError, ValueError, KeyError) as error:
                print(f"Search failed for {city}: {error}", file=sys.stderr)
                continue
            successful_queries += 1
            for post in posts:
                lead = assess(post, city)
                if lead and (lead["id"] not in leads or lead["score"] > leads[lead["id"]]["score"]):
                    leads[lead["id"]] = lead
    if not successful_queries:
        return 1
    ranked = sorted(leads.values(), key=lambda lead: (
        lead["score"], lead["published_at"], lead["hn_points"],
    ), reverse=True)[:args.limit]
    if args.json:
        print(json.dumps(ranked, ensure_ascii=False, indent=2))
    else:
        if not ranked:
            print("No matching leads in this window.")
        for lead in ranked:
            print(f'[{lead["score"]}] {lead["title"]} ({lead["published_at"][:10]})')
            print(f'    {lead["source_url"]}')
            for item in lead["evidence"]:
                print(f'    {item["signal"]}: {item["excerpt"]}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
