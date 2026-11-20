"""A manually reconstructed case with controlled disclosure of later evidence."""
from datetime import date

import streamlit as st


COMPETITION = "https://www.dutchlifesciences.com/news/article/135/myriagon-wins-venture-challenge-fall-2025"
DEALROOM = "https://dealroom.co/news/164193-tu-delft-spinout-constellate-raises-pre-seed-to-speed-up-antibody-screen/"
INVESTOR = "https://www.graduate.nl/insights/new-pre-seed-investment-constellate-proteomics"
CUTOFF = date(2025, 11, 20)
COVERAGE = date(2026, 10, 20)


def render_replay():
    st.header("Make the early call")
    st.caption("Curated historical case · Evidence available by 20 November 2025")
    st.subheader("Constellate Proteomics")
    st.write("The Dutch Life Sciences Conference listed Constellate in the autumn Venture Challenge. "
             "The programme named Dennis de Beeld, Carlos de Lannoy and Arian Khoshchin "
             "and described a single-droplet approach to screening cell lines.")
    st.link_button("Read the original conference report", COMPETITION)
    st.caption("This case presents the dated conference evidence. Formation, traction and equity have yet to be established at this cutoff.")
    with st.form("replay_vote"):
        vote = st.radio("What would you do at this point?", ["Meet", "Watch", "Pass"], horizontal=True)
        if st.form_submit_button("Save decision and reveal"):
            st.session_state["replay_decision"] = vote
    if decision := st.session_state.get("replay_decision"):
        st.write(f"**Your decision** · {decision}")
        st.metric("Conference report to Dealroom News coverage", f"{(COVERAGE - CUTOFF).days} days")
        st.write("On 20 October 2026 Graduate Ventures announced a pre-seed investment. Dealroom News covered the round the same day.")
        st.caption("The date of the first database listing and FirstTrace’s historical discovery time are unknown.")
        st.link_button("Read the investor announcement", INVESTOR)
        st.link_button("Read the Dealroom News story", DEALROOM)
        if st.button("Reset replay"):
            del st.session_state["replay_decision"]
            st.rerun()
