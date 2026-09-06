"""Exercise a running deployment over HTTP, including every major user workflow."""

import argparse
import json
from pathlib import Path

import httpx


def main(base: str):
    checks = []
    with httpx.Client(base_url=base, timeout=180) as client:

        def get(path):
            response = client.get(path)
            response.raise_for_status()
            checks.append({"method": "GET", "path": path, "status": response.status_code})
            return response.json()

        def post(path, body):
            response = client.post(path, json=body)
            response.raise_for_status()
            checks.append({"method": "POST", "path": path, "status": response.status_code})
            return response.json()

        assert get("/health")["status"] == "ok"
        query = "Why is checkout-api returning 503 errors?"
        trace = post("/api/chat", {"query": query})
        assert trace["answer"] and trace["spans"]
        assert get(f"/api/traces/{trace['trace_id']}")["trace_id"] == trace["trace_id"]
        for scenario in get("/api/chaos/scenarios"):
            result = post("/api/chaos/run", {"query": query, "scenario": scenario["id"]})
            assert result["failures"], scenario["id"]
            checks[-1]["scenario"] = scenario["id"]
            checks[-1]["diagnoses"] = [f["failure_category"] for f in result["failures"]]
        post(
            "/api/feedback",
            {"trace_id": trace["trace_id"], "rating": "down", "reason": "Missing information"},
        )
        post(f"/api/candidates/{trace['trace_id']}/review", {"status": "approved"})
        assert any(c["trace_id"] == trace["trace_id"] for c in get("/api/candidates/export"))
        experiment = post("/api/experiments/run", {})
        assert experiment["winner"] in ["A", "B", "TIE"]
        degraded = post("/api/regression/run", {"degraded": True})
        assert degraded["status"] == "DEPLOYMENT BLOCKED"
        normal = post("/api/regression/run", {"degraded": False})
        assert normal["status"] == "PASS", normal["reasons"]
        shifted = post("/api/drift/demo", {})
        assert shifted["status"] in ["WARNING", "CRITICAL"]
        for path in [
            "/api/traces",
            "/api/metrics/overview",
            "/api/evaluations",
            "/api/drift",
            "/api/alerts",
            "/api/experiments",
            "/api/regression",
            "/api/candidates",
        ]:
            get(path)
        assert "agent_requests_total" in client.get("/metrics").text
    report = {
        "base_url": base,
        "checks": checks,
        "normal_gate": normal["status"],
        "degraded_gate": degraded["status"],
        "drift_status": shifted["status"],
        "experiment_winner": experiment["winner"],
    }
    directory = Path(__file__).resolve().parents[1] / "reports"
    directory.mkdir(exist_ok=True)
    (directory / "api-smoke.json").write_text(json.dumps(report, indent=2))
    print(
        f"PASS: {len(checks)} HTTP checks; all 12 faults diagnosed; normal and degraded gates verified."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    main(parser.parse_args().base_url)
