import asyncio
from copy import deepcopy

import pytest

from backend.app.config import Settings
from backend.app.drift import detect_drift
from backend.app.evaluation import citation_validity, retrieval_metrics, trajectory_metrics
from backend.app.regression import quality_gate
from backend.app.tools import incident_tool, metrics_tool


def test_retrieval_ranks_known_runbook(platform):
    docs = platform.retriever.search("Kubernetes CrashLoopBackOff pod exit code", 3)
    assert docs[0]["id"] == "KB-001"
    assert docs[0]["score"] > docs[-1]["score"]
    assert len({d["chunk_id"] for d in docs}) == 3


def test_retrieval_metrics_rank_and_no_ground_truth():
    docs = [{"id": "B"}, {"id": "A"}, {"id": "C"}]
    r = retrieval_metrics(docs, ["A", "D"])
    assert r == {"context_precision": 1 / 3, "context_recall": 0.5, "hit_rate": 1.0, "mrr": 0.5}
    assert retrieval_metrics(docs, None)["context_recall"] is None


def test_citations_reject_fabrications_and_missing_ids():
    docs = [{"id": "KB-001"}]
    assert citation_validity("Evidence [KB-001]", docs)["valid"]
    assert not citation_validity("Evidence [KB-FAKE]", docs)["valid"]
    assert not citation_validity("Evidence without a source", docs)["valid"]
    assert citation_validity("Please clarify", [])["valid"]


def test_tool_determinism_and_service_scoping():
    assert metrics_tool("checkout-api") == metrics_tool("checkout-api")
    assert metrics_tool("checkout-api") != metrics_tool("payments")
    assert all(
        i["service"] == "payments" for i in incident_tool("payments", "latency")["incidents"]
    )


def test_trajectory_penalizes_duplicate_calls_and_retrievals():
    expected = ["retrieve_context", "metrics_tool", "generate_answer"]
    good = trajectory_metrics(expected, expected, 0)
    bad = trajectory_metrics(
        [*expected[:2], "metrics_tool", "retrieve_context", "generate_answer"], expected, 1
    )
    assert good["trajectory_efficiency"] == 1
    assert bad["trajectory_efficiency"] < 1
    assert bad["redundant_tool_calls"] == bad["unnecessary_retrievals"] == 1


def test_drift_detects_distribution_shift_and_requires_samples(platform):
    t = asyncio.run(platform.run("Why is my API returning 503 errors?"))
    baseline = [deepcopy(t) for _ in range(20)]
    recent = deepcopy(baseline)
    assert detect_drift(baseline, recent)["status"] == "NORMAL"
    for row in recent:
        row["duration_ms"] += 10000
    assert detect_drift(baseline, recent)["status"] == "CRITICAL"
    assert detect_drift([], recent)["status"] == "INSUFFICIENT_DATA"


@pytest.mark.parametrize(
    "metric,value",
    [
        ("faithfulness", 0.5),
        ("context_recall", 0.5),
        ("citation_accuracy", 0.5),
        ("p95_latency_ms", 6000),
    ],
)
def test_absolute_gates_block(metric, value):
    baseline = {
        "faithfulness": 0.95,
        "context_recall": 0.95,
        "citation_accuracy": 1,
        "p95_latency_ms": 100,
    }
    current = {**baseline, metric: value}
    assert quality_gate(current, baseline, Settings())["status"] == "DEPLOYMENT BLOCKED"


def test_relative_gate_blocks_even_above_absolute_minimum():
    baseline = {
        "faithfulness": 1,
        "context_recall": 1,
        "citation_accuracy": 1,
        "p95_latency_ms": 100,
    }
    assert (
        quality_gate({**baseline, "context_recall": 0.85}, baseline, Settings())["status"]
        == "DEPLOYMENT BLOCKED"
    )
    assert quality_gate(baseline, baseline, Settings())["status"] == "PASS"
