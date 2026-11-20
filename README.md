# FirstTrace

FirstTrace scans Munich's university startup ecosystem for B2B software projects and brings evidence of the team, public product releases, and funding uncertainty into an investor's lead inbox.

## Run the demo

Python 3.9+ and a browser. Live mode uses public endpoints and needs no API key.

```sh
python3 scout.py --output report.html
open report.html
```

To rehearse offline or present during an outage, replay the captured live scan. The report labels the mode and original observation time.

```sh
python3 scout.py --replay data/demo-snapshot.json --output report.html
open report.html
```

To capture a fresh snapshot, run `python3 scout.py --snapshot data/demo-snapshot.json`. The capture stores derived source tags and release metadata. Review records and repository associations in [data/reviews.json](data/reviews.json) are human-curated. The scan automatically finds candidate names from the whole cohort and fetches public releases only for those associations. The score measures evidence coverage. Assess investment merit separately.

## Team workspace

- [Prompt for Codex and Claude](planning/PROMPT.md)
- [HTGF research and concept selection](planning/RESEARCH.md)
- [18-hour build plan and team workflow](planning/BUILD.md)
- [Best find, validation and pitch](planning/DEMO.md)
- [Agent instructions](AGENTS.md)
