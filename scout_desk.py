"""Dossier presentation for the authoritative pipeline payload."""
from base64 import b64encode
from pathlib import Path
from urllib.parse import urlsplit

import streamlit as st

from profile_evidence import profile_for, SOURCE_GUIDE
from scout_filters import formation_record, funding_stage
from scout_inbox import DECISIONS, WATCH_FOR, valid_url
from ui_brief import render_brief


def reported_stage(item):
    if item["funding_status"] != "funded":
        return "Unverified"
    stages = [funding_stage(report.get("stage") or report.get("round") or report.get("reported_as"))
              for report in item["funding"]["rounds"]]
    known = {stage for stage in stages if stage not in {"Unverified", "Other / review"}}
    return next(iter(known)) if len(known) == 1 else "Round reported · stage unclear"


def evidence_text(item, profile):
    """Present source-backed extracts with the shared payload kept intact."""
    yield from profile.get("dated_signals", [])
    for evidence in item.get("evidence", []):
        yield {**evidence, "url": evidence.get("source_url")}
    for event in item.get("timeline", []):
        if event.get("public_signal", True):
            yield {"signal": "Dated trace", "excerpt": event["label"], "url": event["url"],
                   "observed_at": event["date"]}
    for claim in item.get("claims", []):
        yield {"signal": f'{claim["status"]} · {claim["type"].replace("_", " ")}', "excerpt": claim["text"],
               "url": claim["source_url"]}
    for review in item["funding"]["reviews"]:
        if review.get("outcome") == "no_funding_found" and review.get("scope"):
            for url in review.get("sources", []):
                yield {"signal": "Scoped funding review", "url": url,
                       "excerpt": "No public round surfaced in the recorded review. " + review["scope"],
                       "observed_at": review.get("checked_on")}


def link(label, value):
    if url := valid_url(value):
        st.link_button(label, url)


def render_decision(item, store, saved, notices):
    with st.form(f'scout-decision:{item["mode"]}:{item["id"]}'):
        action = st.radio("Scout decision", DECISIONS, horizontal=True,
                          index=DECISIONS.index(saved["decision"]) if saved else 1)
        owner = st.text_input("Owner", value=saved["owner"] if saved else "", max_chars=80)
        reason = st.text_input("Reason or next action", value=saved["reason"] if saved else "", max_chars=280)
        trigger = st.selectbox("Reopen a Watch decision when…", WATCH_FOR,
                               index=WATCH_FOR.index(saved["watch_for"]) if saved else 0)
        if st.form_submit_button("Save decision", type="primary"):
            if not reason.strip():
                st.warning("Add a reason so a teammate can pick up the lead.")
            else:
                latest = max((notice["id"] for notice in notices if notice["lead_id"] == item["id"]), default=0)
                store.decide(item["mode"], item["id"], action, owner, reason, trigger, through=latest)
                st.rerun()
    if saved:
        st.caption(f'{saved["decision"]} · {saved["owner"] or "Unassigned"}')
        st.text(saved["reason"])


def render_dossier(item, store, saved, notices):
    profile = profile_for(item)
    if path := profile.get("logo_path"):
        asset = Path(__file__).parent / path
        st.markdown(f'<img class="venture-mark" alt="" src="data:image/png;base64,{b64encode(asset.read_bytes()).decode()}">',
                    unsafe_allow_html=True)
    st.header(item["name"])
    description = item.get("description") or "Description unavailable."
    st.text(description[:550] + ("…" if len(description) > 550 else ""))
    a, b = st.columns([1, 2])
    a.metric("Review score", f'{item["score"]}/100')
    b.caption("Funding assessment")
    b.write(item["funding_label"])
    if (stage := reported_stage(item)) not in ("Unverified", "Round reported · stage unclear"):
        b.caption(f"Reported stage · {stage}")
    st.caption(f'{item["sector"]} · {item["location"]} · Location evidence {item["location_evidence"].get("confidence", "unknown")}')
    location = item["location_evidence"]
    if item["location"] == "Germany" and location.get("confidence") in {"registry", "verified"}:
        st.caption("German location documented. Confirm the operating base in diligence.")
        link("German location evidence", location.get("source_url"))
    else:
        st.caption("German operating base needs confirmation.")
    formed = formation_record(item, profile)
    if formed:
        st.caption(f"Founding or registration · {formed.value}")
        link("Formation evidence", formed.source)
    else:
        st.caption("Company age is unverified. The timeline measures public evidence.")
    first_seen = store.first_seen(item["id"]) if item["mode"] == "live" else None
    if first_seen:
        st.caption(f"First seen by this desk · {first_seen[:10]} UTC")

    evidence = list(evidence_text(item, profile))
    st.subheader("Why review this lead")
    updates = [n for n in notices if item["mode"] == "live" and n["lead_id"] == item["id"]
               and n["kind"] != "First seen in shortlist"]
    if updates:
        change = updates[0]
        st.caption(f'{change["kind"]} · observed {change["captured_at"][:10]} UTC')
        st.text(change["detail"])
        link("Read what changed", change["source"])
    why = next((x for x in profile.get("dated_signals", []) if x.get("type") == "pilot"), None)
    why = why or item.get("earliest_verified_public_signal")
    if why:
        st.text(f'{why.get("observed_at") or why.get("date")} · {why.get("signal") or why.get("label")}')
        if why.get("excerpt"):
            st.text(why["excerpt"])
        link("Read the signal", why.get("url"))
    else:
        st.caption("No dated public trace has been verified.")
    question = profile.get("next_question")
    if not question:
        question = ("Which pilot has a named buyer, a success criterion and a paid next step?"
                    if item.get("founder_identified") else "Which source confirms who is building the company?")
    st.text("First-call question · " + question)
    render_decision(item, store, saved, notices)

    overview, timeline, brief, scoring = st.tabs(["People & diligence", "Evidence", "Analyst brief", "Scoring"])
    with overview:
        for person in profile.get("founders") or item.get("founders") or []:
            st.text(person["name"] + (f' · {person["role"]}' if person.get("role") else ""))
            link(f'{person["name"]} · founder evidence', person.get("source_url"))
            link(f'{person["name"]} · LinkedIn', person.get("linkedin_url"))
        if not item.get("founders") and not profile.get("founders"):
            st.text(item.get("team") or "Names unavailable from public evidence.")
        link("Open company or project", item.get("project_url"))
        st.caption("Public financials")
        for record in profile.get("financials", []):
            link(record["label"], record["url"])
        if profile.get("financials"):
            st.caption("Registry lookup. A company-specific filing has yet to be verified.")
        else:
            st.caption("No company filing linked.")
        for gap in item.get("missing_information", []):
            st.text("Verify · " + gap)
        for flag in item.get("red_flags", []):
            st.text(flag["reason"])
        for exclusion in item.get("shortlist_exclusions", []):
            st.text(exclusion.replace("_", " ").capitalize())
    with timeline:
        st.caption(item["public_trace_age"])
        dated = sorted((e for e in evidence if e.get("observed_at")), key=lambda e: e["observed_at"])
        for idx, entry in enumerate(dated + [e for e in evidence if not e.get("observed_at")], start=1):
            st.caption(entry.get("observed_at") or "Date unverified")
            st.text(f'{entry["signal"]} · {entry["excerpt"]}')
            link(f"Evidence {idx} · original source", entry.get("url"))
    with brief:
        outline = (f'# {item["name"]}\n\n'
                   f'Funding: {item["funding_label"]}\n\nTeam: {item["team"] or "Unverified"}\n\n'
                   f'First-call question: {question}\n\n'
                   + "\n".join(f'- {entry["excerpt"]} — {entry["url"]}'
                               for entry in evidence[:8] if valid_url(entry.get("url"))))
        st.download_button("Download sourced call brief", outline, "firsttrace-call-brief.md", "text/markdown")
        render_brief({**item, "evidence": evidence})
    with scoring:
        st.json(item["score_components"], expanded=True)
        st.caption(f'Evidence confidence · {item["evidence_confidence"]}/10')
        for check in item["funding"]["reviews"]:
            if check.get("scope"):
                st.text(f'{check.get("checked_on", "Date unverified")} · {check["scope"]}')
        for idx, report in enumerate(item["funding"]["rounds"] + item["funding"]["public_support"], start=1):
            link(f"Funding or public support record {idx}", report.get("source_url"))

    return evidence


def render_sources(item, evidence=()):
    st.divider()
    st.subheader("Sources")
    if item:
        profile = profile_for(item)
        label_by_url = {source["url"]: source["label"] for source in profile.get("sources", [])}
        urls = [*label_by_url, item.get("project_url"), *item.get("sources", []),
                *(e.get("url") for e in evidence)]
        if formed := formation_record(item, profile):
            label_by_url.setdefault(formed.source, "Company formation")
            urls.append(formed.source)
        for record in profile.get("financials", []):
            label_by_url.setdefault(record["url"], record["label"])
            urls.append(record["url"])
        for idx, url in enumerate(dict.fromkeys(urls), start=1):
            if safe := valid_url(url):
                link(f'{idx}. {label_by_url.get(url, urlsplit(safe).hostname)}', safe)
    with st.expander("Directories for further research"):
        for source in SOURCE_GUIDE:
            link(source["label"], source["url"])
            st.caption(source["use"])
