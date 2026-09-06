import hashlib

from fastapi.testclient import TestClient

from backend.app.config import ROOT, Settings
from backend.app.main import create_app


def test_api_feedback_review_and_export():
    config = Settings(database_url="sqlite:///:memory:", seed_on_start=False, demo_latency_scale=0)
    before = hashlib.sha256((ROOT / "data/evaluation/golden_dataset.json").read_bytes()).hexdigest()
    with TestClient(create_app(config)) as client:
        assert client.get("/health").status_code == 200
        assert client.post("/api/chat", json={"query": "x"}).status_code == 422
        response = client.post("/api/chat", json={"query": "Why is my pod Pending?"})
        assert response.status_code == 200
        trace = response.json()
        assert client.get(f"/api/traces/{trace['trace_id']}").status_code == 200
        assert client.get("/api/traces/unknown").status_code == 404
        assert (
            client.post(
                "/api/feedback",
                json={
                    "trace_id": trace["trace_id"],
                    "rating": "down",
                    "reason": "Missing information",
                },
            ).status_code
            == 200
        )
        candidates = client.get("/api/candidates").json()
        assert candidates[0]["status"] == "pending"
        assert client.get("/api/candidates/export").json() == []
        assert (
            client.post(
                f"/api/candidates/{trace['trace_id']}/review", json={"status": "approved"}
            ).status_code
            == 200
        )
        assert len(client.get("/api/candidates/export").json()) == 1
        assert client.get("/api/metrics/overview").json()["total_requests"] == 1
        assert "agent_requests_total" in client.get("/metrics").text
    assert (
        hashlib.sha256((ROOT / "data/evaluation/golden_dataset.json").read_bytes()).hexdigest()
        == before
    )


def test_api_key_protects_reads_and_writes():
    with TestClient(
        create_app(
            Settings(database_url="sqlite:///:memory:", seed_on_start=False, api_key="test-secret")
        )
    ) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/traces").status_code == 401
        assert client.get("/api/traces", headers={"X-API-Key": "test-secret"}).status_code == 200
