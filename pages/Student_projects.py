"""Public secondary-school projects for manual follow-up."""
import json

import streamlit as st

from pre_vc import annotate
from pre_vc_panel import show_review
from student_watchlist import refresh

st.set_page_config(page_title="Student projects | First Trace", layout="wide")
st.title("Student project watchlist")
st.caption("School and event evidence for early follow-up. Company location, formation and equity funding require diligence.")

if "student_watch" not in st.session_state:
    st.session_state.student_watch = refresh()
if st.button("Check public school and event sources"):
    previous = st.session_state.student_watch
    with st.spinner("Checking the public rosters and school announcements…"):
        st.session_state.student_watch = refresh(live=True, previous=previous if previous["mode"] == "live" else None)
run = st.session_state.student_watch

show_research = st.toggle("Include research projects awaiting verification", value=False)
if run["mode"] == "research_snapshot":
    st.info("Reviewed snapshot · five project dossiers researched on 20 November 2026.")
else:
    st.caption(f'Last source check · {run["generated_at"]}')
    for url, source in run["sources"].items():
        if source["status"] == "error":
            st.warning(f"Source unavailable · {url}. Earlier evidence remains visible with its original dates.")
    if show_research and run["changes"]:
        with st.expander(f'{len(run["changes"])} listing changes since your last check'):
            names = {p["id"]: p["name"] for p in run["student_watchlist"]}
            for update in run["changes"]:
                st.write(names[update["project_id"]], "·", update["change"].replace("_", " "))
                st.caption(update["url"])

pool = annotate(run["student_watchlist"])
if not show_research:
    pool = [p for p in pool if p["pre_vc"]["status"] == "present"]
countries = sorted({p["school_country"] for p in pool})
country = st.selectbox("School or team country", ["All countries", *countries])
pool = [p for p in pool if country == "All countries" or p["school_country"] == country]
reviewed_only = show_research and st.toggle("Reviewed dossiers only", value=True)
pool = [p for p in pool if not reviewed_only or p["provenance"] == "reviewed"]
if pool:
    by_id = {p["id"]: p for p in pool}
    choice = st.selectbox("Project", list(by_id), format_func=lambda k: by_id[k]["name"])
    project = by_id[choice]
    st.subheader(project["name"])
    if project["description"]:
        st.text(project["description"])
    st.caption(f'{project["school_country"]} · Equity funding unknown · Formation date unknown')
    show_review(project["pre_vc"])
    st.write("**Next question**", project["review_question"])
    if project["signals"]:
        st.subheader("Reviewed evidence")
        for signal in sorted(project["signals"], key=lambda s: s["date"] or "9999"):
            st.write(signal["date"] or "Date unspecified", "·", signal["kind"].replace("_", " "))
            st.text(signal["text"])
            if signal.get("scheduled_for"):
                st.caption("Scheduled for " + signal["scheduled_for"] + " · outcome requires verification")
            st.caption(signal["basis"].replace("_", " "))
            st.markdown(f'[Original source]({signal["url"]})')
    if project.get("observations"):
        st.subheader("Live listings")
        for item in project["observations"]:
            st.text(item["text"])
            date_label = "Event edition" if item["kind"] == "event_listing" and len(item["date"] or "") == 4 else "Publication"
            st.caption(f'{item["kind"].replace("_", " ")} · {date_label}: {item["date"] or "date unknown"} · Last seen: {item["last_seen_at"][:10]}')
            st.markdown(f'[View listing]({item["url"]})')
        if project.get("profile_url"):
            st.link_button("Organizer project profile", project["profile_url"])
else:
    st.info("No matching projects. The presentation requires recent early-stage and financing evidence.")

export = {**run, "student_watchlist": pool, "presentation_ids": [p["id"] for p in pool if p["pre_vc"]["status"] == "present"]}
if not show_research:
    included = set(export["presentation_ids"])
    export["changes"] = [c for c in run["changes"] if c["project_id"] in included]
st.download_button("Export displayed projects (JSON)", json.dumps(export, ensure_ascii=False, indent=2),
                   file_name="student_watchlist.json", mime="application/json")
