"""Read the public BVIZ directory independently of the startup lead queue."""
from engine import get_html
from scout_inbox import valid_url


BVIZ_DIRECTORY = "https://innovationszentren.de/mitglieder-zentren/ordentliche-mitglieder/"
PROGRAMME_FINDER = "https://www.de-hub.de/en/programfinder/"
FEDERAL_NETWORK = "https://www.bundeswirtschaftsministerium.de/Redaktion/DE/Dossier/startup-factories-gewinner.html"


def read_centres():
    page = get_html(BVIZ_DIRECTORY)
    centres = {}
    for site in page.select(".mitglied-standort"):
        heading = site.select_one(".mitglied-standort-titel")
        if not heading:
            continue
        name = heading.get_text(" ", strip=True)
        address = site.select_one('a[title="Routenplaner"]')
        location = address.get_text(" ", strip=True) if address else ""
        website = next((valid_url(a["href"]) for a in site.select(".mitglied-standort-inhalt a[href]")
                        if a.get_text(" ", strip=True).casefold() == "website"), None)
        if name:
            centres[(name, location)] = {"Centre": name, "Address": location, "Website": website}
    if not centres:
        raise ValueError("No centre records found")
    return sorted(centres.values(), key=lambda row: row["Centre"].casefold())
