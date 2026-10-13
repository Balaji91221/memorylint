"""Offline held-out fixture evaluation; the same scorer accepts a real provider factory."""

import json
from pathlib import Path
import tempfile

from .evidence import Repository
from .extraction import ExtractionLimits, FixtureProvider, PROMPT_VERSION, extract_claims


def _identity(claim: dict) -> tuple:
    return claim["kind"], claim["value"], claim.get("name"), tuple(sorted(claim["sources"]))


def evaluate_extraction(dataset_path: str | Path, *, provider_factory=None,
                         limits: ExtractionLimits | None = None) -> dict:
    dataset_path = Path(dataset_path)
    data = json.loads(dataset_path.read_text())
    if data.get("version") != 1 or data.get("split") != "held-out" or not isinstance(data.get("cases"), list) or not data["cases"]:
        raise ValueError("Expected a version 1 nonempty held-out dataset")
    tp = fp = fn = false_stale = stale_flags = invalid = 0
    reports = []
    for case in data["cases"]:
        with tempfile.TemporaryDirectory(prefix="memorylint-eval-") as temporary:
            repository = Repository(temporary)
            repository.path("MEMORY.md").write_text(case["markdown"])
            for ref, text in case["sources"].items():
                target = repository.path(ref)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
            provider = provider_factory(case) if provider_factory else FixtureProvider(case["replay"])
            try:
                report = extract_claims(temporary, "MEMORY.md", list(case["sources"]), provider, limits=limits)
                actual = {_identity(item["finding"]["claim"]): item["finding"]["status"] for item in report["candidates"]}
                expected = {_identity(item): item["status"] for item in case["expected"]}
                tp += len(actual.keys() & expected.keys())
                fp += len(actual.keys() - expected.keys())
                fn += len(expected.keys() - actual.keys())
                wrong_stale = sum(status == "stale_candidate" and expected.get(key) != "stale_candidate"
                                  for key, status in actual.items())
                flags = sum(status == "stale_candidate" for status in actual.values())
                false_stale += wrong_stale
                stale_flags += flags
                reports.append({"id": case["id"], "candidates": len(actual), "expected": len(expected),
                                "false_stale_flags": wrong_stale, "usage": report["usage"]})
            except (ValueError, OSError) as exc:
                invalid += 1
                fn += len(case["expected"])
                reports.append({"id": case["id"], "error": str(exc)})
    return {"schema_version": 1, "dataset": data.get("name"), "split": "held-out",
            "mode": "external-provider" if provider_factory else "fixture-replay",
            "prompt_version": PROMPT_VERSION, "runs": len(reports), "invalid_runs": invalid,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "false_stale_rate": false_stale / stale_flags if stale_flags else None,
            "counts": {"true_positive": tp, "false_positive": fp, "false_negative": fn,
                       "false_stale_flags": false_stale, "stale_flags": stale_flags}, "cases": reports,
            "limitation": "Fixture replay validates contracts and scoring, not live-model extraction accuracy." if not provider_factory else "Results apply only to this labeled dataset and configured provider."}
