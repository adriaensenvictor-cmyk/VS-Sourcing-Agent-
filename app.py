"""First Trace scout desk backed by the authoritative discovery pipeline."""
from datetime import date
import sqlite3

import streamlit as st

from dashboard_data import dashboard_rows, export_csv, export_json, load_demo_run
from discovery_pipeline import run_discovery
from emergence import DISCOVERY_SOURCES
from historical_replay import render_replay
from profile_evidence import profile_for
from scout_desk import render_dossier, render_sources, reported_stage
from scout_filters import (
    ALL_EUROPE, ANYWHERE, REGIONS, age_fit, formation_record,
    location_region, region_matches,
)
from scout_inbox import ScoutInbox, valid_url


LIVE_MODE = "Live discovery"
SNAPSHOT_MODE = "Verified research snapshot"

st.set_page_config(page_title="FirstTrace · Scout Desk", layout="wide")
st.markdown("""
<style>
[data-testid="stMainBlockContainer"] {max-width:1330px;padding-top:2rem}
.scout-banner {background:#103c35;color:#effaf4;border-radius:20px;padding:1.4rem 2rem;margin-bottom:.75rem}
.scout-banner h1 {color:#fff9ef;font:500 clamp(2rem,4vw,3.25rem) Georgia,serif;padding:0;margin:.35rem 0}
.scout-banner p {margin:0;color:#d3e8de}
.venture-mark {width:62px;height:62px;object-fit:contain;background:white;border-radius:10px}
div[data-testid="stMetric"] {border:1px solid #7a9a9066;border-radius:12px;padding:.55rem .8rem}
div[data-testid="stTabs"] [role="tablist"] {overflow-x:auto}
</style>
<header class="scout-banner">
<p>FirstTrace / HTGF</p>
<h1>Scout desk</h1>
<p>Find the signal that makes a first call worth taking.</p>
</header>
""", unsafe_allow_html=True)

def open_queued_lead(lead_id):
    st.session_state.update(workspace="Screening", data_mode=LIVE_MODE, lead=lead_id,
                            geography=ANYWHERE, company_age="Any age", query="",
                            funding=[], stages=[], sectors=[], **{"shortlist-Live discovery": False,
                            "watch-Live discovery": False, "review_score": 0})


page = st.sidebar.selectbox("Workspace", ["Screening", "New since review", "Historical replay"], key="workspace")
if page == "Historical replay":
    render_replay()
    st.stop()

store = ScoutInbox()
notices = store.inbox()
if page == "New since review":
    st.header("New since review")
    latest = store.latest_run()
    if latest:
        st.caption(f'Last scan attempt · {latest["generated_at"][:16].replace("T", " ")} UTC')
        for name, status in latest["source_status"].items():
            st.caption(f'{name} · {status["state"]} · {status["count"]} records')
    if not notices:
        st.info("No unread signals. Run discovery to start tracking shortlisted companies.")
    current_ids = {row["id"] for row in (store.latest_run(usable_only=True) or {}).get("candidates", [])}
    for index, notice in enumerate(notices, start=1):
        st.subheader(notice["name"])
        st.caption(f'{notice["kind"]} · observed {notice["captured_at"][:10]} UTC')
        st.text(notice["detail"])
        if source := valid_url(notice["source"]):
            st.link_button(f"Read signal {index} source", source)
        if notice["lead_id"] in current_ids:
            st.button("Open dossier", key=f'open-{notice["id"]}',
                      on_click=open_queued_lead, args=(notice["lead_id"],))
        if st.button("Mark reviewed", key=f'ack-{notice["id"]}'):
            store.acknowledge(notice["id"])
            st.rerun()
    st.stop()

with st.sidebar:
    st.header("Discovery settings")
    mode = st.radio("Data mode", [LIVE_MODE, SNAPSHOT_MODE], key="data_mode")
    is_live = mode == LIVE_MODE
    sources = st.multiselect("Public sources", DISCOVERY_SOURCES, default=DISCOVERY_SOURCES, disabled=not is_live)
    days = st.slider("Show HN lookback window (days)", 30, 365, 365, step=5, disabled=not is_live)
    run_clicked = st.button("Run sourcing engine", type="primary", disabled=is_live and not sources)
    st.caption(f"{len(notices)} unread items in New since review")

key = "live_view" if is_live else "snapshot_view"
if run_clicked:
    try:
        if is_live:
            with st.spinner("Checking public early signals…"):
                run = run_discovery(tuple(sources), days, github_limit=4)
            if run["source_status"]:
                store.record(run)
                notices = store.inbox()
            st.session_state[key] = run
        else:
            st.session_state[key] = load_demo_run()
    except (OSError, ValueError, KeyError, sqlite3.Error):
        st.error("The run could not be loaded. Check the source and local inbox settings.")

outcome = st.session_state.get(key)
if is_live and not run_clicked:
    latest = store.latest_run()
    if latest and (not outcome or latest["generated_at"] >= outcome["generated_at"]):
        outcome = latest
if outcome is None:
    st.info("Run the sourcing engine to see live results, or load the research snapshot.")
    render_sources(None)
    st.stop()

is_snapshot = outcome["mode"] == "research_snapshot"
if is_snapshot:
    st.warning("DEMO RESEARCH MODE · Manually researched reference cases.")
else:
    st.caption(f'Live scan · {outcome["generated_at"][:16].replace("T", " ")} UTC')
for name, status in outcome["source_status"].items():
    if status["state"] in {"error", "partial"}:
        message = name + " · " + " ".join(status["warnings"])
        (st.error if status["state"] == "error" else st.warning)(message)
if outcome["source_status"] and all(v["state"] not in {"ok", "partial"} for v in outcome["source_status"].values()):
    if prior := store.latest_run(usable_only=True):
        st.info(f'Showing the last usable results from {prior["generated_at"][:16].replace("T", " ")} UTC.')
        outcome = prior

st.subheader("Screening queue")
a, b, c = st.columns([1, 1, 1.4])
region = a.selectbox("Geography", REGIONS, index=REGIONS.index(ALL_EUROPE), key="geography")
age = b.selectbox("Company age", ["Any age", "Up to 3 years", "Up to 2 years"], key="company_age")
query = c.text_input("Search", placeholder="Company, founder or sector", key="query").casefold().strip()
with st.expander("Funding, sector and review filters"):
    include_unknown = st.checkbox("Include companies with unverified age", value=True)
    shortlist_only = st.toggle("Show shortlisted only", value=not is_snapshot, key=f"shortlist-{mode}")
    saved_only = st.checkbox("Show watched companies", key=f"watch-{mode}")
    limits = st.multiselect("Funding", ["Unknown · verification required", "No public round found in scoped review", "Funding round reported"], key="funding")
    stage_options = sorted({reported_stage(row) for row in dashboard_rows(outcome)})
    stages = st.multiselect("Reported funding stage", stage_options, key="stages")
    minimum = st.slider("Minimum review score", 0, 100, step=1, key="review_score")

decisions = store.decisions(outcome["mode"])
rows = dashboard_rows(outcome, shortlist_only=shortlist_only and not saved_only)
sector_options = sorted({row["sector"] for row in rows})
sectors = st.multiselect("Sector", sector_options, placeholder="All sectors", key="sectors")
leads = []
for item in rows:
    profile = profile_for(item)
    country = profile.get("country") or item["location"]
    if not region_matches(location_region({"country": country}), region) or item["score"] < minimum:
        continue
    if (limits and item["funding_label"] not in limits) or (stages and reported_stage(item) not in stages):
        continue
    if sectors and item["sector"] not in sectors:
        continue
    if query and query not in " ".join([item["name"], item["team"], item["sector"]]).casefold():
        continue
    if age != "Any age":
        fit = age_fit(formation_record(item, profile), 3 if age == "Up to 3 years" else 2, date.today())
        if fit is False or (fit is None and not include_unknown):
            continue
    if saved_only and decisions.get(item["id"], {}).get("decision") != "Watch":
        continue
    leads.append(item)

st.metric("Leads to review", len(leads))
if not leads:
    st.info("No matching leads. Try All locations, Any age, or turn off the shortlist filter.")
    render_sources(None)
    st.stop()

queue, detail = st.columns([2, 4], gap="large")
with queue:
    by_id = {row["id"]: row for row in leads}
    if st.session_state.get("lead") not in by_id:
        st.session_state["lead"] = next(iter(by_id))
    selection = st.selectbox("Investigate a lead", list(by_id), key="lead",
                             format_func=lambda lead_id: by_id[lead_id]["name"])
    for row in leads[:10]:
        with st.container(border=True):
            st.text(row["name"])
            label = decisions.get(row["id"], {}).get("decision") or row["lead_status"]
            st.caption(f'{row["score"]}/100 · {label} · {row["earliest_public_date"] or "Trace date unknown"}')
            st.caption(row["funding_label"])
    with st.expander("Export screening queue"):
        st.download_button("Export lead dossiers (JSON)", data=export_json(outcome, leads),
                           file_name="first_trace_leads.json", mime="application/json")
        st.download_button("Export screening queue (CSV)", data=export_csv(leads),
                           file_name="first_trace_queue.csv", mime="text/csv")
with detail:
    selected = by_id[selection]
    evidence = render_dossier(selected, store, decisions.get(selection), notices)
render_sources(selected, evidence)
