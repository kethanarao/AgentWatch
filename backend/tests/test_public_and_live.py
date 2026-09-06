import asyncio

import pytest

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.public_limits import PublicActionGuard
from backend.app.service import Platform


@pytest.mark.parametrize(
    "name,arguments", [("shell", {}), ("metrics_tool", {"service": "other-service"})]
)
def test_model_cannot_expand_tool_capabilities(monkeypatch, name, arguments):
    from backend.app.llm import plan_tools

    async def model(*args, **kwargs):
        return {"tool_calls": [{"function": {"name": name, "arguments": arguments}}]}

    monkeypatch.setattr("backend.app.llm.chat", model)
    with pytest.raises(ValueError):
        asyncio.run(plan_tools(Settings(), "CPU metrics", "checkout-api"))


def test_model_extra_arguments_never_reach_execution(monkeypatch):
    from backend.app.llm import plan_tools

    async def model(*args, **kwargs):
        return {
            "tool_calls": [
                {
                    "function": {
                        "name": "metrics_tool",
                        "arguments": {"service": "checkout-api", "command": "ignored"},
                    }
                }
            ]
        }

    monkeypatch.setattr("backend.app.llm.chat", model)
    selected, plan = asyncio.run(plan_tools(Settings(), "CPU metrics", "checkout-api"))
    assert selected == ["metrics_tool"]
    assert plan["tool_calls"][0]["function"]["arguments"] == {"service": "checkout-api"}


def test_shared_budget_cannot_be_bypassed_with_forwarded_headers():
    config = Settings(
        database_url="sqlite:///:memory:",
        seed_on_start=False,
        demo_latency_scale=0,
        public_requests_per_minute=1,
    )
    with TestClient(create_app(config)) as client:
        assert client.post("/api/chat", json={"query": "Why is my pod Pending?"}).status_code == 200
        blocked = client.post(
            "/api/chat",
            json={"query": "Why is my pod Pending?"},
            headers={"X-Forwarded-For": "192.0.2.99"},
        )
        assert blocked.status_code == 429
        assert int(blocked.headers["Retry-After"]) > 0
        assert client.get("/health").status_code == 200
        assert client.get("/api/traces").status_code == 200


def test_oversized_body_rejected_before_parsing():
    with TestClient(
        create_app(Settings(database_url="sqlite:///:memory:", seed_on_start=False))
    ) as client:
        assert client.post("/api/chat", content=b"x" * 17000).status_code == 413


def test_heavy_admission_and_release_after_cancellation():
    async def exercise():
        entered, release = asyncio.Event(), asyncio.Event()

        async def application(scope, receive, send):
            entered.set()
            await release.wait()

        guard = PublicActionGuard(application, Settings())

        async def receive():
            return {"type": "http.request", "body": b"{}"}

        messages = []

        async def send(message):
            messages.append(message)

        scope = {"type": "http", "method": "POST", "path": "/api/experiments/run"}
        task = asyncio.create_task(guard(scope, receive, send))
        await entered.wait()
        await guard(scope, receive, send)
        assert messages[0]["status"] == 429
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert guard.active == guard.heavy_active == 0

    asyncio.run(exercise())


def test_no_fake_judge_or_unlabeled_perfect_tool_score(platform):
    trace = asyncio.run(platform.run("What is the capital of France?"))
    e = trace["evaluation"]
    assert e["tool_selection"] is None and e["faithfulness"] is None
    assert e["answer_relevance"] < 1
    assert e["judge"]["result"] is None
    assert e["judge"]["status"] == "disabled_demo"
    assert "no language model" in trace["answer"]
    assert trace["query_category"] == "general"  # "capital" must not match "api".


def test_demo_answer_uses_successful_tool_results(platform):
    trace = asyncio.run(platform.run("Show checkout-api metrics for high latency"))
    metrics = trace["tool_calls"][0]["result"]
    assert str(metrics["p95_latency_ms"]) in trace["answer"]
    assert "Simulated metrics" in trace["answer"]


def test_failed_generation_preserves_verified_diagnostic_values(platform):
    trace = asyncio.run(
        platform.run("Show checkout-api CPU metrics", scenario="generation_failure")
    )
    assert trace["fallback"]
    assert "Verified tool output (simulated)" in trace["answer"]
    assert str(trace["tool_calls"][0]["result"]["p95_latency_ms"]) in trace["answer"]


def test_live_model_selects_tools_and_receives_results(monkeypatch):
    payloads = []

    async def model(config, messages, tools=None):
        payloads.append((messages, tools))
        if tools is not None:
            return {"tool_calls": [{"function": {"name": "metrics_tool", "arguments": {}}}]}
        assert any(m["role"] == "tool" and "p95_latency_ms" in m["content"] for m in messages)
        return {
            "content": "The simulated metrics show service latency. Inspect the runbook [KB-001]."
        }

    monkeypatch.setattr("backend.app.llm.chat", model)
    p = Platform(
        Settings(
            demo_mode=False,
            database_url="sqlite:///:memory:",
            seed_on_start=False,
            online_eval_sample_rate=0,
            demo_latency_scale=0,
        )
    )
    trace = asyncio.run(p.run("Kubernetes CrashLoopBackOff pod latency"))
    assert trace["execution_metadata"]["tool_selection_source"] == "llm"
    assert trace["selected_tools"] == ["metrics_tool"]
    assert len(payloads) >= 2
    p.store.engine.dispose()


def test_general_question_reaches_live_model_without_runbooks(monkeypatch):
    async def model(config, messages, tools=None):
        assert tools is None
        return {"content": "Paris is the capital of France."}

    monkeypatch.setattr("backend.app.llm.chat", model)
    p = Platform(
        Settings(
            demo_mode=False,
            database_url="sqlite:///:memory:",
            seed_on_start=False,
            online_eval_sample_rate=0,
            demo_latency_scale=0,
        )
    )
    trace = asyncio.run(p.run("What is the capital of France?"))
    assert trace["answer"] == "Paris is the capital of France."
    assert not trace["retrieved_documents"] and not trace["tool_calls"]
    assert not trace["fallback"]
    p.store.engine.dispose()


def test_cpu_mode_makes_one_model_call_and_preserves_tool_output(monkeypatch):
    calls = []

    async def model(config, messages, tools=None):
        calls.append(tools)
        return {"content": "An uncited answer"}

    monkeypatch.setattr("backend.app.llm.chat", model)
    p = Platform(
        Settings(
            demo_mode=False,
            llm_tool_selection=False,
            database_url="sqlite:///:memory:",
            seed_on_start=False,
            online_eval_sample_rate=0,
            demo_latency_scale=0,
        )
    )
    t = asyncio.run(p.run("Show checkout-api CPU and latency metrics"))
    assert calls == [None]
    assert t["execution_metadata"]["tool_selection_source"] == "rules"
    assert t["retry_count"] == 0 and t["fallback"]
    assert "Verified tool output" in t["answer"]
    p.store.engine.dispose()


def test_structured_answer_rejects_fabricated_sources(monkeypatch):
    from backend.app.llm import answer

    async def model(*args, **kwargs):
        assert kwargs["response_format"]["properties"]["sources"]["items"]["enum"] == ["KB-003"]
        return {"content": '{"answer":"Check the probe port", "sources":["KB-FAKE"]}'}

    monkeypatch.setattr("backend.app.llm.chat", model)
    with pytest.raises(ValueError):
        asyncio.run(
            answer(
                Settings(structured_answers=True),
                "Readiness issue",
                [{"id": "KB-003", "text": "Check the port"}],
                [],
            )
        )


def test_structured_answer_renders_model_selected_sources(monkeypatch):
    from backend.app.llm import answer

    async def model(*args, **kwargs):
        return {"content": '{"answer":"Check the probe port", "sources":["KB-003"]}'}

    monkeypatch.setattr("backend.app.llm.chat", model)
    result = asyncio.run(
        answer(
            Settings(structured_answers=True),
            "Readiness issue",
            [{"id": "KB-003", "text": "Check the port"}],
            [],
        )
    )
    assert result.endswith("[KB-003]")


def test_general_answer_is_not_failed_for_low_word_overlap(monkeypatch):
    async def model(*args, **kwargs):
        return {"content": "Two penguins walk into a library."}

    monkeypatch.setattr("backend.app.llm.chat", model)
    p = Platform(
        Settings(
            demo_mode=False,
            database_url="sqlite:///:memory:",
            seed_on_start=False,
            online_eval_sample_rate=0,
            demo_latency_scale=0,
        )
    )
    t = asyncio.run(p.run("Tell me a joke"))
    assert t["evaluation"]["answer_relevance"] == 0
    assert t["status"] == "OK"
    p.store.engine.dispose()
