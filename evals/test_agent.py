import asyncio

from deepeval.test_case import LLMTestCase

from backend.app.config import Settings
from backend.app.service import Platform
from evals.metrics.deterministic import CitationMetric


def test_deepeval_on_real_graph_output():
    p = Platform(
        Settings(database_url="sqlite:///:memory:", seed_on_start=False, demo_latency_scale=0)
    )
    trace = asyncio.run(p.run("Why is my Kubernetes pod in CrashLoopBackOff?"))
    case = LLMTestCase(
        input=trace["query"],
        actual_output=trace["answer"],
        additional_metadata={"document_ids": [d["id"] for d in trace["retrieved_documents"]]},
    )
    assert CitationMetric().measure(case) == 1
    assert trace["evaluation"]["trajectory_efficiency"] == 1
