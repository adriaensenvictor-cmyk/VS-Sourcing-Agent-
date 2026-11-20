"""Presentation of a single lead and its public provenance."""
from base64 import b64encode
from datetime import datetime, timezone
from pathlib import Path
from html import escape
from urllib.parse import urlsplit

import streamlit as st

from profile_evidence import profile_for, SOURCE_GUIDE
from scout_filters import formation_record, lead_stage
from ui_brief import render_brief


def safe_url(value):
    try:
        parsed = urlsplit(value or "")
        if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password:
            return value
    except (TypeError, ValueError, AttributeError):
        pass
    return None


def evidence_date(value):
    try:
        stamp = datetime.fromisoformat((value or "").replace("Z", "+00:00"))
        return stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp
    except (ValueError, TypeError, AttributeError):
        return None


def links_for(item, profile):
    """Assign one reference to each URL in the order it appears in the dossier."""
    references = {}
    def add(label, url):
        if safe_url(url) and url not in references:
            references[url] = (len(references) + 1, label)
    for source in profile.get("sources", []):
        add(source["label"], source["url"])
    for evidence in item.get("evidence", []) + profile.get("dated_signals", []):
        add(evidence["signal"], evidence.get("url"))
    if formed := formation_record(item, profile):
        add("Company formation", formed.source)
    add("Discovery record", item.get("source_url"))
    add("Project", item.get("project_url"))
    add("Official company mark", profile.get("logo_url"))
    for filing in profile.get("financials", []):
        add(filing["label"], filing["url"])
    return references


def identity(item, profile):
    name = escape(item["name"])
    initials = escape("".join(w[0] for w in item["name"].split()[:2]).upper() or "?")
    mark = f'<span class="company-initials" aria-hidden="true">{initials}</span>'
    if profile.get("logo_path"):
        logo = Path(__file__).parent / profile["logo_path"]
        if logo.is_file():
            data = b64encode(logo.read_bytes()).decode("ascii")
            mark += f'<img alt="" src="data:image/png;base64,{data}">'
    st.markdown(f'<div class="company"><div class="company-mark">{mark}</div><div>'
                f'<h2>{name}</h2><p>{escape(item.get("sector") or "Sector unverified")} · '
                f'{escape(item.get("location") or "Location unverified")}</p></div></div>',
                unsafe_allow_html=True)


def render_stage(stage):
    steps = ["Pre-seed", "Seed", "Series A", "Series B", "Series C+", "Growth"]
    cells = "".join(f'<li class="{"current" if s == stage else ""}">{s}</li>' for s in steps)
    st.markdown(f'<ol class="vc-stages" aria-label="Venture funding stages">{cells}</ol>',
                unsafe_allow_html=True)
    st.caption(f"Reported funding stage · {stage}")


def render_timeline(rows, refs):
    by_signal = {e.get("signal"): (date, e) for date, e in rows if date}
    early = by_signal.get("Public venture competition")
    later = by_signal.get("Dealroom News funding coverage")
    if early and later and later[0] > early[0]:
        st.subheader("Before the round")
        st.caption("Historical replay · Two dated publications about the same company")
        reveal = st.toggle("Reveal the later coverage", key=f"reveal-{later[1]['url']}")
        if reveal:
            days = (later[0].date() - early[0].date()).days
            st.metric("Conference mention to Dealroom News coverage", f"{days} days")
            st.caption("FirstTrace’s discovery time and the company’s first database listing are unknown.")
        else:
            st.caption(f"Showing the timeline through {early[0]:%d %b %Y}.")
            rows = [(stamp, e) for stamp, e in rows if stamp and stamp <= early[0]]
    for stamp, e in rows:
        ref = refs.get(e.get("url"))
        st.caption((stamp.date().isoformat() if stamp else "Date unverified") +
                   (f"  ·  Source {ref[0]}" if ref else ""))
        st.write(e["signal"])
        st.write(e["excerpt"])
        if ref and stamp and early and later:
            st.link_button("Read " + e["signal"].lower(), e["url"])
    if not rows:
        st.caption("No evidence recorded yet.")


def render_dossier(item):
    profile = profile_for(item)
    refs = links_for(item, profile)
    identity(item, profile)
    description = item.get("description") or ""
    if len(description) > 650:
        st.write(description[:600].rsplit(" ", 1)[0] + "…")
        with st.expander("Full source description"):
            st.write(description)
    else:
        st.write(description)
    a, b = st.columns(2)
    a.metric("Review score", f'{item["score"]}/100')
    formed = formation_record(item, profile)
    b.metric("Founding / registration", str(formed.value) if formed else "Unverified")
    if formed:
        b.caption(f"Source {refs[formed.source][0]} · " + ("Reported year" if isinstance(formed.value, int) else "Documented date"))
    render_stage(lead_stage(item, profile))
    if stage_source := safe_url(profile.get("stage_source")):
        st.link_button("Read the investor announcement", stage_source)
    if not profile.get("stage"):
        st.caption(item.get("funding_status") or "Equity financing remains unverified.")
    overview, timeline, scoring, analyst = st.tabs(["People & financials", "Timeline", "Score", "Analyst brief"])
    with overview:
        st.subheader("Founders & team")
        if profile.get("founders"):
            for person in profile["founders"]:
                st.write(person["name"] + (f' · {person["role"]}' if person.get("role") else ""))
                if url := safe_url(person.get("linkedin_url")):
                    st.link_button(f'{person["name"]} on LinkedIn', url)
        else:
            st.write(item.get("team") or "Team identity needs verification.")
        if url := safe_url(item.get("project_url")):
            st.link_button("Open project", url)
        st.subheader("Public financials")
        if profile.get("financials"):
            st.caption("Registry lookup · A company-specific financial statement has yet to be verified.")
            for record in profile["financials"]:
                if url := safe_url(record["url"]):
                    st.link_button(record["label"], url)
        else:
            st.caption("No company filing has been linked to this record.")
        st.subheader("Next diligence question")
        if not item.get("founder_identified"):
            st.write("Who on the project is building a company, and which public source confirms their role?")
        elif formed is None:
            st.write("When was the team founded or incorporated, and under which legal name?")
        elif lead_stage(item, profile) == "Unverified":
            st.write("Has the company raised equity alongside its other support? Confirm with the founders or an investor.")
        elif "pilot" in item.get("description", "").casefold():
            st.write("Which pilots have converted to paying customers?")
        else:
            st.write("Which customer can independently confirm the product is in use?")
        with st.expander("Additional diligence checks"):
            for warning in item.get("warnings", []):
                st.write("• " + warning)
            st.write("Confirm a founder, the operating base and any equity raised before making contact.")
    with timeline:
        records = item.get("evidence", []) + profile.get("dated_signals", [])
        rows = [(evidence_date(e.get("observed_at")), e) for e in records]
        rows.sort(key=lambda pair: (pair[0] is None, pair[0] or datetime.max.replace(tzinfo=timezone.utc)))
        render_timeline(rows, refs)
    with scoring:
        st.caption("The sourcing engine assigns these points to prioritize analyst review.")
        if item.get("score_components"):
            st.table([{"Signal": name, "Points": points}
                      for name, points in item["score_components"].items()])
    with analyst:
        extra = list(profile.get("dated_signals", []))
        if formed:
            extra.append({"signal": "Founding or registration", "excerpt": f"Reported founding or registration: {formed.value}.",
                          "url": formed.source})
        if profile.get("stage_source"):
            extra.append({"signal": "Reported equity round", "excerpt": f"The investor reported a {profile['stage']} round.",
                          "url": profile["stage_source"]})
        render_brief(item, extra_evidence=extra)


def render_sources(item=None):
    st.divider()
    st.header("Sources")
    if item:
        refs = links_for(item, profile_for(item))
        st.subheader(f'References for {item["name"]}')
        for url, (number, label) in refs.items():
            st.link_button(f"{number}. {label}", url)
    with st.expander("Research directories across Europe", expanded=item is None):
        for source in SOURCE_GUIDE:
            st.link_button(source["label"], source["url"])
            st.caption(source["use"])
    with st.expander("Discovery coverage and methodology"):
        st.write("Live discovery currently checks TU Berlin venture profiles, Show HN and GitHub for German signals. "
                 "A developer profile or university affiliation is a starting point for verification. "
                 "The European directories above support manual research across borders.")
        st.write("EXIST and other public grants are tracked separately from equity financing. "
                 "A lead-time claim needs a dated public trace and a dated database comparison for the same company.")
