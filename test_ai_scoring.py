import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from ai_scoring import (
    MissingAPIKeyError,
    OpenAIRequestError,
    WEIGHTS,
    evaluate_candidate,
)


def model_result(**overrides):
    result = {
        "investment_thesis": "Insufficient sourced information for a thesis.",
        "thesis_evidence_urls": [],
        "founder_assessments": [],
        "dimensions": [
            {
                "criterion": criterion,
                "score": None,
                "rationale": "Not assessable.",
                "evidence_urls": [],
            }
            for criterion in WEIGHTS
        ],
        "early_stage_confidence": None,
        "evidence_confidence": 10,
        "germany_focus": "unconfirmed",
        "positive_signals": [],
        "red_flags": [],
        "missing_information": ["Product and team evidence are missing."],
    }
    result.update(overrides)
    return result


def mocked_response(result):
    response = MagicMock()
    response.read.return_value = json.dumps({
        "status": "completed",
        "output": [{
            "type": "message",
            "content": [{
                "type": "output_text",
                "text": json.dumps(result),
            }],
        }],
    }).encode("utf-8")
    response.__enter__.return_value = response
    return response


class AIScoringTests(unittest.TestCase):
    def test_incomplete_candidate_returns_insufficient_evidence(self):
        candidate = {"id": "sparse", "title": "Sparse lead"}
        with tempfile.TemporaryDirectory() as directory, patch(
            "ai_scoring.urlopen", return_value=mocked_response(model_result())
        ):
            result = evaluate_candidate(
                candidate, api_key="test-key", cache_path=Path(directory) / "cache.sqlite"
            )

        self.assertEqual(result["candidate_id"], "sparse")
        self.assertIsNone(result["investment_attractiveness_score"])
        self.assertEqual(result["score_coverage"], 0)
        self.assertEqual(result["funding_status"], "unknown")
        self.assertEqual(result["founder_assessments"], [])
        self.assertTrue(any("Founder identities" in item for item in result["missing_information"]))

    def test_missing_founder_information_drops_model_invented_founder(self):
        candidate = {
            "id": "no-founder",
            "title": "Unattributed project",
            "source_url": "https://example.org/project",
            "evidence": [{"excerpt": "A prototype is being built.", "source_url": "https://example.org/project"}],
        }
        raw = model_result(founder_assessments=[{
            "name": "Invented Person",
            "background_summary": "A fabricated biography.",
            "experience_relevance": "Unknown.",
            "evidence_urls": ["https://example.org/project"],
        }])
        with tempfile.TemporaryDirectory() as directory, patch(
            "ai_scoring.urlopen", return_value=mocked_response(raw)
        ):
            result = evaluate_candidate(
                candidate, api_key="test-key", cache_path=Path(directory) / "cache.sqlite"
            )
        self.assertEqual(result["founder_assessments"], [])

    def test_score_requires_source_url_from_candidate(self):
        candidate = {
            "id": "source-check",
            "title": "Project",
            "source_url": "https://example.org/project",
            "evidence": [],
        }
        dimensions = [{
            "criterion": criterion,
            "score": 5,
            "rationale": "A model claim.",
            "evidence_urls": ["https://made-up.example/evidence"],
        } for criterion in WEIGHTS]
        raw = model_result(dimensions=dimensions)
        with tempfile.TemporaryDirectory() as directory, patch(
            "ai_scoring.urlopen", return_value=mocked_response(raw)
        ):
            result = evaluate_candidate(
                candidate, api_key="test-key", cache_path=Path(directory) / "cache.sqlite"
            )
        self.assertIsNone(result["investment_attractiveness_score"])
        self.assertEqual(result["score_coverage"], 0)
        self.assertTrue(all(item["score"] is None for item in result["dimensions"]))

    def test_unknown_funding_stays_unknown(self):
        candidate = {
            "id": "unknown-funding",
            "title": "Early project",
            "funding": {"status": "unknown", "reviews": []},
        }
        with tempfile.TemporaryDirectory() as directory, patch(
            "ai_scoring.urlopen", return_value=mocked_response(model_result())
        ):
            result = evaluate_candidate(
                candidate, api_key="test-key", cache_path=Path(directory) / "cache.sqlite"
            )
        self.assertEqual(result["funding_status"], "unknown")
        self.assertIn("unknown", result["funding_note"].lower())

    def test_cached_result_avoids_second_api_call(self):
        candidate = {
            "id": "cache-test",
            "title": "Cache test",
            "source_url": "https://example.org/",
        }
        with tempfile.TemporaryDirectory() as directory, patch(
            "ai_scoring.urlopen", return_value=mocked_response(model_result())
        ) as request:
            cache_path = Path(directory) / "cache.sqlite"
            first = evaluate_candidate(candidate, api_key="test-key", cache_path=cache_path)
            second = evaluate_candidate(candidate, api_key="test-key", cache_path=cache_path)
        self.assertEqual(first, second)
        request.assert_called_once()

    def test_missing_api_key_has_clear_error(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True), patch(
            "ai_scoring.urlopen"
        ) as request:
            with self.assertRaises(MissingAPIKeyError):
                evaluate_candidate(
                    {"id": "no-key"},
                    cache_path=Path(directory) / "cache.sqlite",
                )
        request.assert_not_called()

    def test_network_failure_has_clear_error(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "ai_scoring.urlopen", side_effect=URLError("offline")
        ):
            with self.assertRaisesRegex(OpenAIRequestError, "Could not reach"):
                evaluate_candidate(
                    {"id": "offline"},
                    api_key="test-key",
                    cache_path=Path(directory) / "cache.sqlite",
                )


if __name__ == "__main__":
    unittest.main()
