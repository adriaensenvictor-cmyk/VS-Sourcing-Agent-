"""Hidden Gem — an evidence-first scouting cockpit for High-Tech Gründerfonds."""
import csv
import io
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import streamlit as st
from engine import load_research_snapshot, run_live

def funding_stage(status):
    """Group explicit round labels for display while preserving the source wording."""
    text = (status or "").casefold()
    if not text or re.search(r"unknown|unverified|not verified|not confirmed|no funding found|no equity|seeking|planned|targeting", text):
        return "Unverified"
    if re.search(r"\bpre[ -]seed\b", text):
        return "Pre-seed"
    match = re.search(r"\bseries[ -]([a-z])\b", text)
    if match:
        return {"a": "Series A", "b": "Series B"}.get(match[1], "Series C+")
    if re.search(r"\bseed\b", text):
        return "Seed"
    if re.search(r"\bgrowth\b", text):
        return "Growth"
    return "Other / review"


def evidence_date(value):
    """Parse ISO evidence dates without guessing from text or using today's date."""
    try:
        parsed = datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def safe_url(value):
    try:
        parsed = urlparse(value or "")
        return value if parsed.scheme in {"http", "https"} and parsed.hostname else None
    except (ValueError, AttributeError):
        return None


st.set_page_config(page_title="FirstTrace | HTGF Scout", layout="wide")
st.markdown("""
<style>
[data-testid="stMainBlockContainer"] {max-width:1240px;padding-top:2.1rem}
.firsttrace-hero {background:linear-gradient(115deg,#112c25,#205244);color:#f5fff8;
                 border-radius:1.25rem;padding:clamp(1.25rem,4vw,3rem);margin-bottom:1rem}
.firsttrace-hero h1 {color:#fff;font-size:clamp(2.2rem,6vw,4.25rem);
                    letter-spacing:-.045em;line-height:1.05;margin:.35rem 0 .75rem;padding:0}
.firsttrace-hero p {color:#d6eadd;margin:0}
.firsttrace-hero .desk {font-size:.8rem;letter-spacing:.075em;text-transform:uppercase}
div[data-testid="stMetric"] {border:1px solid rgba(78,118,97,.28);border-radius:.75rem;padding:.7rem}
</style>
<div class="firsttrace-hero">
  <p class="desk">FirstTrace · HTGF sourcing desk</p>
  <h1>Find the founders early.</h1>
  <p>Review startup signals, compare evidence and decide who to meet.</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Discovery settings")
    mode = st.radio("Data mode", ["Live discovery", "Verified research snapshot"],
                    help="Snapshot cases are manually researched examples, NOT automatic discoveries.")
    sources = st.multiselect("Public sources", ["Campus", "Hacker News", "GitHub"],
                             default=["Campus", "Hacker News", "GitHub"],
                             disabled=mode != "Live discovery")
    days = st.slider("Lookback window (days)", 30, 365, 180, step=30)
    minimum = st.slider("Minimum review score", 0, 100, 0, step=5)
    token = os.environ.get("GITHUB_TOKEN", "")
    st.caption("Optional GITHUB_TOKEN environment variable increases API allowance. Never paste keys into a public demo.")
    run = st.button("🔎 Run sourcing engine", type="primary", use_container_width=True)
    st.divider()
    st.caption("Scoring is rules-based and auditable. Human funding and company checks remain mandatory.")

@st.cache_data(ttl=900, show_spinner=False)
def cached_live(which, days, has_token, token_value):
    return run_live(which, days, token_value if has_token else None)

if ("leads" not in st.session_state or run
    or (mode == "Verified research snapshot" and st.session_state.get("scanned_mode") != mode)):
    if mode == "Verified research snapshot":
        st.session_state["leads"] = load_research_snapshot()
        st.session_state["errors"] = []
        st.session_state["scanned_mode"] = "Verified research snapshot"
    elif run:
        with st.spinner("Checking public early signals..."):
            items, errors = cached_live(tuple(sources), days, bool(token), token)
        st.session_state["leads"] = items
        st.session_state["errors"] = errors
        st.session_state["scanned_mode"] = "Live discovery"
    else:
        st.session_state["leads"] = []
        st.session_state["errors"] = []
        st.session_state["scanned_mode"] = "Not scanned"

scanned_mode = st.session_state["scanned_mode"]
candidates = st.session_state["leads"]
errors = st.session_state.get("errors", [])
st.caption(f"Data mode: {scanned_mode} · Scores prioritize review. Grants and equity are tracked separately.")
if scanned_mode == "Verified research snapshot":
    st.info("Reference snapshot · Manually researched cases collected on 20 Nov 2026.")
elif scanned_mode == "Not scanned":
    st.write("Run discovery from the sidebar, or choose the research snapshot for an offline walkthrough.")
for err in errors:
    st.error(f"Source unavailable: {err}")

leads = []
if candidates:
    st.subheader("Lead inbox")
    search = st.text_input("Search leads", placeholder="Search companies, founders or locations")
    sectors, stages = st.columns(2)
    with sectors:
        sector_filter = st.multiselect("Sectors", sorted({x["sector"] for x in candidates}))
    with stages:
        funding_filter = st.multiselect("Funding stages", [
            "Pre-seed", "Seed", "Series A", "Series B", "Series C+",
            "Growth", "Other / review", "Unverified",
        ])
    for item in candidates:
        searchable = " ".join(str(item.get(key) or "") for key in (
            "name", "team", "sector", "location", "origin", "description",
        )).casefold()
        if (item["score"] >= minimum
            and all(word in searchable for word in search.casefold().split())
            and (not sector_filter or item["sector"] in sector_filter)
            and (not funding_filter or funding_stage(item.get("funding_status")) in funding_filter)):
            leads.append(item)
    st.caption(f"{len(leads)} of {len(candidates)} leads match your filters")

if leads:
    queue, details = st.columns([2, 3], gap="large")
    with queue:
        st.subheader("Opportunities")
        by_id = {lead["id"]: lead for lead in leads}
        selection = st.selectbox("Select a startup", list(by_id),
                                 format_func=lambda key: f'{by_id[key]["name"]} · {by_id[key]["score"]}/100')
        st.dataframe([
            {"Project": x["name"], "Score": x["score"], "Funding": funding_stage(x.get("funding_status"))}
            for x in leads
        ], hide_index=True, use_container_width=True)
    with details:
        item = by_id[selection]
        st.header(item["name"])
        score, funding = st.columns([1, 2])
        score.metric("Review score", f'{item["score"]}/100')
        funding.caption("Funding status")
        funding.write(item.get("funding_status") or "Unverified")
        st.caption(f'{item["sector"]} · {item["location"]} · {item["origin"]}')
        st.write(item["description"][:1300])
        st.write(f'**Founding team** · {item["team"] or "Unverified"}')
        for label, key in (("Open project", "project_url"), ("Open discovery source", "source_url")):
            if url := safe_url(item.get(key)):
                st.link_button(label, url)

        timeline, scoring, diligence = st.tabs(["Evidence timeline", "Score breakdown", "Diligence"])
        with timeline:
            dated = []
            undated = []
            for evidence in item["evidence"]:
                entry = (evidence_date(evidence.get("observed_at")), evidence)
                (dated if entry[0] else undated).append(entry)
            if not dated and not undated:
                st.caption("No evidence entries are available for this lead.")
            for stamp, evidence in sorted(dated, key=lambda entry: entry[0]) + undated:
                st.caption(stamp.date().isoformat() if stamp else "Date unverified")
                st.write(evidence["signal"])
                st.write(evidence["excerpt"])
                if url := safe_url(evidence.get("url")):
                    st.link_button("Open evidence source", url)
        with scoring:
            st.caption("Points supplied by the sourcing engine.")
            if item["score_components"]:
                st.table([{"Signal": name, "Points": points}
                          for name, points in item["score_components"].items()])
        with diligence:
            for warning in item["warnings"]:
                st.write("• " + warning)
            st.caption("Confirm team identity and equity financing before outreach. Compare publication dates against a dated baseline to assess earliness.")
    st.divider()
    st.subheader("Download the evidence trail")
    st.download_button("Export lead dossiers (JSON)",
          data=json.dumps(leads, ensure_ascii=False, indent=2),
          file_name="hidden_gem_leads.json", mime="application/json")
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["name", "sector", "location", "origin",
                      "score", "lead_status", "funding_status", "source_url", "project_url"])
    writer.writeheader()
    for lead in leads:
        writer.writerow({k: lead.get(k, "") for k in writer.fieldnames})
    st.download_button("Export screening queue (CSV)", data=buffer.getvalue(),
                       file_name="hidden_gem_leads.csv", mime="text/csv")
else:
    st.warning("No leads under the current settings. This is not evidence that none exist. "
               "Try another lookback window or a different source; check source errors above.")

with st.expander("Scouting methodology · limitations · HTGF fit"):
    st.markdown("""
**Goal:** surface German deep-tech and technology teams before their first funding round.

**Live sources:**
- TU Berlin: follows links from the public 2026 venture directory, then reads team and
  EXIST support from each venture profile (subject to the site's accessibility).
- Hacker News: searches Show HN and requires self-reported German location.
- GitHub: finds recent technical repositories and verifies a German profile location.
  Public project owners are **not automatically confirmed founders**.

**Originality of signals:** research-to-product transfer, founder-team trace, explicit
pilot/customer language, code artifact, university venture support and cross-source corroboration.

**Important limits:** scores are transparent heuristic priorities and capped if no founding team
is identified. The system cannot infer that a startup is unfunded from silence in databases.
Claims about being first require dated baseline evidence from those databases. Public research
grants are not equivalent to VC equity rounds.

**Safe use:** no private data enrichment or automated unsolicited outreach. Respect publisher
access restrictions and GitHub API rate limits. A human must validate any investor outreach.
""")
