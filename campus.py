"""Discover early TUM Venture Labs projects from public team pages.

Run: python3 campus.py --limit 5
Export for the demo: python3 campus.py --json

TUM's sitemap dates are page updates. The actual first public trace and
funding status require verification. GitHub and LinkedIn links are kept
when the team page publishes them directly.
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from founder_signals import founder_history
from qualification import detect_intent
from sourcing import positive_int

SITE = "https://www.tum-venture-labs.de"
SIGNALS = (
    ("Academic origin", r"\b(?:student team|research team|doctoral|PhD|researchers? at|spin[- ](?:off|out) from|thesis)\b", 3),
    ("Founding team", r"\b(?:co[- ]founders?|founding team|our team consists)\b", 2),
    ("Product validation", r"\b(?:(?:ran|completed|launched|offering) (?:[\w-]+ ){0,2}pilots?|tested (?:our|the) prototype|validated (?:our|the) prototype)\b", 3),
    ("Early project stage", r"\b(?:(?:working|functional|validated) prototype|proof[- ]of[- ]concept|pre[- ]seed|MVP)\b", 2),
)
FUNDING = re.compile(r"\b(?:raised|secured|closed|completed)\b[^.!?]{0,60}\b(?:funding round|financing round|seed round|series [a-e]|million)\b", re.I)


def download(url):
    request = Request(url, headers={"User-Agent": "Victor-Startup-Sourcing/1.0"})
    with urlopen(request, timeout=12) as response:
        return response.read(4_000_000)


class TeamPage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.main_depth = 0
        self.section = None
        self.heading = ""
        self.paragraphs = []
        self.links = []
        self.chunks = []
        self.fact_label = ""
        self.founders = []

    def handle_starttag(self, tag, attrs):
        if tag == "main":
            self.main_depth += 1
        if not self.main_depth:
            return
        if tag in {"h1", "p", "li", "dt", "dd"} and self.section is None:
            self.section = tag
            self.chunks = []
        if tag == "br" and self.section == "dd":
            self.chunks.append(";")
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_data(self, data):
        if self.section:
            self.chunks.append(data)

    def handle_endtag(self, tag):
        if tag == "main":
            self.main_depth = max(0, self.main_depth - 1)
        if tag == self.section:
            text = " ".join("".join(self.chunks).split())
            if tag == "h1":
                self.heading = text
            elif tag == "dt":
                self.fact_label = text.casefold()
            elif tag == "dd":
                if self.fact_label in {"founder", "founders", "co-founders"}:
                    self.founders.extend(
                        name.strip() for name in re.split(r"[;,]|\s+and\s+", text)
                        if 2 <= len(name.split()) <= 7
                    )
            elif text:
                self.paragraphs.append(text)
            self.section = None


def evidence_excerpt(paragraph, match):
    return paragraph[max(0, match.start() - 85):match.end() + 95]


def read_team(entry):
    url, modified_at = entry
    page = TeamPage()
    page.feed(download(url).decode("utf-8"))
    if not page.heading or not page.paragraphs:
        return None
    signals = []
    score = 0
    for label, pattern, weight in SIGNALS:
        for paragraph in page.paragraphs:
            match = re.search(pattern, paragraph, re.I)
            if match:
                signals.append({"signal": label, "excerpt": evidence_excerpt(paragraph, match)})
                score += weight
                break
    labels = {item["signal"] for item in signals}
    if not labels & {"Early project stage", "Product validation"}:
        return None
    if not labels & {"Academic origin", "Founding team", "Product validation"}:
        return None
    if any(FUNDING.search(paragraph) for paragraph in page.paragraphs):
        return None

    links = {"github": [], "linkedin": []}
    for href in page.links:
        link = urljoin(url, href)
        parts = urlsplit(link)
        host = parts.hostname or ""
        if parts.scheme != "https":
            continue
        for platform, domain in (("github", "github.com"), ("linkedin", "linkedin.com")):
            if (host == domain or host.endswith("." + domain)) and link not in links[platform]:
                links[platform].append(link)
    signals.extend(founder_history(page.heading, list(dict.fromkeys(page.founders)),
                                   page.paragraphs, url))
    return {
        "id": f"tum:{url.rstrip('/').rsplit('/', 1)[-1]}",
        "title": page.heading,
        "description": next((paragraph[:350] for paragraph in page.paragraphs if len(paragraph) > 100), None),
        "source": "TUM Venture Labs",
        "location_query": "Germany (university ecosystem)",
        "source_url": url,
        "published_at": None,
        "source_updated_at": modified_at,
        "funding_status": "unverified",
        "score": score,
        "evidence": signals,
        "founders": [{"name": name, "role": "Founder", "source_url": url}
                     for name in dict.fromkeys(page.founders)],
        "intent_cues": detect_intent(" ".join(page.paragraphs), url),
        "links": links,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", type=positive_int, default=100, help="Maximum team pages to fetch")
    parser.add_argument("--limit", type=positive_int, default=10)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        sitemap = ET.fromstring(download(f"{SITE}/sitemap.xml"))
    except (OSError, ET.ParseError) as error:
        print(f"TUM sitemap unavailable: {error}", file=sys.stderr)
        return 1
    entries = {}
    for item in sitemap:
        url = item.findtext("{*}loc") or ""
        if re.fullmatch(re.escape(SITE) + r"/teams/[^/?#]+/", url):
            entries[url] = item.findtext("{*}lastmod")
    if not entries:
        print("No TUM team pages found in sitemap", file=sys.stderr)
        return 1
    recent = sorted(entries.items(), key=lambda entry: entry[1] or "", reverse=True)[:args.scan]
    leads = []
    successful = 0
    with ThreadPoolExecutor(max_workers=5) as executor:
        jobs = {entry[0]: executor.submit(read_team, entry) for entry in recent}
        for url, job in jobs.items():
            try:
                lead = job.result()
            except (OSError, ValueError) as error:
                print(f"Team page unavailable for {url}: {error}", file=sys.stderr)
                continue
            successful += 1
            if lead:
                leads.append(lead)
    if not successful:
        return 1
    leads.sort(key=lambda lead: (lead["score"], lead["source_updated_at"] or ""), reverse=True)
    leads = leads[:args.limit]
    if args.json:
        print(json.dumps(leads, ensure_ascii=False, indent=2))
    elif not leads:
        print("No teams with matching project-stage evidence.")
    else:
        for lead in leads:
            print(f'[{lead["score"]}] {lead["title"]} | {lead["source_url"]}')
            for evidence in lead["evidence"]:
                print(f'    {evidence["signal"]}: {evidence["excerpt"]}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
