"""Hidden Gem — an evidence-first scouting cockpit for High-Tech Gründerfonds."""
import csv
import io
import json
import os

import streamlit as st
from engine import load_research_snapshot, run_live

st.set_page_config(page_title="Hidden Gem | HTGF Scout", page_icon="💎",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
.stApp {background-color:#0b1020;color:#f4f5ff}
div[data-testid="stMetric"] {background:#171f36;border:1px solid #35405b;border-radius:12px;padding:12px}
h1,h2,h3 {letter-spacing:-.025em}
</style>
""", unsafe_allow_html=True)

st.title("💎 Hidden Gem")
st.caption("Early-stage founder intelligence · HTGF MAIN Summit 2026 · Evidence before hype")
st.info("Lead scores prioritize review; they are **not** investment recommendations or probabilities. "
        "Funding is **unverified** unless independently checked. A university grant is not a VC funding round.")

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

if "leads" not in st.session_state or run:
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
leads = [x for x in st.session_state["leads"] if x["score"] >= minimum]
errors = st.session_state.get("errors", [])
if scanned_mode == "Verified research snapshot":
    st.warning("DEMO RESEARCH MODE: these are genuine source-linked examples manually collected "
               "on 20 Nov 2026. They were NOT discovered by the live engine.")
elif scanned_mode == "Not scanned":
    st.write("Select sources and click **Run sourcing engine**. "
             "Or switch to the explicitly labelled reference snapshot for a reliable offline walkthrough.")
for err in errors:
    st.error(f"Source unavailable (other sources may still work): {err}")

if leads:
    a, b, c, d = st.columns(4)
    a.metric("Leads to review", len(leads))
    b.metric("Named founding teams", sum(bool(x["founder_identified"]) for x in leads))
    c.metric("German-location leads", sum("germany" in x["location"].lower()
              or "berlin" in x["location"].lower() for x in leads))
    d.metric("Evidence links", sum(len(x["evidence"]) for x in leads))
    st.subheader("Evidence-ranked opportunity queue")
    st.dataframe([
        {"Score /100": x["score"], "Project": x["name"], "Sector": x["sector"],
         "Location": x["location"], "Origin": x["origin"],
         "Team review": x["lead_status"], "Funding": "Not verified"}
        for x in leads
    ], hide_index=True, use_container_width=True)
    selection = st.selectbox("Investigate a lead", range(len(leads)),
                             format_func=lambda i: f'{leads[i]["name"]} · {leads[i]["score"]}/100')
    item = leads[selection]
    st.divider()
    st.header(item["name"])
    st.write(item["description"][:1300])
    st.write(f'**Investment sector:** {item["sector"]}  |  **Location:** {item["location"]}')
    st.write(f'**Founding team:** {item["team"] or "Not identified from available public evidence"}')
    st.write(f'**Source:** {item["source_url"]}')
    st.write(f'**Project:** {item["project_url"]}')
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Evidence ledger")
        for e in item["evidence"]:
            st.markdown(f'**{e["signal"]}** — {e["excerpt"]}')
            st.caption(e["url"] + (f' · {e["observed_at"]}' if e.get("observed_at") else ""))
        st.subheader("What a VC analyst should verify next")
        st.markdown("- Confirm the founding team and relevant commercial/IP experience\n"
                    "- Search press and funding databases for prior equity rounds\n"
                    "- Check pilots, customers, willingness to pay and addressable market\n"
                    "- Establish IP ownership and whether this is a startup rather than a side project\n"
                    "- Verify timing: earliest *public* trace versus first public funding announcement")
    with right:
        st.subheader("Why it was ranked here")
        st.caption("Heuristic prioritization, not a success probability")
        st.json(item["score_components"])
        st.subheader("Diligence warnings")
        for w in item["warnings"]:
            st.write("• " + w)
        st.markdown("**Funding conclusion:** Unknown — requires independent verification")
        st.markdown("**Earliness versus Dealroom/Crunchbase:** Not measured")
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
