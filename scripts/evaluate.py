"""Run the golden benchmark and fail the process if the quality gate blocks deployment."""

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.config import ROOT, Settings
from backend.app.evaluation import EVALUATOR_VERSION
from backend.app.regression import summarize
from backend.app.service import Platform


async def main(args):
    config = Settings(database_url="sqlite:///:memory:", seed_on_start=False)
    platform = Platform(config)
    if args.write_baseline:
        traces = await platform.benchmark()
        baseline = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mode": "demo" if config.demo_mode else "ollama",
            "dataset_sha256": hashlib.sha256(
                (ROOT / "data/evaluation/golden_dataset.json").read_bytes()
            ).hexdigest(),
            "metrics": summarize(traces),
            "evaluator_version": EVALUATOR_VERSION,
            "cases": len(traces),
            "note": "Measured benchmark. Timing includes graph setup, but demo waits are scaled to 0.02x.",
        }
        (ROOT / "data/evaluation/baseline.json").write_text(json.dumps(baseline, indent=2))
        print("Explicitly wrote baseline:", baseline["metrics"])
        return 0
    result = await platform.regression(degraded=args.degraded)
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "evaluation.json").write_text(json.dumps(result, indent=2))
    lines = [
        "# AgentWatch evaluation",
        "",
        f"**{result['status']}** — {result['passed']}/{result['total']} cases passed",
        "",
        "| Metric | Baseline | Current | Difference |",
        "|---|---:|---:|---:|",
    ]
    for c in result["comparisons"]:
        lines.append(
            f"| {c['metric']} | {c['baseline']:.4f} | {c['current']:.4f} | {c['difference']:+.4f} |"
        )
    lines += ["", *[f"- {r}" for r in result["reasons"]]]
    (reports / "evaluation.md").write_text("\n".join(lines))
    print("\n".join(lines))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Explicitly replace reviewed baseline; never run in CI",
    )
    parser.add_argument(
        "--degraded", action="store_true", help="Inject empty retrieval to prove gate failure"
    )
    sys.exit(asyncio.run(main(parser.parse_args())))
