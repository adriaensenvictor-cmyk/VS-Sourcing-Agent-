"""First Trace's evidence-first Streamlit dashboard."""
from urllib.parse import urlsplit

import streamlit as st

from dashboard_data import dashboard_rows, export_csv, export_json, load_demo_run
from discovery_pipeline import run_discovery
from emergence import DISCOVERY_SOURCES
from fit_panel import render_fit
from founder_fit import AGE_LABELS

LIVE_MODE = "Live discovery"
SNAPSHOT_MODE = "Verified research snapshot"

st.set_page_config(page_title="First Trace | HTGF Scout", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown("""
<style>
div[data-testid="stMetric"] {border:1px solid #8793a255;border-radius:12px;padding:12px}
h1,h2,h3 {letter-spacing:-.025em}
</style>
""", unsafe_allow_html=True)

st.title("First Trace")
st.caption("Early-stage founder intelligence · HTGF Venture Capital Challenge")
st.info("Scores prioritize diligence. A grant and a public funding round are tracked separately.")

with st.sidebar:
    st.header("Discovery settings")
    mode = st.radio("Data mode", [LIVE_MODE, SNAPSHOT_MODE])
    sources = st.multiselect("Public sources", DISCOVERY_SOURCES, default=DISCOVERY_SOURCES,
                             disabled=mode != LIVE_MODE)
    days = st.slider("Show HN lookback window (days)", 30, 365, 365, step=5,
                     disabled=mode != LIVE_MODE)
    minimum = st.slider("Minimum Early Signal Score", 0, 100, 0, step=5)
    run_clicked = st.button("Run sourcing engine", type="primary", use_container_width=True,
                            disabled=mode == LIVE_MODE and not sources)
    st.divider()
    st.caption("Funding and company checks remain part of human diligence.")

if run_clicked:
    try:
        if mode == SNAPSHOT_MODE:
            outcome = load_demo_run()
        else:
            with st.spinner("Checking public early signals…"):
                outcome = run_discovery(tuple(sources), days, github_limit=4)
    except (OSError, ValueError, KeyError):
        st.error("The run could not be loaded. Check the source configuration and try again.")
    else:
        st.session_state["run"] = outcome

outcome = st.session_state.get("run")
if outcome is None:
    st.info("Select discovery sources and run the engine, or load the research snapshot.")
else:
    is_snapshot = outcome["mode"] == "research_snapshot"
    if is_snapshot:
        st.warning("DEMO RESEARCH MODE · Manually researched reference cases with original source links.")
    elif mode == SNAPSHOT_MODE:
        st.caption("Showing the last live result. Run the engine to switch datasets.")
    st.caption(f'Loaded {outcome["generated_at"]}')

    for name, status in outcome["source_status"].items():
        detail = " ".join(status["warnings"])
        if status["state"] == "error":
            st.error(f"{name} · {detail}")
        elif status["state"] == "partial":
            st.warning(f"{name} · Partial coverage. {detail}")

    shortlist_only = st.toggle("Show shortlisted only", value=not is_snapshot,
                               key=f'shortlist_{outcome["mode"]}')
    leads = [row for row in dashboard_rows(outcome, shortlist_only=shortlist_only)
             if row["score"] >= minimum]
    if not leads:
        st.warning("No leads match the current filters. You can widen the score range or include additional candidates.")

    if leads:
        a, b, c, d = st.columns(4)
        a.metric("Leads to review", len(leads))
        b.metric("Named founding teams", sum(row["founder_identified"] for row in leads))
        c.metric("German-location leads", sum(row["location"] == "Germany" for row in leads))
        d.metric("Evidence links", len({url for row in leads for url in row["sources"]}))
        st.subheader("Evidence-ranked opportunity queue")
        st.dataframe([
            {"Early Signal /100": row["score"], "Project": row["name"], "Sector": row["sector"],
             "Founder Potential /100": row["founder_venture_fit"]["founder"]["score"],
             "Venture Potential /100": row["founder_venture_fit"]["venture"]["score"],
             "Three-year eligibility": AGE_LABELS[row["founder_venture_fit"]["three_year_eligibility"]["status"]],
             "Location": row["location"], "Origin": row["origin"], "Team review": row["lead_status"],
             "Funding": row["funding_label"], "Earliest public signal": row["earliest_public_date"],
             "Evidence confidence /10": row["evidence_confidence"]}
            for row in leads
        ], hide_index=True, use_container_width=True)

        by_id = {row["id"]: row for row in leads}
        selection = st.selectbox("Investigate a lead", list(by_id),
                                 format_func=lambda key: f'{by_id[key]["name"]} · {by_id[key]["score"]}/100')
        item = by_id[selection]
        st.divider()
        st.header(item["name"])
        st.text(item["description"] or "Description unavailable.", help="Description from the source record")
        st.write(f'**Investment sector:** {item["sector"]}  |  **Location:** {item["location"]}')
        location = item["location_evidence"]
        st.caption(f'Location confidence · {location.get("confidence", "unknown")}')
        render_fit(item["founder_venture_fit"])
        left, right = st.columns([3, 2])
        with left:
            st.subheader("Founders and team")
            for person in item.get("founders", []):
                role = person.get("role")
                st.text(f'{person["name"]} · {role}' if role else person["name"])
                if person.get("source_url"):
                    st.caption(person["source_url"])
            if not item.get("founders"):
                st.text(item["team"] or "Names unavailable from public evidence.")

            st.subheader("Evidence ledger")
            if item.get("record_provenance"):
                st.caption(item["record_provenance"])
            for entry in item.get("evidence", []):
                st.text(f'{entry["signal"]} · {entry["excerpt"]}')
                st.caption(entry["source_url"])
            for entry in item.get("claims", []):
                st.text(f'{entry["status"].title()} · {entry["type"]} · {entry["text"]}')
                st.caption(entry["source_url"])

            st.subheader("Evidence timeline")
            st.caption(item["public_trace_age"])
            if item["founder_venture_fit"]["three_year_eligibility"]["status"] == "unknown":
                st.caption("Company age is unverified. The timeline measures public evidence.")
            for event in item.get("timeline", []):
                qualifier = " · public visibility unverified" if event.get("public_signal") is False else ""
                st.text(f'{event["date"]} · {event["label"]}{qualifier}')
                st.caption(event["url"])
            if not item.get("timeline"):
                st.caption("No dated public trace is available.")

            st.subheader("Original sources")
            for url in dict.fromkeys([item.get("project_url"), *item["sources"]]):
                if url and urlsplit(url).scheme in {"http", "https"}:
                    st.link_button(url, url)

        with right:
            st.subheader("Early Signal Score")
            st.write(f'{item["score"]}/100 · public emergence signals')
            st.json(item["score_components"], expanded=True)
            st.caption(f'Evidence confidence · {item["evidence_confidence"]}/10')
            st.subheader("Funding review")
            st.write(item["funding_label"])
            st.caption("A scoped search can miss private or undisclosed financing.")
            for check in item["funding"]["reviews"]:
                if check.get("checked_on"):
                    st.caption(f'Checked {check["checked_on"]} · {check.get("scope", "")}')
                for url in check.get("sources", []):
                    st.caption(url)
                if check.get("source_url"):
                    st.caption(check["source_url"])
            for report in item["funding"]["rounds"] + item["funding"]["public_support"]:
                st.caption(report["source_url"])

            st.subheader("Early-stage signals")
            signals = item.get("commercialization_signals") or []
            for signal in signals:
                st.text(f'{signal["status"].title()} · {signal["type"].replace("_", " ")}')
                st.caption(signal["source_url"])
            if not signals:
                st.caption("No commercialization signals documented in this run.")

            st.subheader("Diligence warnings")
            for flag in item.get("red_flags", []):
                st.text(flag["reason"])
                st.caption(flag["source_url"])
            for warning in item.get("shortlist_exclusions", []):
                st.text(warning.replace("_", " ").capitalize())
            for gap in item.get("missing_information", []):
                st.text(f"Verify · {gap}")
            st.caption("Database lead-time comparison · unmeasured")
        st.divider()
        st.subheader("Download the evidence trail")
        st.download_button("Export lead dossiers (JSON)", data=export_json(outcome, leads),
                           file_name="first_trace_leads.json", mime="application/json")
        st.download_button("Export screening queue (CSV)", data=export_csv(leads),
                           file_name="first_trace_queue.csv", mime="text/csv")

with st.expander("Scouting methodology · limitations · HTGF fit"):
    st.markdown("""
**Goal** — Surface German and European venture teams before their first public funding round.

**Sources** — TUM Venture Labs, TU Berlin's venture directory, Show HN and bounded GitHub search.
Evidence can include named teams, old public traces, applied research, public grant support and
commercialization cues. Source URLs and verification states accompany the signals.

**Scoring** — Early Signal Score (formerly Founder Emergence) combines team, technical, commercial, market, timing and evidence
signals. Eligibility is evaluated separately. Confirm company fit, IP ownership, customer demand
and funding with human diligence before outreach.
""")
