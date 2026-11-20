"""Project-level secondary-school scouting using public event rosters and school news."""
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

from pre_vc import annotate

import requests
from bs4 import BeautifulSoup

GEN = "https://gen-e.eu/2026/awards"
GERMAN_FINAL = "https://www.jugend-gruendet.de/finale-2026"
KOSICE = "https://www.gympos.sk/novinky/2026"
BRUCHSAL = "https://www.handelslehranstalt-bruchsal.de/?s=Heuwind&feed=rss2"
REGIONAL = ("https://www.baden-wuerttemberg.de/de/service/presse/pressemitteilung/pid/"
            "zwei-schuelerfirmen-beim-landeswettbewerb-ausgezeichnet")
SOURCES = (REGIONAL, GERMAN_FINAL, GEN, BRUCHSAL, KOSICE)
DATA = Path(__file__).with_name("data") / "student_watchlist.json"
EUROPE = set(("Albania|Austria|Belgium|Bosnia and Herzegovina|Bulgaria|Croatia|Cyprus|Czechia|Czech Republic|"
              "Denmark|Estonia|Finland|France|Germany|Greece|Hungary|Iceland|Ireland|Isle of Man|Italy|Kosovo|"
              "Latvia|Liechtenstein|Lithuania|Luxembourg|Malta|Moldova|Montenegro|Netherlands|North Macedonia|"
              "Norway|Poland|Portugal|Romania|Serbia|Slovakia|Slovenia|Spain|Sweden|Switzerland|Ukraine|"
              "United Kingdom").split("|"))


def fetch(url):
    with requests.get(url, headers={"User-Agent": "FirstTrace/1.0 (public event watchlist)"},
                      timeout=(4, 8), stream=True) as response:
        response.raise_for_status()
        chunks = bytearray()
        for chunk in response.iter_content(65536):
            chunks.extend(chunk)
            if len(chunks) > 2_000_000:
                raise ValueError("Source exceeded the watchlist size limit")
        return bytes(chunks)


def public_link(base, href, host, prefix):
    parsed = urlsplit(urljoin(base, href or ""))
    if (href and parsed.scheme == "https" and parsed.netloc == host
            and parsed.path.startswith(prefix) and len(parsed.path) > len(prefix)):
        return parsed._replace(query="", fragment="").geturl()
    return None


def label(card, selector):
    element = card.select_one(selector)
    return element.get_text(" ", strip=True) if element else ""


def roster(url, content):
    soup = BeautifulSoup(content, "html.parser")
    if url == REGIONAL:
        # Pair each quoted project with the immediately following school attribution.
        matches = []
        for paragraph in soup.select("main p"):
            text = paragraph.get_text(" ", strip=True)
            matches.extend(re.finditer(r'„([^“]{1,90})“ vom ([\w -]{0,70}Gymnasium)\b', text))
        if not matches:
            raise ValueError("Regional school attributions missing")
        published = soup.select_one("time[datetime]")
        for match in matches:
            name, school = match.groups()
            identity = "bw-junior-2026:" + name.casefold()
            yield identity, name, "Germany", {"kind": "event_listing", "basis": "regional_reporting",
                "date": published["datetime"][:10] if published else None, "url": url,
                "text": f"The regional competition report lists {name} from {school}."}
        return
    german = url == GERMAN_FINAL
    cards = soup.select("a.team-card" if german else "a.winner-tile")
    if not cards:
        raise ValueError("Expected event roster missing")
    for card in cards:
        if german:
            school = label(card, ".team-text strong")
            # The event also accepts trainees. Only keep identifiable school entries.
            if not re.search(r"gymnasium|gymnasien|berufsoberschule|handelslehranstalt|gesamtschule|fachoberschule", school, re.I):
                continue
            name, country = label(card, ".name-label"), "Germany"
            profile = public_link(url, card.get("href"), "www.jugend-gruendet.de", "/finale-2026/")
            text = f"{school} appears on the German national final roster for this project."
        else:
            if label(card, ".winner-level") != "Upper-Secondary":
                continue
            name, country = label(card, ".winner-name"), label(card, ".winner-country")
            if country not in EUROPE:
                continue
            profile = public_link(url, card.get("href"), "expo.gen-e.eu", "/expo/")
            text = "The Gen-E organizer lists this upper-secondary team in its 2026 awards."
        if profile and name:
            yield profile, name, country, {"kind": "event_listing", "basis": "organizer",
                                           "date": "2026", "text": text, "url": url}


def school_news(url, content):
    if url == KOSICE:
        soup = BeautifulSoup(content, "html.parser")
        links = soup.select("td h3 a[href]")
        if not links:
            raise ValueError("School news index missing")
        for link in links:
            title = link.get_text(" ", strip=True)
            href = public_link(url, link["href"], "www.gympos.sk", "/novinky/2026/")
            if href and re.search(r"\bLIPIGO\b", title, re.I):
                yield "student:lipigo", {"kind": "publication_to_review", "date": None, "url": href,
                                         "basis": "school_index", "text": title}
    else:
        channel = ElementTree.fromstring(content).find("channel")
        if channel is None:
            raise ValueError("School RSS channel missing")
        for item in channel.findall("item"):
            title = item.findtext("title") or ""
            content_text = " ".join(item.itertext())
            href = public_link(url, item.findtext("link"), "www.handelslehranstalt-bruchsal.de", "/")
            if href and title and re.search(r"\bHeuwind\b", content_text, re.I):
                stamp = item.findtext("pubDate")
                yield "student:heuwind", {"kind": "publication_to_review",
                    "date": parsedate_to_datetime(stamp).date().isoformat() if stamp else None,
                    "url": href, "basis": "school_feed", "text": title}


def refresh(*, live=False, previous=None, fetcher=fetch):
    stamp = datetime.now(timezone.utc).isoformat()
    previous_rows = {p["id"]: p for p in (previous or {}).get("student_watchlist", [])}
    rows = {}
    for entry in json.loads(DATA.read_text(encoding="utf-8")):
        rows[entry["id"]] = {**entry, "provenance": "reviewed", "funding_status": "unknown",
                             "formation_date": None, "reviewed_on": "2026-11-20"}
    # Carry forward observations with their original last-seen timestamps.
    for key, previous_row in previous_rows.items():
        if key not in rows and previous_row.get("provenance") == "event_roster":
            rows[key] = dict(previous_row)
        if key in rows:
            rows[key]["observations"] = [dict(o) for o in previous_row.get("observations", [])]
    profiles = {p["profile_url"]: p for p in rows.values() if p.get("profile_url")}
    sources, changes = {}, []
    for url in SOURCES if live else ():
        try:
            raw = fetcher(url)
            if url in (GEN, GERMAN_FINAL, REGIONAL):
                found = []
                for profile, name, country, signal in list(roster(url, raw)):
                    row = profiles.get(profile) or rows.get("student:" + profile)
                    if row is None:
                        key = "student:" + profile
                        row = {"id": key, "name": name, "profile_url": profile if url != REGIONAL else None,
                               "school_country": country,
                               "provenance": "event_roster", "signals": [], "formation_date": None,
                               "funding_status": "unknown", "description": None,
                               "review_question": "Is there a public product, field test or customer reference?"}
                        rows[key] = profiles[profile] = row
                    found.append((row["id"], signal))
            else:
                found = list(school_news(url, raw))
            count = 0
            for key, signal in found:
                observations = rows[key].setdefault("observations", [])
                old = next((o for o in observations if o["url"] == signal["url"] and o["kind"] == signal["kind"]), None)
                if old:
                    old["last_seen_at"] = stamp
                    if old["text"] != signal["text"] or old["date"] != signal["date"]:
                        old.update(signal)
                        changes.append({"project_id": key, "url": signal["url"], "change": "listing_updated"})
                else:
                    observations.append({**signal, "first_seen_at": stamp, "last_seen_at": stamp})
                    if previous is not None:
                        changes.append({"project_id": key, "url": signal["url"], "change": "new_listing"})
                count += 1
            sources[url] = {"status": "ok", "matches": count}
        except (requests.RequestException, OSError, ValueError, TypeError, ElementTree.ParseError) as exc:
            sources[url] = {"status": "error", "reason": type(exc).__name__}
    successful = sum(s["status"] == "ok" for s in sources.values())
    status = "snapshot"
    if live:
        status = "ok" if successful == len(SOURCES) else ("partial" if successful else "error")
    projects = annotate(rows.values())
    return {"presentation_ids": [p["id"] for p in projects if p["pre_vc"]["status"] == "present"],
            "module": "student_watchlist", "mode": "live" if live else "research_snapshot",
            "generated_at": stamp, "status": status, "sources": sources, "changes": changes,
            "student_watchlist": sorted(projects, key=lambda p: (p["school_country"] != "Germany",
                                       p["provenance"] != "reviewed", p["name"].casefold()))}
