"""Package one portable HTML report with its data, styles and behavior."""
import json
from pathlib import Path

from sources import SOURCES

UI = Path(__file__).resolve().parent / "ui"


def render(snapshot, leads, replay, server=False):
    sources = [
        {"label": label, "url": url, **snapshot.get("source_status", {}).get(key, {})}
        for key, (label, url) in SOURCES.items()
        if key in snapshot.get("source_status", {"campus": {}, "github": {}})
    ]
    data = {
        "mode": "Snapshot replay" if replay else "Live scan",
        "cutoff": snapshot.get("cutoff"),
        "observedAt": snapshot["observed_at"],
        "total": len(snapshot["projects"]),
        "errors": snapshot["errors"],
        "hasBaseline": snapshot.get("has_baseline", False),
        "server": server,
        "sources": sources,
        "leads": leads,
    }
    # Keep source text inert even if it includes an HTML closing tag.
    payload = json.dumps(data, ensure_ascii=True).replace("<", "\\u003c")
    return (
        (UI / "report.html").read_text(encoding="utf-8")
        .replace("/* FIRSTTRACE_STYLE */", (UI / "report.css").read_text(encoding="utf-8"))
        .replace("/* FIRSTTRACE_SCRIPT */", (UI / "report.js").read_text(encoding="utf-8"))
        .replace("FIRSTTRACE_PAYLOAD", payload)
    )
