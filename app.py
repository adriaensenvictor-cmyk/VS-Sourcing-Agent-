"""Hidden Gem — an evidence-first scouting cockpit for High-Tech Gründerfonds."""
import csv
import io
import json
import os
from datetime import datetime, timezone

import streamlit as st
from engine import load_research_snapshot, run_live

from scout_dossier import render_dossier, render_sources
from profile_evidence import profile_for
from scout_filters import (
    ALL_EUROPE, FUNDING_STAGES, GERMANY, REGIONS, age_fit, formation_record,
    lead_stage, location_region, region_matches,
)


st.set_page_config(page_title="FirstTrace · Scout desk", page_icon="🌱", layout="wide")

st.markdown("""
<style>
[data-testid="stMainBlockContainer"] {max-width:1370px;padding-top:2rem}
.desk-hero {background:#0a3431;border-radius:18px;position:relative;overflow:hidden;
  isolation:isolate;color:#fcfaf4;padding:clamp(1.3rem,2.4vw,2rem);margin-bottom:.8rem}
.desk-hero::after {content:"";position:absolute;z-index:-1;right:-5rem;top:-12rem;
  width:32rem;height:32rem;border-radius:50%;
  background:repeating-radial-gradient(circle,transparent 0 19px,#43857b 20px 21px,transparent 22px 29px);
  mask-image:linear-gradient(90deg,transparent,black)}
.desk-brand {font-weight:700;font-size:.9rem;letter-spacing:.02em;color:#bdeedb}
.desk-hero h1 {color:#fff9ee;font-family:Georgia,serif;font-weight:500;
  font-size:clamp(2.3rem,5vw,4.2rem);line-height:1.06;letter-spacing:-.045em;margin:.55rem 0;padding:0}
.desk-hero p {margin:0;color:#def2eb;max-width:38rem}
.company {display:flex;align-items:center;gap:.85rem;margin:.5rem 0 .85rem}
.company h2 {font-family:Georgia,serif;font-weight:500;font-size:clamp(1.75rem,3vw,2.7rem);
  line-height:1.1;padding:0;letter-spacing:-.035em}
.company p {margin:.25rem 0 0;font-size:.9rem}
.company-mark {height:3.8rem;width:3.8rem;flex:none;position:relative;border-radius:14px;
  background:#e2efe8;color:#10483c;overflow:hidden;display:grid;place-items:center}
.company-initials {font-weight:700;font-size:1.35rem}
.company-mark img {position:absolute;inset:0;width:100%;height:100%;object-fit:contain;padding:.4rem;background:white}
.vc-stages {display:flex;flex-wrap:wrap;gap:.35rem;padding:0!important;margin:.7rem 0 .2rem!important}
.vc-stages li {list-style:none;margin:0!important;font-size:.75rem;line-height:1.2;
  padding:.4rem .55rem;border-top:3px solid #879b95}
.vc-stages .current {border-color:#18735d;background:#d2f6de;color:#113d33;font-weight:bold}
div[data-testid="stMetric"] {border:1px solid rgba(110,135,122,.4);border-radius:12px;padding:.6rem .8rem}
div[data-testid="stTabs"] [role="tablist"] {overflow-x:auto}
@media(max-width:680px){.desk-hero::after{opacity:.45;right:-16rem}.desk-hero{padding:1.4rem}}
</style>
<header class="desk-hero">
<div class="desk-brand">FirstTrace / HTGF</div>
<h1>Scout desk</h1>
<p>Find the first trace, open the evidence, and decide which founders to meet.</p>
</header>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Discovery settings")
    mode = st.radio("Data mode", ["Verified research snapshot", "Live discovery"],
                    help="The snapshot contains manually researched cases. Live discovery queries public sources.")
    live_mode = mode == "Live discovery"
    if live_mode:
        sources = st.multiselect("Public sources", ["Campus", "Hacker News", "GitHub"],
                                 default=["Campus", "Hacker News", "GitHub"])
        days = st.slider("Lookback window (days)", 30, 365, 180, step=30)
        run = st.button("Run sourcing engine", type="primary", disabled=not sources)
    minimum = st.slider("Minimum review score", 0, 100, step=5, key="min_score")

@st.cache_data(ttl=900, show_spinner=False)
def cached_live(which, days, token):
    return run_live(which, days, token or None)

if live_mode:
    if run:
        with st.spinner("Checking public early signals…"):
            st.session_state["live_scan"] = cached_live(tuple(sources), days, os.environ.get("GITHUB_TOKEN", ""))
    candidates, errors = st.session_state.get("live_scan", ([], []))
    if "live_scan" not in st.session_state:
        st.info("Select public sources in the sidebar and run the sourcing engine.")
    else:
        st.caption("Live discovery · Results from your last scan")
else:
    candidates = load_research_snapshot()
    errors = []
    st.caption("Research snapshot · Manually researched public records · 20 Nov 2026")
for err in errors:
    st.error(f"Source unavailable: {err}")

leads = []
if candidates:
    st.subheader("Lead inbox")
    regions, ages = st.columns(2)
    region_filter = regions.selectbox(
        "Geography", REGIONS, key="inbox_region",
        help="Uses the reported company or team location. An owner profile or university affiliation alone leaves the location unverified.",
    )
    age_options = {"Up to 3 years": 3, "Up to 2 years": 2, "Any age": None}
    age_filter = ages.selectbox("Company age", list(age_options), key="inbox_age",
                                help="Uses a sourced founding or registration date. Grants and first public signals do not establish age.")
    include_unknown = st.checkbox("Include companies with unverified age", key="inbox_unknown_age",
                                  disabled=age_options[age_filter] is None)
    search = st.text_input("Search leads", placeholder="Company, team or location", key="inbox_query")
    with st.expander("Sector and funding stage"):
        sectors, stages = st.columns(2)
        sector_filter = sectors.multiselect("Sectors", sorted({x["sector"] for x in candidates}), key="inbox_sector")
        funding_filter = stages.multiselect("Funding stages", FUNDING_STAGES, key="inbox_stage",
                                            help="Unverified includes teams with only grant evidence or no confirmed round.")
    today = datetime.now(timezone.utc).date()
    unknown_age_count = 0
    terms = search.casefold().split()
    for item in candidates:
        profile = profile_for(item)
        region = location_region(item, profile)
        searchable = " ".join(str(item.get(key) or "") for key in (
            "name", "team", "sector", "location", "origin", "description",
        )).casefold()
        if (item["score"] < minimum or not all(word in searchable for word in terms)
            or not region_matches(region, region_filter)
            or (sector_filter and item["sector"] not in sector_filter)
            or (funding_filter and lead_stage(item, profile) not in funding_filter)):
            continue
        if age_options[age_filter] is not None:
            fits = age_fit(formation_record(item, profile), age_options[age_filter], today)
            if fits is None:
                unknown_age_count += 1
            if fits is False or (fits is None and not include_unknown):
                continue
        leads.append(item)
    if region_filter == ALL_EUROPE:
        leads.sort(key=lambda item: location_region(item, profile_for(item)) != GERMANY)
    count_message = f"Showing {len(leads)} of {len(candidates)} companies"
    if unknown_age_count:
        action = "included" if include_unknown else "hidden"
        count_message += f" · {unknown_age_count} with unverified age {action}"
    st.caption(count_message)

def clear_inbox_filters():
    st.session_state.update(inbox_region="All locations", inbox_age="Any age", inbox_query="",
                            inbox_sector=[], inbox_stage=[], show_shortlist=False, min_score=0)


item = None
if leads:
    queue, details = st.columns([2, 3], gap="large")
    with queue:
        st.subheader("Screening queue")
        selected_ids = st.session_state.setdefault("shortlisted", set())
        only_saved = st.checkbox("Shortlisted only", key="show_shortlist")
        visible = [lead for lead in leads if not only_saved or lead["id"] in selected_ids]
        if visible:
            by_id = {lead["id"]: lead for lead in visible}
            if st.session_state.get("selected_lead") not in by_id:
                st.session_state["selected_lead"] = next(iter(by_id))
            if len(by_id) <= 8:
                selection = st.radio("Open a dossier", list(by_id), key="selected_lead",
                                     format_func=lambda key: by_id[key]["name"],
                                     captions=[f'{x["score"]}/100 · {lead_stage(x, profile_for(x))}' +
                                               (" · Shortlisted" if x["id"] in selected_ids else "") for x in visible])
            else:
                selection = st.selectbox("Open a dossier", list(by_id), key="selected_lead",
                                         format_func=lambda key: f'{by_id[key]["name"]} · {by_id[key]["score"]}/100')
            item = by_id[selection]
            saved = selection in selected_ids
            if st.button("Remove from shortlist" if saved else "Add to shortlist",
                         key=f"save-{selection}"):
                if saved:
                    selected_ids.discard(selection)
                else:
                    selected_ids.add(selection)
                st.rerun()
            st.caption("Your shortlist is saved for this browser session.")
            with st.expander("Export this queue"):
                st.caption("These exports contain the original sourcing records. Curated profile checks appear in the dossier below.")
                st.download_button("Lead dossiers (JSON)", data=json.dumps(visible, ensure_ascii=False, indent=2),
                                   file_name="hidden_gem_leads.json", mime="application/json")
                buffer = io.StringIO()
                writer = csv.DictWriter(buffer, fieldnames=["name", "sector", "location", "origin",
                    "score", "lead_status", "funding_status", "source_url", "project_url"])
                writer.writeheader()
                for lead in visible:
                    writer.writerow({k: lead.get(k, "") for k in writer.fieldnames})
                st.download_button("Screening queue (CSV)", data=buffer.getvalue(),
                                   file_name="hidden_gem_leads.csv", mime="text/csv")
        else:
            st.info("Your shortlist has no matches here. Turn off Shortlisted only to review the full queue.")
    if item:
        with details:
            render_dossier(item)
elif candidates:
    st.info("No companies match this combination. Widen the region or age range, or clear a filter.")
    st.button("Review all source hits", on_click=clear_inbox_filters)
elif live_mode and "live_scan" in st.session_state:
    st.info("This scan returned no leads. Try another source or lookback window.")

render_sources(item)
