from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from backend.app.evaluation import citation_validity


class CitationMetric(BaseMetric):
    """DeepEval-compatible deterministic citation check with no model or credentials."""

    def __init__(self, threshold=0.95):
        self.threshold = threshold
        self.async_mode = False
        self.strict_mode = False
        self.evaluation_cost = 0
        self.error = None

    def measure(self, test_case: LLMTestCase, *args, **kwargs):
        documents = [
            {"id": id} for id in (test_case.additional_metadata or {}).get("document_ids", [])
        ]
        result = citation_validity(test_case.actual_output or "", documents)
        self.score = result["score"] if result["valid"] else 0
        self.success = self.score >= self.threshold
        self.reason = f"Citation validation: {result}"
        return self.score

    async def a_measure(self, test_case, *args, **kwargs):
        return self.measure(test_case)

    def is_successful(self):
        return self.success

    @property
    def __name__(self):
        return "Deterministic citation validity"
