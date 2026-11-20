# FirstTrace competitive review and demo

Reviewed 20 November 2026. Platform descriptions come from vendor documentation and announcements. Competitive positioning is a product hypothesis.

| Platform | AI and where it is used | Implication for FirstTrace |
| --- | --- | --- |
| Harmonic | Scout handles natural-language research in Harmonic and Slack. Scheduled Scouts and structured searches can send matching leads to Slack. Stealth emergence is surfaced in company profiles and searches. [Scout in Slack](https://support.harmonic.ai/en/articles/15347952-scout-via-slack) · [Scheduled alerts](https://support.harmonic.ai/en/articles/5878370-slack-alerts) · [Stealth emergence](https://support.harmonic.ai/en/articles/11586000-stealth-emergence) | Alerts and a chatbot are familiar. Link each alert to the specific change and the scout’s original question. |
| Dealroom | The web platform combines company profiles, signals, ecosystem maps and alerts. Its API and MCP server expose company search and analysis to external AI clients. [Product FAQ](https://dealroom.co/faq/) · [API and MCP](https://knowledge.dealroom.co/knowledge/model-context-protocol-mcp-support-for-dealroom-api) | Use dated coverage as a comparison when available. Build a trail back to the local source that came first. |
| Crunchbase | Predictive filters and saved searches support screening in the web app. Its MCP server exposes company, funding and predictive data to subscribed AI workflows. [Search and predictions](https://support.crunchbase.com/hc/en-us/articles/360049781993-Filtering-Your-Searches-with-Insights-Predictions) · [MCP](https://data.crunchbase.com/docs/getting-started-with-mcp) | Pair a transparent sourcing score with a separately displayed funding review and factual gaps. |
| PitchBook | Origin markets AI-assisted search and alerts on early-stage founder and company signals. PitchBook AI offers scheduled agents, reports with citations, and a data MCP for external systems. [Origin](https://pitchbook.com/products/pitchbook-origin) · [PitchBook AI and MCP](https://pitchbook.com/media/press-releases/pitchbook-launches-an-agentic-platform-assistant-and-new-pitchbook-data-mcp-to-meet-investors-rapidly-evolving-workflow-needs) | A small public-evidence product can compete on time to a specific decision in a specific mandate. |
| Affinity | Ascend works in its VC CRM, chat and external MCP clients. Agents prepare meetings, find warm intro paths and propose CRM updates. [Ascend product overview](https://www.affinity.co/blog/introducing-affinity-ascend) | Make it easy to hand off a call brief and evidence, with the scout owning the decision. |

## What FirstTrace can demonstrate

1. Run live discovery or open the latest stored scan. Open **Rapid Resilience**, inspect the named founder, dated festival signal, funding-review scope, and the pilot question. Score comes from the shared engine. The registration publication belongs in the timeline, with formation age still unverified. [Public festival report](https://www.munich-startup.de/en/110579/impact-area-at-the-munich-startup-festival/)
2. Ask a teammate to make a decision using the evidence, then save **Meet**, **Watch**, or **Pass**, a reason and an owner. If watching, specify a new sourced milestone, a customer or pilot claim, or a public equity round. Compare a timed decision against an ordinary browser-based search. A historical shortlist or an analyst score alone does not measure outreach quality.
3. Open **Historical replay** and make the call on Constellate using the dated conference report. The reveal shows a 334-day interval to Dealroom News coverage. This is one curated comparison. The database’s first listing and FirstTrace’s historical detection time remain unknown.
4. In the research snapshot, open **TerraTask**. Its core profile gains an organizer-published signal naming the municipality of Wandlitz and a municipal participant. Ask what would turn their pilot into a paid rollout. The organizer programme establishes the named pilot, while pricing and measured outcomes remain open. [Smart City Berlin programme](https://smart-city-berlin.de/events/scc2026)
5. Open **New since review** to see newly shortlisted leads or evidence matched to a saved Watch criterion. A partial or failed run is visible. The analyst brief uses linked evidence, and the Markdown download works without a model call.

## Automation runbook

The Streamlit desk and schedule runner share a local SQLite file. Use one absolute `FIRSTTRACE_DB_PATH`, or run both under the same service account so the default path matches. The database stores public scan payloads and scout-entered reasons. Keep it on the host with restricted access. The demo assumes a single trusted workspace.

From the deployed repository, run `python scout_inbox.py --db /absolute/path/to/desk.sqlite3`. The command emits JSON with source outcomes, newly shortlisted count and Watch matches. Two consecutive captures of the same evidence should emit zero new items on the second run. An all-source failure exits 1 and preserves the last usable scan for review. Partial success retains source warnings.

Import the [inactive n8n template](../automation/n8n-firsttrace.json) or configure the workflow manually. Replace the sample checkout and database paths and choose a dedicated SSH credential. The template schedules weekdays at 08:00 Berlin time once enabled.

1. **Manual Trigger** for the first two validation runs. Add **Schedule Trigger**, e.g. 08:00 Europe/Berlin on weekdays, once the runner is reachable and the output is stable.
2. **SSH → Execute Command** with a dedicated credential to the host running the dashboard. Set the working directory to the repository checkout, and set the command to the deployment's virtualenv Python plus `scout_inbox.py --db /absolute/path/to/desk.sqlite3`. The command is fixed. Credentials live in the deployment environment or n8n credential store.
3. Inspect the exit status and parse the JSON from stdout on success. Route failed scans and partial-source warnings to operator review. Keep scout decisions in the dashboard.
4. Optional internal digest once the team chooses a destination. Post only nonzero change counts and a link to the desk. Keep founder outreach and CRM updates for human approval.

[n8n Schedule Trigger](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.scheduletrigger/) · [n8n SSH node](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.ssh/) · [n8n error handling](https://docs.n8n.io/flow-logic/error-handling/)

The implemented scanner uses Victor’s source coverage. A Watch decision observes evidence in that payload. Customer-side and financing coverage will improve when dedicated sources feed verified claims. Scheduled execution in a connected n8n instance requires a configured runner and credentials.

## After the demo

- **Buyer-side verification.** Add one connector for named awarding bodies or public pilot programmes. Join exact domains or legal entities, preserve the original notice, and distinguish a pilot or award from a tender invitation. Test the source on known positives and lookalike negatives. [TED Search API](https://docs.ted.europa.eu/api/latest/search.html)
- **Measure earliness prospectively.** Keep the runner’s first-observed timestamp and separately capture dated database observations across a small cohort. Report sample size, coverage and median lead time where comparable. Publish the denominator of cases with unknown baselines.
- **Prepare the first call.** Use OpenAI for evidence-linked questions and concise briefs with explicit coverage gaps. An optional ElevenLabs audio version can read an analyst-reviewed brief before a meeting. [ElevenLabs text-to-speech](https://elevenlabs.io/docs/overview/capabilities/text-to-speech)
