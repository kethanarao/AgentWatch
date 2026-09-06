import json

from .config import ROOT, Settings
from .monitoring import percentile


def golden_cases():
    return json.loads((ROOT / "data/evaluation/golden_dataset.json").read_text())


def summarize(traces):
    result = {}
    for name in [
        "faithfulness",
        "context_precision",
        "context_recall",
        "answer_relevance",
        "citation_accuracy",
        "trajectory_efficiency",
        "tool_selection",
        "safety",
    ]:
        values = [t["evaluation"][name] for t in traces if t["evaluation"][name] is not None]
        result[name] = sum(values) / len(values) if values else None
    result["p95_latency_ms"] = percentile([t["duration_ms"] for t in traces], 95)
    result["tool_calls"] = sum(len(t["tool_calls"]) for t in traces) / max(1, len(traces))
    return result


def quality_gate(current: dict, baseline: dict, config: Settings):
    reasons, comparisons = [], []
    thresholds = {
        "faithfulness": config.min_faithfulness,
        "context_recall": config.min_context_recall,
        "citation_accuracy": config.min_citation_accuracy,
    }
    for name, minimum in thresholds.items():
        if current.get(name) is None or current[name] < minimum:
            reasons.append(f"{name} {current.get(name)} is below minimum {minimum}")
    if current.get("p95_latency_ms", float("inf")) > config.max_p95_latency_ms:
        reasons.append(f"P95 latency exceeds {config.max_p95_latency_ms} ms")
    for name, value in current.items():
        old = baseline.get(name)
        if value is None or old is None:
            continue
        delta = value - old
        # Timing noise on sub-millisecond CI runs is not a meaningful regression.
        denominator = max(abs(old), 50 if name == "p95_latency_ms" else 0.01)
        regression = (
            delta / denominator * 100
            if name in ["p95_latency_ms", "tool_calls"]
            else -delta / denominator * 100
        )
        comparisons.append(
            {
                "metric": name,
                "baseline": old,
                "current": value,
                "difference": delta,
                "regression_percent": regression,
            }
        )
        # Scheduling noise is material on tiny demo benchmarks. Apply both a relative
        # limit and an explicit 100ms absolute deadband to latency regressions.
        exceeds_noise_floor = name != "p95_latency_ms" or delta > config.min_latency_regression_ms
        if regression > config.max_regression_percent and exceeds_noise_floor:
            reasons.append(
                f"{name} regressed {regression:.1f}% (limit {config.max_regression_percent}%)"
            )
    return {
        "status": "DEPLOYMENT BLOCKED" if reasons else "PASS",
        "reasons": reasons,
        "comparisons": comparisons,
    }
