"""Automatic company research: website, German legal notice (Impressum) and website signals.

German companies must publish an Impressum naming the legal entity, its address, the register
court and number, and the people who legally represent it. FirstTrace reads it to do the first
research step an analyst does by hand.

Identity rule: an automatic match needs the company name in the legal notice and a matching city,
register court or German address. Analyst-verified domains (data/assessments.json) always win.
"""
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timedelta, timezone
import html as H
import json
import re
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

AGENT = "FirstTrace-Hackathon/2.0 (sourcing research prototype)"
TLDS = ("com", "de", "io", "ai", "tech")
LEGAL_PATHS = ("/impressum", "/imprint", "/de/impressum", "/en/imprint", "/legal-notice", "/en/legal-notice")
NEGATIVE_HOURS = 24
DEADLINE_SECONDS = 60
WORKERS = 16
CITY_ALIASES = {"munich": "münchen", "muenchen": "münchen", "nuremberg": "nürnberg", "cologne": "köln"}

LEGAL_FORM = (
    r"(GmbH\s*&\s*Co\.\s*KG|gGmbH|GmbH|UG\s*\(haftungsbeschränkt\)|UG|AG|SE|GbR|e\.\s?V\.|KG)"
    r"(\s*i\.\s?G\.|\s*in Gründung)?(?![\wäöü])"
)
REGISTER = re.compile(r"\b(HRB|HRA|VR|GnR|PR)\s*[:.]?\s*(?:Nr\.?\s*)?(\d{2,7})(?:\s*B)?\b")
COURT = re.compile(
    r"(?:Amtsgericht|Registergericht|Register [Cc]ourt|Local [Cc]ourt|District [Cc]ourt|Court of [Rr]egistration)"
    r"(?:\s*\(Amtsgericht\))?\s*(?:of|in)?\s*[:\-–,]?\s*(?:Amtsgericht\s+)?"
    r"([A-ZÄÖÜ][a-zäöüß]+(?:\s+am\s+Main|\s+an\s+der\s+[A-ZÄÖÜ][a-zäöüß]+)?)"
)
NOT_A_CITY = {"handelsregister", "registernummer", "registereintrag", "hrb", "registergericht", "amtsgericht", "eingetragen"}
POSTCODE = re.compile(r"\b(?:D-)?(\d{5})\s+([A-ZÄÖÜ][a-zäöüß]+(?:[ -](?:[A-ZÄÖÜ][a-zäöüß]+|an der|am|im|bei)){0,3})")
GERMAN_MARKERS = re.compile(r"Deutschland|Germany|Amtsgericht|Registergericht|USt-?Id|DE\s?\d{9}|Handelsregister|Vereinsregister")
DIRECTORS = re.compile(
    r"(Geschäftsführer(?:in|innen)?|Geschäftsführung|Vertreten durch|Vertretungsberechtigt(?:e|er)?(?:\s+Geschäftsführer(?:in)?)?|"
    r"Managing Directors?|Represented by|Vorstand)\s*:?\s*(.{3,200})"
)
DIRECTOR_STOP = re.compile(
    r"\b(Registergericht|Handelsregister|Registereintrag|Register|Amtsgericht|HRB|HRA|Sitz|USt|Umsatzsteuer|Kontakt|"
    r"Contact|E-?Mail|Telefon|Tel\.|Phone|Inhaltlich|Verantwortlich|Anschrift|Address|Steuernummer|VAT|Postanschrift|"
    r"Haftung|Disclaimer|Datenschutz|Privacy|Copyright)\b"
)
NAME_PART = r"[A-ZÄÖÜ][a-zäöüßéèáàíóúñç'’]+(?:-[A-ZÄÖÜ]?[a-zäöüßéèáàíóúñç'’]+)*"
PERSON = re.compile(
    r"(?:(?:Dr|Prof)\.\s*)*" + NAME_PART + r"(?:\s+(?:von|van|de|der|del|da|zu|den)?\s*" + NAME_PART + r"){1,3}"
)
ROLE_WORDS = re.compile(
    r"\b(?:Managing|Director|Directors|Geschäftsführ\w*|CEO|CTO|COO|Founder|Gründer\w*|Vorstand|Inhaber\w*|"
    r"GmbH|UG|Team|Health|Software|Solutions|Kontakt|Contact|Impressum|Angaben|Deutschland|Germany|Str|Straße)\b", re.I)
ROLE_LINE = re.compile(r"^(?:Managing Director|Geschäftsführer(?:in)?|CEO(?:\s*(?:&|and)\s*(?:Co-)?Founder)?|Inhaber(?:in)?)$", re.I)
PRE_COMPANY = re.compile(r"in Gründung|\bi\.\s?G\.|vor Gründung|Venture-Team|Gründungsvorhaben|Gründungsteam", re.I)
ENTITY_STOP = re.compile(r"Impressum|Angaben|Anbieter|Diensteanbieter|Company|Firma|Haftung|Google|Webflow|Hosting|Datenschutz", re.I)

SIGNALS = (
    ("pilot", "Pilot program", re.compile(r"\bpilot(?:\s+program(?:me)?|\s+customers?|\s+partners?|projekt\w*|en)?\b", re.I)),
    ("beta", "Beta, early access or waitlist", re.compile(r"\b(?:beta|early access|wait-?list|warteliste)\b", re.I)),
    ("demo", "Sells through demos", re.compile(r"\b(?:book|request|get|schedule) a demo\b|\bdemo (?:anfragen|buchen|vereinbaren)\b", re.I)),
    ("pricing", "Public pricing", re.compile(r"\b(?:pricing|preise|per month|pro monat)\b", re.I)),
    ("customers", "Names customers or case studies", re.compile(r"\b(?:trusted by|our customers|unsere kunden|case stud(?:y|ies)|used by)\b", re.I)),
    ("hiring", "Hiring", re.compile(r"\b(?:we['’]?re hiring|we are hiring|join our team|careers|karriere|open positions|offene stellen)\b", re.I)),
    ("investors", "Names investors or a round", re.compile(
        r"\bbacked by [^.]{0,50}?\b(?:ventures?|capital|vc|investors?|angels?|fonds?|funds?)\b(?!-)|\bour investors\b|"
        r"\bunsere investoren\b|\braised (?:€|\$|eur|usd|\d)|\b(?:pre-?seed|seed) (?:round|funding|financing)\b|"
        r"\bseries [ab]\b|\bfinanzierungsrunde\b|\bseed-finanzierung\b", re.I)),
    ("raising", "Talking to investors now", re.compile(
        r"\b(?:for investors|investor:innen|investor relations|looking for investors|we are raising|currently raising|"
        r"seeking investment|investoren gesucht|venture investors|für investoren)\b", re.I)),
    ("grant", "Mentions public funding", re.compile(
        r"\bEXIST(?:-| )?(?:Gründerstipendium|Forschungstransfer|Startup|Women)?\b|\bgefördert\b|\bhorizon europe\b|"
        r"\bBMWK\b|\bBMBF\b|\bFlügge\b|\bEIC\b")),
)


def fetch_page(url):
    """GET an HTML page with a short timeout; return (final URL, text)."""
    request = Request(url, headers={"User-Agent": AGENT, "Accept": "text/html,application/xhtml+xml"})
    with urlopen(request, timeout=6) as response:
        if "html" not in (response.headers.get("Content-Type") or "html"):
            raise ValueError("not an HTML page")
        charset = response.headers.get_content_charset() or "utf-8"
        return response.geturl(), response.read(800_000).decode(charset, "replace")


def page_text(markup):
    markup = re.sub(r"(?is)<(script|style|noscript|svg|template)[^>]*>.*?</\1>", " ", markup)
    markup = re.sub(r"(?i)<br\s*/?>|</(?:p|div|li|h[1-6]|tr|section|address|span)>", "\n", markup)
    text = H.unescape(re.sub(r"<[^>]+>", " ", markup))
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def normalized(value):
    value = value.casefold().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^0-9a-z]", "", value)


def city_key(value):
    value = (value or "").casefold().strip()
    return CITY_ALIASES.get(value, value)


def candidate_domains(name):
    lowered = name.casefold().strip()
    if re.fullmatch(r"[a-z0-9-]+\.[a-z]{2,}", lowered):
        return [lowered]
    ascii_name = lowered.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    joined = re.sub(r"[^a-z0-9]", "", ascii_name)
    hyphened = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")
    words = re.findall(r"[a-z0-9]+", ascii_name)
    bases = [joined, hyphened]
    if len(words) > 1 and len(words[0]) >= 5:
        bases.append(words[0])
    if len(joined) < 4:
        return []
    return [f"{base}.{tld}" for base in dict.fromkeys(bases) for tld in TLDS]


def legal_link(home_url, markup):
    links = re.findall(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', markup, re.S | re.I)
    ranked = []
    for href, label in links:
        text = f"{href} {re.sub('<[^>]+>', ' ', label)}"
        if re.search(r"impressum|imprint", text, re.I):
            ranked.insert(0, href)
        elif re.search(r"legal[-_ ]?notice|rechtliches|legal\b", text, re.I):
            ranked.append(href)
    urls = [urljoin(home_url, href) for href in ranked if not href.startswith(("mailto:", "tel:", "javascript:"))]
    return list(dict.fromkeys(urls + [urljoin(home_url, path) for path in LEGAL_PATHS]))[:5]


def brand_names(name):
    """The brand as listed, plus the brand without a trailing domain suffix (Deskbot.io -> Deskbot)."""
    names = [name]
    stripped = re.sub(r"\.(?:io|ai|de|com|app|tech)$", "", name, flags=re.I)
    if stripped != name:
        names.append(stripped)
    return names


def find_entity(text, name):
    """The legal entity: first one carrying the brand name, else the first entity named in the notice."""
    for brand in brand_names(name):
        words = [re.escape(word) for word in re.findall(r"[0-9A-Za-zÄÖÜäöüß]+", brand)]
        pattern = re.compile(r"(" + r"[\s\-_.]*".join(words) + r"(?:[ \-][\w&.\-]+){0,3}?)\s*,?\s+" + LEGAL_FORM, re.I)
        match = pattern.search(text)
        if match:
            return entity_from(*match.groups(), brand_match=True)
    generic = re.compile(r"([A-ZÄÖÜ0-9][\w&.\-]*(?:[ ][A-ZÄÖÜ0-9][\w&.\-]*){0,4})\s*,?\s+" + LEGAL_FORM)
    for line in text.splitlines():
        match = generic.search(line)
        if match and not ENTITY_STOP.search(match.group(1)):
            return entity_from(*match.groups(), brand_match=False)
    return None


def entity_from(base, form, forming, brand_match):
    form = re.sub(r"\s+", " ", form).replace("( ", "(")
    if form.upper().startswith("UG"):
        form = "UG (haftungsbeschränkt)" if "haft" in form else "UG"
    return {"entity": f"{base.strip()} {form}{' i.G.' if forming else ''}", "form": form,
            "forming": bool(forming), "brand_match": brand_match}


def people_in(chunk, name):
    found = []
    for part in re.split(r",|;|/|&|\bund\b|\band\b|\|", chunk):
        person = part.strip(" .:-()–")
        if PERSON.fullmatch(person) and not ROLE_WORDS.search(person) and normalized(person) != normalized(name):
            found.append(person)
    return found


def find_directors(text, name):
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = DIRECTORS.search(line)
        if match:
            chunk = DIRECTOR_STOP.split(match.group(2))[0]
            chunk = re.sub(r"^\s*(?:die|den|der|the)?\s*(?:Geschäftsführer\w*|Managing Directors?|CEO)?\s*:?\s*", "", chunk)
            people = people_in(re.sub(r"\([^)]*\)", " ", chunk), name)
            if not people and index + 1 < len(lines):
                people = people_in(DIRECTOR_STOP.split(lines[index + 1])[0], name)
            if people:
                return people, "Managing directors named in the legal notice"
        # "Jane Doe" on one line followed by a role line such as "Managing Director".
        if index and ROLE_LINE.match(line.strip()):
            people = people_in(lines[index - 1], name)
            if people:
                return people, "Managing directors named in the legal notice"
    return [], None


def parse_legal(text, name):
    """Extract legal facts from an Impressum. Missing facts stay missing."""
    facts = {"entity": None, "form": None, "forming": False, "brand_match": False, "register": None, "court": None,
             "address": None, "german": False, "directors": [], "people_note": None, "stage": "Unknown"}
    entity = find_entity(text, name)
    if entity:
        facts.update(entity)
    register = REGISTER.search(text)
    if register:
        facts["register"] = f"{register.group(1)} {register.group(2)}"
        if register.group(1) == "VR" and not facts["form"]:
            facts["form"] = "e.V."
    for court in COURT.finditer(text):
        if court.group(1).casefold() not in NOT_A_CITY:
            facts["court"] = court.group(1)
            break
    places = [(code, city) for code, city in POSTCODE.findall(text)
              if city.casefold() not in {"mail", "email", "fax", "tel", "telefon", "registereintrag", "neu"}]
    preferred = [place for place in places if facts["court"] and city_key(place[1]) == city_key(facts["court"])]
    if preferred or places:
        facts["address"] = " ".join((preferred or places)[0])
    facts["german"] = bool(facts["address"] and (GERMAN_MARKERS.search(text) or facts["court"]))
    facts["directors"], facts["people_note"] = find_directors(text, name)
    if not facts["form"] and not facts["directors"]:
        # Individuals named as the provider right under the brand: no company form stated.
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if any(normalized(brand) == normalized(line) for brand in brand_names(name)):
                for following in lines[index + 1:index + 4]:
                    people = people_in(following, name)
                    if people:
                        facts["directors"], facts["people_note"] = people, "People named as the provider"
                        break
                if facts["directors"]:
                    break
    facts["directors"] = facts["directors"][:5]
    if facts["form"] == "e.V.":
        facts["stage"] = "Registered association (e.V.)"
    elif facts["forming"] or (not facts["form"] and PRE_COMPANY.search(text)):
        facts["stage"] = "Being incorporated"
    elif facts["form"] and facts["form"].startswith("UG"):
        facts["stage"] = "Incorporated · UG"
    elif facts["form"]:
        facts["stage"] = f"Incorporated · {facts['form']}"
    elif facts["directors"]:
        facts["stage"] = "No company form stated"
    return facts


def site_signals(text):
    found = []
    for key, label, pattern in SIGNALS:
        match = pattern.search(text)
        if match:
            # Quote the line that contains the match, trimmed around it.
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            line = text[line_start:line_end if line_end != -1 else len(text)]
            offset = match.start() - line_start
            start, end = max(0, offset - 90), min(len(line), offset + len(match.group(0)) + 90)
            quote = " ".join(line[start:end].split())
            found.append({"key": key, "label": label,
                          "quote": f"{'…' if start else ''}{quote}{'…' if end < len(line) else ''}"})
    return found


def describe(markup):
    title = re.search(r"(?is)<title[^>]*>(.*?)</title>", markup)
    meta = re.search(r'(?is)<meta[^>]+(?:name|property)=["\'](?:og:)?description["\'][^>]+content=["\']([^"\']+)', markup) \
        or re.search(r'(?is)<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:name|property)=["\'](?:og:)?description', markup)
    clean = lambda value: " ".join(H.unescape(value).split())[:300] if value else ""
    return clean(title.group(1) if title else ""), clean(meta.group(1) if meta else "")


def identity(facts, text, name, location, verified):
    """Return the reason an automatic match is accepted, or None."""
    if verified:
        return "Analyst-verified domain"
    words = re.findall(r"[0-9a-zäöüß]+", name.casefold())
    present = normalized(name) in normalized(text) or (len(words) > 1 and len(words[0]) >= 5 and normalized(words[0]) in normalized(text))
    if not present or not facts["german"]:
        return None
    places = {city_key(facts["court"]), city_key((facts["address"] or " ").split(" ", 1)[-1])}
    roster = {city_key(part) for part in re.split(r"[/,]", location or "") if part.strip()}
    if roster and places & roster:
        return "Name, city and German address match the legal notice"
    if roster:
        return None
    return "Name and German address match the legal notice"


def research(project, assessment, previous=None):
    """Find the company site and read its legal notice. Returns a result dict or None."""
    verified = (assessment.get("domain") or "").lower()
    domains = [verified] if verified else candidate_domains(project["name"])
    for domain in domains:
        try:
            home_url, markup = fetch_page(f"https://{domain}/")
        except (OSError, ValueError):
            continue
        home_text = page_text(markup)
        legal_url, legal_text = None, ""
        for url in legal_link(home_url, markup):
            if urlparse(url).hostname and urlparse(url).hostname.split(".")[-2:] != urlparse(home_url).hostname.split(".")[-2:]:
                continue
            try:
                final, legal_markup = fetch_page(url)
            except (OSError, ValueError):
                continue
            candidate = page_text(legal_markup)
            if re.search(r"Impressum|Imprint|Amtsgericht|HRB|Geschäftsführ|Legal notice", candidate, re.I):
                legal_url, legal_text = final, candidate
                break
        facts = parse_legal(legal_text, project["name"]) if legal_text else None
        reason = identity(facts, legal_text, project["name"], project.get("location"), bool(verified)) if facts else (
            "Analyst-verified domain" if verified else None)
        if not reason:
            continue
        title, summary = describe(markup)
        return {
            "domain": urlparse(home_url).hostname.removeprefix("www."), "url": home_url, "match": reason,
            "title": title, "summary": summary, "legal_url": legal_url, "legal": facts,
            "signals": site_signals(home_text), "text": home_text[:2500],
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    return None


def collect(projects, assessments, cache_path, errors):
    """Research every candidate project in parallel within a time budget, using a cache."""
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    now = datetime.now(timezone.utc)
    todo = []
    results = {}
    for project in projects:
        entry = cache.get(project["id"])
        assessment = assessments.get(project["id"], {})
        fresh_negative = entry and entry.get("result") is None and not assessment.get("domain") and \
            now - datetime.fromisoformat(entry["checked_at"]) < timedelta(hours=NEGATIVE_HOURS)
        if fresh_negative:
            continue
        todo.append((project, assessment, entry))
    pool = ThreadPoolExecutor(WORKERS)
    futures = {pool.submit(research, project, assessment): (project, entry) for project, assessment, entry in todo}
    done, pending = wait(futures, timeout=DEADLINE_SECONDS)
    for future in done:
        project, entry = futures[future]
        previous = (entry or {}).get("result")
        try:
            result = future.result()
        except Exception as error:  # A single site must never break the scan.
            errors.append(f"Website research for {project['name']}: {error}")
            result = None
        if result is None and previous:
            # A site that does not answer this time keeps its last research, marked with its original date.
            errors.append(f"Website research for {project['name']}: no answer, showing research from {previous['checked_at'][:10]}")
            cache[project["id"]] = {**entry, "result": {**previous, "stale": True}}
            continue
        if result:
            result.pop("stale", None)
        cache[project["id"]] = {"checked_at": now.isoformat(timespec="seconds"), "result": result}
    for future in pending:
        project, entry = futures[future]
        future.cancel()
        if entry and entry.get("result"):
            cache[project["id"]] = entry
    pool.shutdown(wait=False, cancel_futures=True)
    if pending:
        errors.append(f"Website research: {len(pending)} sites did not answer within {DEADLINE_SECONDS} s; previous results kept.")
    for project in projects:
        result = (cache.get(project["id"]) or {}).get("result")
        if result:
            results[project["id"]] = result
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    status = {"state": "partial" if pending else "fresh", "count": len(results), "checked": len(todo)}
    return results, status
