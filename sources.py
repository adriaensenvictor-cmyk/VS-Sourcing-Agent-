"""Bounded access to public source pages and GitHub release metadata."""
from datetime import datetime
from html.parser import HTMLParser
import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

COHORT = "https://funding.unternehmertum.de/supportedteams-2/"
BAYSTARTUP = "https://www.baystartup.de"
COMPETITION = BAYSTARTUP + "/startupdate/die-nominierten-im-muenchener-businessplan-wettbewerb-2026-phase-1"
# The organizer's news index lists each new roster, so repeated scans discover new pages.
COMPETITION_INDEX = BAYSTARTUP + "/startupdate"
# Business plan competition rosters only; other contests use layouts the parsers do not read.
ROSTER_LINK = re.compile(
    r'href="(/startupdate/(?=[a-z0-9-]*businessplan)[a-z0-9-]*(?:nominierten|finale|sieger)[a-z0-9-]*)"'
)
MAX_ROSTERS = 10
GITHUB = "https://api.github.com"
DIGITAL_DE = re.compile(
    r"\b(?:KI|AI|Software|SaaS|Plattform|digital\w*|Daten\w*|IT-Sicherheit|Cyber\w*|Cloud|"
    r"Schnittstellen|Algorithm\w*|Halluzination\w*|App)\b"
)
SECTOR = re.compile(
    r"\b(?:enterprise|infrastructure|developer|codebases?|cybersecurity|"
    r"data (?:platform|pipeline|teams)|software|llms?)\b", re.IGNORECASE
)
NOISE = re.compile(
    r"\b(?:student[- ]initiated team|student club|student assignment|digital agency|"
    r"student association)\b", re.IGNORECASE
)
SOURCES = {
    "campus": ("UnternehmerTUM", COHORT),
    "competition": ("BayStartUP", COMPETITION),
    "github": ("GitHub releases", "https://docs.github.com/en/rest/releases/releases"),
    "footprint": ("Founder footprint", "https://web.archive.org/"),
    "web": ("Company research (Impressum, § 5 DDG)", "https://www.gesetze-im-internet.de/ddg/__5.html"),
}


class CohortParser(HTMLParser):
    """Read names and descriptions from the programme's project cards."""

    def __init__(self):
        super().__init__()
        self.projects = []
        self.card = None
        self.field = None

    def handle_starttag(self, tag, attrs):
        if tag == "utum-tile":
            self.card = {"h2": [], "p": []}
        elif self.card is not None and tag in self.card:
            self.field = tag

    def handle_endtag(self, tag):
        if tag == self.field:
            self.field = None
        if tag == "utum-tile" and self.card is not None:
            name, description = (
                " ".join("".join(self.card[field]).split()) for field in ("h2", "p")
            )
            if name and description:
                tags = sorted({match.group().lower() for match in SECTOR.finditer(description)})
                self.projects.append({
                    "name": name, "tags": tags, "noise": bool(NOISE.search(description)),
                    "description": description,
                })
            self.card = None
            self.field = None

    def handle_data(self, data):
        if self.field:
            self.card[self.field].append(data)


class CompetitionParser(HTMLParser):
    """Read company names, locations and category from the organizer's dated roster."""

    def __init__(self):
        super().__init__()
        self.publication = []
        self.publication_open = False
        self.heading = None
        self.category = None
        self.item = None
        self.in_name = False
        self.projects = []

    def handle_starttag(self, tag, attrs):
        if tag == "time" and not self.publication and dict(attrs).get("itemprop") == "datePublished":
            self.publication_open = True
        elif tag == "h3":
            self.heading = []
        elif tag == "li":
            self.item = []
            self.rest = []
        elif tag == "strong" and self.item is not None:
            self.in_name = True

    def handle_endtag(self, tag):
        if tag == "time":
            self.publication_open = False
        elif tag == "h3" and self.heading is not None:
            self.category = {
                "Digitale Infrastruktur, KI und Software": "Digital tech",
                "Medizintechnik, Life Sciences und Pharma": "Health and life sciences",
                "Industrie, Robotik, Energie und Agrar": "Industrial and climate tech",
            }.get(" ".join("".join(self.heading).split()))
            self.heading = None
        elif tag == "strong":
            self.in_name = False
        elif tag == "li" and self.item is not None:
            name_and_location = re.fullmatch(r"(.+?)\s+\(([^()]+)\)", "".join(self.item).strip())
            if self.category and name_and_location:
                name, location = name_and_location.groups()
                self.projects.append({
                    "name": name, "location": location, "tags": [self.category], "noise": False,
                    "description": " ".join("".join(self.rest).split()).strip(" –-:"),
                })
            self.item = None
            self.in_name = False

    def handle_data(self, data):
        if self.publication_open:
            self.publication.append(data)
        if self.heading is not None:
            self.heading.append(data)
        if self.item is not None and not self.in_name:
            self.rest.append(data)
        if self.in_name:
            self.item.append(data)


class FinalistParser(HTMLParser):
    """Read finalist ("Name aus City: tagline") and winner ("Platz 1: ...") article sections."""

    def __init__(self):
        super().__init__()
        self.publication = []
        self.publication_open = False
        self.heading = None
        self.paragraph = None
        self.entries = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "time" and not self.publication and attributes.get("itemprop") == "datePublished":
            self.publication_open = True
        elif tag == "h2" and "section-headline" not in (attributes.get("class") or ""):
            self.heading = []
        elif tag == "p" and self.entries and not self.entries[-1]["description"]:
            self.paragraph = []

    def handle_endtag(self, tag):
        if tag == "time":
            self.publication_open = False
        elif tag == "h2" and self.heading is not None:
            self.entries.append({"heading": " ".join("".join(self.heading).split()), "description": ""})
            self.heading = None
        elif tag == "p" and self.paragraph is not None:
            self.entries[-1]["description"] = " ".join("".join(self.paragraph).split())
            self.paragraph = None

    def handle_data(self, data):
        if self.publication_open:
            self.publication.append(data)
        if self.heading is not None:
            self.heading.append(data)
        if self.paragraph is not None:
            self.paragraph.append(data)

    def finalists(self):
        rows = []
        for entry in self.entries:
            match = re.fullmatch(r"(.{2,60}?)(?:\s+aus\s+(.+?))?:\s+(.+)", entry["heading"])
            if not match or entry["heading"].startswith("Platz"):
                continue
            name, location, tagline = match.groups()
            if location:
                location = re.split(r"\s+(?:in|im)\s+", location, maxsplit=1)[0]
            text = f"{tagline} {entry['description']}"
            rows.append({
                "name": name, "location": location or "",
                "tags": ["Digital tech"] if DIGITAL_DE.search(text) else [], "noise": False,
                "description": f"{tagline}. {entry['description']}".strip(". "),
            })
        return rows

    def placed(self):
        """Phase winners listed as "1. Platz: Name aus City" with a description paragraph."""
        rows = []
        for entry in self.entries:
            match = re.fullmatch(r"(\d+)\. Platz:\s*(.{2,60}?)(?:\s+aus\s+(.+))?", entry["heading"])
            if match:
                place, name, location = match.groups()
                location = re.split(r"\s+(?:in|im|bei)\s+", location or "", maxsplit=1)[0]
                rows.append({
                    "name": name, "location": location, "place": int(place), "noise": False,
                    "tags": ["Digital tech"] if DIGITAL_DE.search(entry["description"]) else [],
                    "description": entry["description"],
                })
        return rows

    def winners(self):
        return [
            (int(match.group(1)), match.group(2))
            for match in (re.fullmatch(r"Platz (\d+):\s*(.+)", entry["heading"]) for entry in self.entries)
            if match
        ]


def normalized(name):
    """Same-organizer name key: case, spacing and punctuation differ between rosters."""
    return re.sub(r"[^0-9a-z]", "", name.casefold())


def roster_label(url):
    region = "Nordbayern" if "nordbayern" in url else "Munich"
    if "finale" in url:
        stage = "Finalist"
    elif "sieger" in url:
        stage = "Phase 2 winner" if "phase-2" in url else "Winner"
    else:
        phase = re.search(r"phase-(\d)", url)
        stage = f"Phase {phase.group(1)} nomination" if phase else "Nomination"
    return f"{region} BPW · {stage}"


def fetch(url):
    headers = {"User-Agent": "FirstTrace-Hackathon/2.0"}
    # Optional token from the local environment raises GitHub's limit from 60 to 5,000 requests/hour.
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith(GITHUB + "/"):
        headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    request = Request(url, headers=headers)
    for attempt in range(2):
        try:
            with urlopen(request, timeout=10) as response:
                return response.read().decode("utf-8")
        except HTTPError as error:
            retry_after = error.headers.get("Retry-After")
            if attempt or error.code not in {429, 500, 502, 503, 504}:
                raise
            if retry_after and (not retry_after.isdigit() or int(retry_after) > 2):
                raise
            time.sleep(int(retry_after or "1"))
        except (URLError, TimeoutError):
            if attempt:
                raise
            time.sleep(1)


def campus_projects():
    parser = CohortParser()
    parser.feed(fetch(COHORT))
    if not parser.projects:
        raise ValueError("No campus project cards found")
    return parser.projects


def roster_urls(errors):
    urls = [COMPETITION]
    try:
        for path in ROSTER_LINK.findall(fetch(COMPETITION_INDEX)):
            if BAYSTARTUP + path not in urls:
                urls.append(BAYSTARTUP + path)
    except (OSError, ValueError) as error:
        errors.append(f"BayStartUP news index: {error}")
    return urls[:MAX_ROSTERS]


def parse_roster(url, html):
    """Return dated rows from a nominee list, finalist article or winner article."""
    nominees = CompetitionParser()
    nominees.feed(html)
    article = FinalistParser()
    article.feed(html)
    stamp = "".join(nominees.publication).strip() or "".join(article.publication).strip()
    published = datetime.strptime(stamp, "%d.%m.%Y").date().isoformat()
    label = roster_label(url)
    rows = nominees.projects or (article.finalists() if "finale" in url else article.placed())
    return (
        [{**row, "published": published, "url": url,
          "title": f"{label} · place {row.pop('place')}" if "place" in row else label} for row in rows],
        [(place, text, published, url, f"{label} · place {place}") for place, text in article.winners()],
    )


def competition_projects(errors=None):
    errors = [] if errors is None else errors
    pages = []
    for url in roster_urls(errors):
        try:
            pages.append(parse_roster(url, fetch(url)))
        except (OSError, ValueError) as error:
            errors.append(f"BayStartUP roster {url.rsplit('/', 1)[-1]}: {error}")
    # Oldest rosters first, so a team keeps the name from its first appearance.
    pages.sort(key=lambda page: (page[0] or [{"published": "9999"}])[0]["published"])
    rows = [row for page, _ in pages for row in page]
    known = {normalized(row["name"]): row["name"] for row in rows}
    for _, winners in pages:
        for place, text, published, url, title in winners:
            key = normalized(text)
            prefix = normalized(" ".join(text.split()[:2]))
            matches = [name for norm, name in known.items() if key.startswith(norm)] or [
                name for norm, name in known.items() if norm.startswith(prefix)
            ]
            if len(set(matches)) == 1:
                rows.append({"name": matches[0], "location": "", "tags": [], "noise": False,
                             "published": published, "url": url, "title": title})
    if not rows:
        raise ValueError("No competition nominations found")
    return rows


def repository_releases(repo):
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo) or ".." in repo.split("/"):
        raise ValueError("Invalid GitHub repository name")
    releases = []
    for page in range(1, 4):
        batch = json.loads(fetch(f"{GITHUB}/repos/{repo}/releases?per_page=100&page={page}"))
        for release in batch:
            if release["published_at"] and not release["draft"] and not release["prerelease"]:
                releases.append({
                    "title": f"{repo.split('/')[1]} · {release['tag_name']}",
                    "url": release["html_url"],
                    "date": release["published_at"][:10],
                })
        if len(batch) < 100:
            return releases, False
    return releases, True
