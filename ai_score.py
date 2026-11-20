"""Generate separate AI investment reports for First Trace candidate JSON.

Example:
    python ai_score.py candidates.json --output ai_evaluations.json
"""

import argparse
import json
import sys
from pathlib import Path

from ai_scoring import AIScoringError, evaluate_candidate


def _read_json(path):
    try:
        source = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
        return json.loads(source)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("{}: {}".format(path, error)) from None


def _candidate_rows(candidate_data):
    if isinstance(candidate_data, dict) and isinstance(candidate_data.get("candidates"), list):
        candidates = candidate_data["candidates"]
    elif isinstance(candidate_data, dict):
        candidates = [candidate_data]
    elif isinstance(candidate_data, list):
        candidates = candidate_data
    else:
        raise ValueError("candidate input must be a JSON object, candidate array, or First Trace envelope")
    if not candidates or any(not isinstance(item, dict) for item in candidates):
        raise ValueError("candidate input must contain one or more candidate objects")
    return candidates


def _evaluation_candidates(candidate_data, all_candidates=False):
    candidates = _candidate_rows(candidate_data)
    return candidates if all_candidates else candidates[:1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", help="JSON object or array from radar.py --json")
    parser.add_argument(
        "--investor-profile",
        help="Optional JSON file describing the fund's sectors, geography, and stage preferences",
    )
    parser.add_argument(
        "--output",
        default="ai_evaluations.json",
        help="Output JSON path (default: ai_evaluations.json); use - for stdout",
    )
    parser.add_argument("--all-candidates", action="store_true",
                        help="Evaluate every candidate in the input; may make many paid API calls")
    parser.add_argument("--no-cache", action="store_true", help="Do not read or write the local SQLite cache")
    args = parser.parse_args(argv)

    try:
        candidate_data = _read_json(args.candidates)
        candidates = _evaluation_candidates(candidate_data, args.all_candidates)

        investor_profile = _read_json(args.investor_profile) if args.investor_profile else None
        if investor_profile is not None and not isinstance(investor_profile, dict):
            raise ValueError("investor profile must be a JSON object")

        reports = [
            evaluate_candidate(
                candidate,
                investor_profile,
                use_cache=not args.no_cache,
            )
            for candidate in candidates
        ]
        rendered = json.dumps(reports, indent=2, ensure_ascii=False)
        if args.output == "-":
            print(rendered)
        else:
            Path(args.output).write_text(rendered + "\n", encoding="utf-8")
            print("Wrote {} evaluation(s) to {}".format(len(reports), args.output))
        return 0
    except (AIScoringError, OSError, ValueError) as error:
        print("AI scoring failed: {}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
