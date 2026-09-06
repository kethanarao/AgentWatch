import asyncio

from backend.app.config import Settings
from backend.app.evaluation import judge


def test_online_judge_retries_invalid_json_then_succeeds(monkeypatch):
    attempts = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            content = (
                "invalid"
                if len(attempts) == 1
                else '{"correctness":0.8,"completeness":0.9,"helpfulness":0.9,"groundedness":0.8,"reasoning":"supported"}'
            )
            return {"message": {"content": content}}

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            attempts.append(kwargs)
            return Response()

    monkeypatch.setattr("backend.app.evaluation.httpx.AsyncClient", Client)
    trace = {"trace_id": "test", "query": "query", "retrieved_documents": [], "answer": "answer"}
    result = asyncio.run(judge(trace, Settings(demo_mode=False, online_eval_sample_rate=1)))
    assert result["status"] == "completed" and result["attempts"] == 2
    assert result["result"]["correctness"] == 0.8
    assert attempts[0]["json"]["format"]["type"] == "object"


def test_latency_deadband_does_not_hide_material_regression():
    from backend.app.regression import quality_gate

    baseline = {
        "faithfulness": 1,
        "context_recall": 1,
        "citation_accuracy": 1,
        "p95_latency_ms": 100,
    }
    assert (
        quality_gate({**baseline, "p95_latency_ms": 150}, baseline, Settings())["status"] == "PASS"
    )
    assert (
        quality_gate({**baseline, "p95_latency_ms": 250}, baseline, Settings())["status"]
        == "DEPLOYMENT BLOCKED"
    )
