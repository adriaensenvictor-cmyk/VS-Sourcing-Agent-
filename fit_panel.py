"""Founder–venture fit dossier section for the Streamlit dashboard."""
import os

import streamlit as st

from fit_analysis import QUESTIONS, cache_key, request_analysis
from founder_fit import AGE_LABELS


def display_score(score):
    return "Unknown" if score is None else f"{score}/100"


def render_fit(fit):
    st.subheader("Founder–Venture Fit")
    st.write(fit["assessment"])
    founder, venture, joint = st.columns(3)
    founder.metric("Founder Potential", display_score(fit["founder"]["score"]))
    venture.metric("Venture Potential", display_score(fit["venture"]["score"]))
    joint.metric("Fit assessment", display_score(fit["score"]))
    st.caption(f'{fit["coverage"]}. Points reflect documented strengths. Unknown criteria remain open.')
    eligibility = fit["three_year_eligibility"]
    st.write(f'**Three-year eligibility** · {AGE_LABELS[eligibility["status"]]}')
    if eligibility["formation_date"]:
        st.caption(f'Legal formation · {eligibility["formation_date"]}')
    st.caption(f'{eligibility["reason"]} · assessed {eligibility["as_of"]}')
    for item in eligibility["evidence"]:
        st.text(item["text"])
        st.caption(item["source_url"])
    if eligibility["university_review"]:
        st.caption("University project · retain for formation and potential review.")
    for key, title in (("founder", "Founder evidence"), ("venture", "Venture evidence")):
        axis = fit[key]
        with st.expander(title):
            criteria = axis["strengths"] + axis["limitations"] + axis["conflicts"]
            for item in fit["evidence"]:
                if item["criterion"] in criteria:
                    subject = item.get("subject")
                    st.text(f'{subject} · {item["text"]}' if subject else item["text"])
                    st.caption(f'{item["criterion"].replace("_", " ")} · {item["direction"]} · {item["source_url"]}')
            for label, items in (("Verify", axis["missing"]), ("Conflicting evidence", axis["conflicts"])):
                if items:
                    st.caption(f'{label} · ' + ", ".join(value.replace("_", " ") for value in items))

    key = cache_key(fit)
    cache = st.session_state.setdefault("fit_analysis_cache", {})
    if st.button("Generate AI diligence assessment", disabled=not os.getenv("OPENAI_API_KEY")
                 or not fit["evidence"] or key in cache, help="Optional. Sends cited excerpts to OpenAI."):
        try:
            result = request_analysis(fit)
            if result:
                cache[key] = result
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            st.warning("AI assessment unavailable. The evidence and deterministic evaluation are available above.")
    if key in cache:
        result = cache[key]
        fact = fit["evidence"][result["evidence_id"]]
        st.write(f'AI diligence judgment · investigate {result["priority"]}')
        st.text(QUESTIONS[result["question"]])
        st.caption("Public evidence selected by the model")
        st.text(fact["text"])
        st.caption(fact["source_url"])
