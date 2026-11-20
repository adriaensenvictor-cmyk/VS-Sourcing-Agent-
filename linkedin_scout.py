"""Work with scout-submitted public LinkedIn references without fetching profiles."""
from datetime import date
from hashlib import sha256
import re
from urllib.parse import urlencode, urlsplit

from founder_employers import ALIASES, EMPLOYER_GROUPS
from founder_signals import founder_history
from qualification import claim, detect_intent, url_key


LINKEDIN_SOURCE = "LinkedIn (analyst submissions)"
PUBLIC_POST = "Analyst-submitted LinkedIn post"
SIGNALS = {
    "Announced a startup project": "formation_intent",
    "Looking for a co-founder": "formation_intent",
    "Announced a public launch": "launch",
}
SEARCHES = (
    ("Founders building in Germany", '"building a startup" AND (Germany OR Berlin OR München)'),
    ("Teams looking for a co-founder", '("looking for a co-founder" OR "Mitgründer gesucht") AND (Germany OR Deutschland)'),
    ("Repeat founders announcing a venture", '("my second startup" OR "back to building") AND (Germany OR Deutschland)'),
)


def post_url(value):
    """Accept post permalinks only. Remove tracking parameters and aliases."""
    value = value.strip()
    if any(c.isspace() for c in value) or "\\" in value:
        return None
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        if (parsed.scheme != "https" or parsed.username is not None or parsed.port
                or not re.fullmatch(r"(?:(?:www|[a-z]{2})\.)?linkedin\.com", host)):
            return None
        path = parsed.path.rstrip("/")
        if not (re.fullmatch(r"/posts/[^/]+", path)
                or re.fullmatch(r"/feed/update/urn:li:(?:activity|share|ugcPost):\d+", path)):
            return None
    except ValueError:
        return None
    return "https://www.linkedin.com" + path


def submitted_post(url, founder, venture, country, signal, note, *, website="", posted_on=None):
    source = post_url(url)
    if not source:
        raise ValueError("Enter the HTTPS permalink to a LinkedIn post.")
    founder, venture, note = founder.strip(), venture.strip(), note.strip()
    if not founder or not venture or not note or signal not in SIGNALS:
        raise ValueError("Enter the founder's public name, project, and a brief summary of the announcement.")
    if posted_on and posted_on > date.today():
        raise ValueError("The post date cannot be in the future.")
    website = website.strip()
    if website:
        try:
            key = url_key(website)
            parsed = urlsplit(website)
            if not key or key[0] != "website" or parsed.username or any(c.isspace() for c in website) or "\\" in website:
                raise ValueError
        except ValueError:
            raise ValueError("Use the official project website, or leave the field empty.") from None
    activity = re.search(r"(?:-activity-|/urn:li:activity:)(\d+)(?:\D|$)", source)
    reference = activity[1] if activity else source
    uid = "linkedin-post:" + sha256(reference.encode()).hexdigest()[:24]
    note = note[:700]
    cues = [claim(SIGNALS[signal], f"{signal}. {note}", source, "hypothesis")]
    return {
        "id": uid,
        "title": venture[:150],
        "source": LINKEDIN_SOURCE,
        "source_url": source,
        "description": note,
        "record_provenance": PUBLIC_POST,
        "project_url": website or None,
        "published_at": posted_on.isoformat() if posted_on else None,
        "location": {"country": country or None, "confidence": "self_reported" if country else "unknown",
                     "source_url": source if country else None},
        "evidence": [
            {"signal": PUBLIC_POST, "excerpt": note, "source_url": source},
            *founder_history(venture, [founder], [note], source),
        ],
        "founders": [{"name": founder[:120], "role": "Founder (reported in post)", "source_url": source}],
        "claims": cues + detect_intent(note, source),
        "funding": {"status": "unknown", "rounds": [], "reviews": [], "public_support": []},
        "timeline": [{"date": posted_on.isoformat(), "url": source, "label": "LinkedIn announcement · date supplied by scout"}]
        if posted_on else [],
    }


def linkedin_search(keywords):
    return "https://www.linkedin.com/search/results/content/?" + urlencode({"keywords": keywords})


def render_linkedin(store, countries):
    import streamlit as st

    st.header("LinkedIn scouting")
    st.caption("Search public launch and co-founder announcements, then save a sourced lead for review.")
    for column, (title, keywords) in zip(st.columns(2), SEARCHES[:2]):
        column.link_button(title, linkedin_search(keywords))
    with st.expander("Search by former employer"):
        category, company = st.columns(2)
        group = category.selectbox("Employer group", list(EMPLOYER_GROUPS), key="employer_group")
        employer = company.selectbox("Previous employer to search", EMPLOYER_GROUPS[group], key="employer_search")
        term = f'"{employer}"'
        if aliases := ALIASES.get(employer):
            term = f'({term} OR "{aliases[0]}")'
        st.link_button("Find founding announcements",
                       linkedin_search(f'{term} AND (founder OR Mitgründer)'))
        st.link_button("Find co-founder searches",
                       linkedin_search(f'{term} AND ("looking for a co-founder" OR "Mitgründer gesucht")'))
        st.caption("Look for posts that name the employer and describe a new venture.")
        for title, keywords in SEARCHES[2:]:
            st.link_button(title, linkedin_search(keywords))
    st.caption("In LinkedIn, use Posts and Date posted to narrow the results.")
    with st.form("linkedin_post_intake", clear_on_submit=True):
        st.subheader("Save a founder announcement")
        url = st.text_input("Public LinkedIn post link", max_chars=1500)
        left, right = st.columns(2)
        founder = left.text_input("Founder name", max_chars=120)
        venture = right.text_input("Venture or project", max_chars=150)
        country = left.selectbox("Country named in the post", (None, *countries),
                                 format_func=lambda value: value or "Needs verification")
        posted_on = right.date_input("Publication date", value=None, max_value=date.today())
        signal = st.selectbox("What the founder announced", list(SIGNALS))
        website = st.text_input("Official project website (optional)", max_chars=1000)
        note = st.text_area("Public facts in your own words", max_chars=700,
                            placeholder="What are they building? Who is mentioned? What remains uncertain?")
        if st.form_submit_button("Save source for next scan", type="primary"):
            try:
                record = submitted_post(url, founder, venture, country, signal, note,
                                        website=website, posted_on=posted_on)
            except ValueError as error:
                st.warning(str(error))
            else:
                store.save_linkedin_lead(record)
                st.success("Saved. Run the sourcing engine or let n8n pick it up on the next scan.")

    posts = store.linkedin_leads()
    if posts:
        st.subheader("Saved announcements")
        for index, record in enumerate(posts, start=1):
            st.text(record["title"] + " · " + record["founders"][0]["name"])
            st.link_button(f'Open post {index} · {record["title"]}', record["source_url"])
