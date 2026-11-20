Hidden gem

#Team
Matei
Mathia
Victor
Jinansh

# FounderRadar

FounderRadar surfaces potential German and European founding teams for the HTGF Venture Capital Challenge. It combines existing TUM and Show HN discovery with a small public GitHub sample and a reviewed EXIST-related announcement.

## Reproduce

From the repository root, with Python 3.9+ and network access:

```sh
python3 -m unittest discover -v
python3 emergence.py --github-limit 4 --limit 10 > founder-shortlist.json
python3 radar.py --json --limit 10 > legacy-radar.json
```

An optional `FOUNDER_RADAR_GITHUB_TOKEN` increases the GitHub API quota. A public GitHub search failure or sample failure can reduce coverage. To run without GitHub collection, pass `--github-limit 0`. The database-free legacy flow and its dashboard JSON remain available. See [RADAR.md](RADAR.md) for that schema.

## Read the shortlist

`shortlist` contains up to ten eligible candidates, with Germany prioritized. `manual_review` gives up to three candidate IDs. `candidates` includes excluded records and their reasons. Each candidate includes sourced claims, geographic confidence, funding verification, a timeline and separate dimensions that add up to 100. Commercial evidence carries the highest weight, and GitHub stars carry none.

Funded and reported later-stage leads are excluded from the shortlist. Projects lacking location or commercial evidence and projects with clear hobby or agency cues are also excluded. Unknown funding can appear in the shortlist with a visible verification gap. A public funding search records its scope, and a grant does not establish an equity round. The TUM recruitment announcement describes an EXIST application rather than an award.

GitHub searches use recent creation and push dates plus product keywords. The engine samples up to 50 recent commits and 20 releases per selected repository. Two non-bot accounts, each active across at least two sampled weeks, are needed for the collaboration signal. Repository creation date is shown as metadata because public visibility at creation is unknown. Founder names require a public source and are not inferred from contributor identity or profile location. GitHub README wording about geographic location is self-reported. The EXIST input is a single reviewed source, and matching across collectors uses an exact website or repository identity. The output is a research shortlist and needs human verification before outreach.
