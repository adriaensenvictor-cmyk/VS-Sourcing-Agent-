"""HTGF readiness: turn collected evidence into checks, an investment window and first-call questions.

The score measures how ready a lead is for a first conversation under HTGF's stated criteria.
Every point comes from a linked observation. It is not a prediction of success.
"""
from datetime import date

FUNDED = {"Seed", "Seed reported", "Series A", "Series B", "Series C+", "Growth"}
PRODUCT_SIGNALS = {"pilot", "beta", "demo", "pricing", "customers"}
DIGITAL_TAGS = {"Digital tech", "enterprise", "developer", "infrastructure", "software", "codebases", "llms",
                "cybersecurity", "data platform", "data pipeline", "data teams", "llm", "codebase"}


def signal(lead, key):
    return next((row for row in (lead.get("web") or {}).get("signals", []) if row["key"] == key), None)


def legal(lead):
    return ((lead.get("web") or {}).get("legal")) or {}


def months_since(value, today):
    year, month = int(value[:4]), int(value[5:7])
    return (today.year - year) * 12 + today.month - month


def earliest(lead):
    rows = [{"date": trace["date"], "label": trace["title"], "url": trace["url"]} for trace in lead["traces"] if trace.get("date")]
    rows += [{"date": row["date"], "label": "GitHub release", "url": row.get("url")} for row in lead["releases"] if row.get("date")]
    rows += [{"date": row["date"], "label": "website first archived" if row.get("date_type") == "archived" else row["source"],
              "url": row["url"]} for row in lead.get("footprint", []) if row.get("date")]
    return min(rows, key=lambda row: row["date"]) if rows else None


def checks(lead, today):
    web = lead.get("web") or {}
    facts = legal(lead)
    funding = (lead["assessment"].get("funding") or {}).get("label")
    team = lead["assessment"].get("team") or ({"label": lead["review"].get("team"), "url": lead["review"].get("team_url")}
                                              if lead["review"].get("team") else None)
    rows = []

    def add(label, points, earned, detail, url=None):
        rows.append({"label": label, "points": points, "earned": earned, "ok": earned == points if earned else False,
                     "detail": detail, "url": url})

    if facts.get("german"):
        add("German base", 15, 15, f"{facts['address']}" + (f" · {facts['register']} {facts.get('court') or ''}".rstrip()
                                                              if facts.get("register") else ""), web.get("legal_url"))
    elif any(trace["source"] == "BayStartUP" for trace in lead["traces"]):
        add("German base", 15, 10, f"Listed by a Bavarian business plan competition · {lead.get('location') or 'Bavaria'}",
            next(trace["url"] for trace in lead["traces"] if trace["source"] == "BayStartUP"))
    elif lead.get("location"):
        add("German base", 15, 8, f"Located in {lead['location']} per analyst assessment")
    else:
        add("German base", 15, 0, "No German address found yet")

    stage = facts.get("stage", "Unknown")
    if stage.startswith("Incorporated"):
        add("Company formed", 10, 10, facts.get("entity") or stage, web.get("legal_url"))
    elif stage == "Being incorporated":
        add("Company formed", 10, 5, "Team states it is not incorporated yet: the earliest point to meet", web.get("legal_url"))
    elif stage == "No company form stated":
        add("Company formed", 10, 5, "People named as provider, no company form stated yet", web.get("legal_url"))
    else:
        add("Company formed", 10, 0, "Legal entity not found yet")

    if facts.get("directors"):
        add("People identified", 15, 15, f"{', '.join(facts['directors'])} · {facts.get('people_note', 'legal notice')}",
            web.get("legal_url"))
    elif team and team.get("label"):
        add("People identified", 15, 15, team["label"], team.get("url"))
    else:
        add("People identified", 15, 0, "No named people yet")

    tags = set(lead.get("tags", []))
    if lead["fit"] == "Core fit" or tags & DIGITAL_TAGS:
        add("Digital tech fit", 15, 15, ", ".join(sorted(tags)) or lead["fit"])
    elif tags & {"Health and life sciences", "Industrial and climate tech"}:
        add("Digital tech fit", 15, 0, f"{', '.join(sorted(tags))}: route to HTGF's Life Sciences or Industrial Tech team")
    else:
        add("Digital tech fit", 15, 0, ", ".join(sorted(tags)) or "Sector not identified")

    product = [row for row in web.get("signals", []) if row["key"] in PRODUCT_SIGNALS]
    if lead["releases"]:
        add("Product signal", 10, 10, f"{len(lead['releases'])} public GitHub releases, first {lead['releases'][0]['date']}",
            lead["releases"][0].get("url"))
    elif lead["assessment"].get("product"):
        add("Product signal", 10, 10, lead["assessment"]["product"]["label"], lead["assessment"]["product"]["url"])
    elif product:
        add("Product signal", 10, 10, f"Website: {', '.join(row['label'].lower() for row in product)}", web.get("url"))
    else:
        add("Product signal", 10, 0, "No product signal found yet")

    first = earliest(lead)
    if first:
        age = months_since(first["date"], today)
        earned = 10 if age <= 24 else 5 if age <= 36 else 0
        add("Young enough for HTGF", 10, earned,
            f"First public trace {first['date']} ({first['label']}), {age} months ago · HTGF invests up to 3 years after founding",
            first.get("url"))
    else:
        add("Young enough for HTGF", 10, 0, "No dated public trace yet")

    validation = []
    if lead.get("momentum"):
        validation.append(f"jury progression ({lead['momentum']})")
    if lead["assessment"].get("grant"):
        validation.append(lead["assessment"]["grant"]["label"])
    if any(trace["source"] == "UnternehmerTUM" for trace in lead["traces"]):
        validation.append("UnternehmerTUM prototype grant")
    if signal(lead, "grant"):
        validation.append("public funding on website")
    if len({trace["source"] for trace in lead["traces"]}) > 1:
        validation.append("two independent sources")
    add("Independent validation", 15, 15 if validation else 0, "; ".join(validation) or "Single listing only")

    investors = signal(lead, "investors")
    if funding in FUNDED:
        add("No equity round seen", 10, 0, f"{funding} reported", (lead["assessment"].get("funding") or {}).get("url"))
    elif investors:
        add("No equity round seen", 10, 0, f"Website names investors: {investors['quote']}", web.get("url"))
    else:
        add("No equity round seen", 10, 10, "No round in checked sources; website names no investors" if web else
            "No round in checked sources")
    return rows


def window(lead, rows):
    facts = legal(lead)
    funding = (lead["assessment"].get("funding") or {}).get("label")
    if funding in FUNDED or (lead.get("hold") and "financ" in lead["hold"].lower()):
        return {"zone": 3, "label": "Window closed", "reason": "A financing round is reported."}
    if signal(lead, "investors"):
        return {"zone": 2, "label": "Window closing", "reason": "The website mentions investors or a round. Verify before outreach."}
    if facts.get("stage") in {"Being incorporated", "No company form stated"}:
        return {"zone": 1, "label": "Window open · pre-company", "reason": "The team is not incorporated yet. Earliest point to build a relationship."}
    earned = sum(row["earned"] for row in rows)
    if earned >= 55:
        return {"zone": 1, "label": "Window open", "reason": "Early traces, no equity round seen."}
    return {"zone": 0, "label": "Too early to judge", "reason": "Not enough public evidence yet."}


def why_now(lead, today):
    facts = legal(lead)
    parts = []
    if signal(lead, "raising"):
        parts.append("talking to investors now")
    recent = sorted((trace for trace in lead["traces"] if trace.get("date")), key=lambda trace: trace["date"])
    if lead.get("momentum") and recent:
        parts.append(f"{lead['momentum']} in {recent[-1]['title'].split(' · ')[0]} ({recent[-1]['date']})")
    elif recent and months_since(recent[-1]["date"], today) <= 12:
        parts.append(f"{recent[-1]['title']} ({recent[-1]['date']})")
    if facts.get("stage") == "Being incorporated":
        parts.append("not incorporated yet")
    elif facts.get("entity"):
        parts.append(f"{facts['entity']}" + (f", {facts['register']}" if facts.get("register") else ""))
    for key in ("pilot", "beta", "hiring", "customers"):
        found = signal(lead, key)
        if found:
            parts.append(found["label"].lower())
            break
    if lead["releases"]:
        parts.append(f"latest release {lead['releases'][-1]['date']}")
    return " · ".join(parts[:3])


def questions(lead):
    facts = legal(lead)
    funding = (lead["assessment"].get("funding") or {}).get("label")
    asked = []
    if facts.get("stage") == "Being incorporated":
        asked.append("When do you incorporate, and how is IP from your research institution handled?")
    if facts.get("entity") and not facts.get("brand_match"):
        asked.append(f"Is {facts['entity']} the only entity behind {lead['name']}?")
    if not funding or funding == "Unverified":
        asked.append("Have you raised equity yet, or only grants and prizes? Who is on the cap table?")
    if signal(lead, "raising"):
        asked.insert(0, "You are talking to investors: what round size and timeline, and who leads so far?")
    if signal(lead, "pilot") or signal(lead, "beta"):
        asked.append("How many pilots run today, and what makes a pilot convert into a paid contract?")
    elif signal(lead, "demo") or signal(lead, "pricing"):
        asked.append("Who signs the contract, and what does a typical deal look like today?")
    if not facts.get("directors") and not lead["assessment"].get("team") and not lead["review"].get("team"):
        asked.append("Who are the founders, and are they full-time on the company?")
    if lead.get("momentum"):
        asked.append("What did the competition jury challenge most, and what changed since?")
    if signal(lead, "hiring"):
        asked.append("Which roles are you hiring first, and how is that funded?")
    asked.append("What would you need from a first investor in the next six months?")
    return asked[:3]


def assess(lead, today=None):
    today = today or date.today()
    rows = checks(lead, today)
    score = sum(row["earned"] for row in rows)
    return {"score": score, "checks": rows, "window": window(lead, rows),
            "why_now": why_now(lead, today), "questions": questions(lead)}
