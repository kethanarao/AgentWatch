import os

import pytest
from deepeval.test_case import LLMTestCase

from evals.metrics.deterministic import CitationMetric


def test_offline_citation_metric_distinguishes_hallucinated_sources():
    metric = CitationMetric()
    good = LLMTestCase(
        input="Why is my pod restarting?",
        actual_output="Inspect previous logs [KB-001]",
        additional_metadata={"document_ids": ["KB-001"]},
    )
    bad = LLMTestCase(
        input=good.input,
        actual_output="Delete the cluster [KB-FAKE]",
        additional_metadata=good.additional_metadata,
    )
    assert metric.measure(good) == 1
    assert metric.is_successful()
    assert metric.measure(bad) == 0
    assert not metric.is_successful()


@pytest.mark.skipif(
    os.getenv("RUN_LOCAL_JUDGE") != "true", reason="Optional local Ollama semantic evaluation"
)
def test_builtin_rag_metrics_with_ollama():
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        FaithfulnessMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        ContextualRelevancyMetric,
    )
    from evals.metrics.ollama import OllamaJudge

    model = OllamaJudge()
    case = LLMTestCase(
        input="What does a readiness probe failure do?",
        actual_output="It removes the pod from service endpoints without restarting it.",
        expected_output="The pod is removed from service endpoints. It is not restarted.",
        retrieval_context=[
            "Readiness failure removes the pod from service endpoints without restarting it."
        ],
    )
    for cls in [
        AnswerRelevancyMetric,
        FaithfulnessMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        ContextualRelevancyMetric,
    ]:
        metric = cls(model=model, threshold=0.7, async_mode=False)
        metric.measure(case)
        assert metric.is_successful(), metric.reason
