"""Cited evidence for the investor-facing screen."""
import streamlit as st

from pre_vc import LABEL


def show_review(review):
    st.subheader("Pre-VC review")
    st.write(LABEL if review["status"] == "present" else review["status"].capitalize())
    for reason in review["reasons"]:
        st.caption(reason)
    for item in review["evidence"].values():
        st.text(f'{item["date"]} · {item["summary"]}')
        st.caption(item["url"])
