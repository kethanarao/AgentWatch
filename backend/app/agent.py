import asyncio
import json
import re
from typing import Any, TypedDict

import httpx
from langgraph.graph import END, START, StateGraph

from .config import Settings
from .evaluation import citation_validity
from .llm import answer as live_answer, plan_tools
from .rag import Retriever
from .tools import ServiceMetrics, incident_tool, metrics_tool, select_tools
from .tracing import Recorder


class AgentState(TypedDict, total=False):
    query: str
    query_category: str
    retrieved_documents: list[dict]
    retrieval_scores: list[float]
    selected_tools: list[str]
    tool_calls: list[dict]
    tool_results: list[dict]
    generated_answer: str
    citations: list[str]
    validation_results: dict
    validation_errors: list[str]
    retry_count: int
    execution_metadata: dict[str, Any]
    trace_id: str
    trajectory: list[str]
    safe_response: bool
    security_event: bool
    fallback: bool
    tool_plan: dict


INJECTION = re.compile(
    r"ignore.{0,40}instructions|system prompt|disregard.{0,40}instructions|leak credentials|reveal secrets",
    re.I | re.S,
)
DOMAIN = re.compile(
    r"\b(?:pods?|kubernetes|containers?|docker|deploy\w*|apis?|latency|p95|p99|cpu|memory|dns|network\w*|http|503|502|504|429|pool|cache|probe|secret|configmap|tls|hpa|volume|retry|sigterm|disk|thread|worker|clock|token|incidents?|services?|files|rollout|image|registry)\b",
    re.I,
)


class SupportAgent:
    def __init__(self, config: Settings, retriever: Retriever):
        self.config, self.retriever = config, retriever

    async def run(
        self,
        query: str,
        service: str,
        top_k: int,
        scenario: str | None,
        recorder: Recorder,
        latency_scale: float | None = None,
    ):
        scale = self.config.demo_latency_scale if latency_scale is None else latency_scale

        async def pause(seconds):
            await asyncio.sleep(seconds * scale)

        def visit(state, node):
            state["trajectory"].append(node)

        async def analyze_query(state):
            visit(state, "analyze_query")
            with recorder.span("QueryAnalysis", query) as span:
                security = bool(INJECTION.search(query)) or scenario == "prompt_injection"
                category = (
                    "safety" if security else ("devops" if DOMAIN.search(query) else "general")
                )
                safe = security or (category == "general" and self.config.demo_mode)
                span["output_summary"] = {"category": category, "security_event": security}
                return {
                    "query_category": category,
                    "security_event": security,
                    "safe_response": bool(safe),
                }

        async def retrieve_context(state):
            visit(state, "retrieve_context")
            with recorder.span("Retrieval", {"query": query, "top_k": top_k}) as span:
                with recorder.span("Embedding", {"characters": len(query)}) as embed:
                    vector = self.retriever.embed(query)
                    embed["output_summary"] = {
                        "dimensions": len(vector),
                        "source": "sentence-transformers"
                        if self.config.semantic_retrieval
                        else "tfidf",
                    }
                with recorder.span("VectorSearch", {"top_k": top_k}) as search:
                    docs = self.retriever.search(query, top_k, vector)
                    if scenario == "empty_retrieval":
                        docs = []
                    elif scenario == "bad_retrieval":
                        docs = [{**self.retriever.documents[-1], "score": 0.015}]
                    elif scenario == "outdated_document":
                        docs = [
                            {
                                **d,
                                "stale": True,
                                "updated_at": "2020-01-01",
                                "text": d["text"]
                                + " Legacy revision: verify against current cluster version.",
                            }
                            for d in docs
                        ]
                    elif scenario == "long_context":
                        docs = [{**d, "text": d["text"] * 80} for d in docs]
                    await pause(0.045)
                    search["output_summary"] = [{"id": d["id"], "score": d["score"]} for d in docs]
                span["output_summary"] = {"chunks": len(docs)}
                return {"retrieved_documents": docs, "retrieval_scores": [d["score"] for d in docs]}

        async def choose_tools(state):
            visit(state, "select_tools")
            with recorder.span("ToolSelection", query) as span:
                chosen = select_tools(query, max(state["retrieval_scores"], default=0))
                plan = {}
                metadata = dict(state["execution_metadata"])
                metadata["tool_selection_source"] = "rules"
                if not self.config.demo_mode and self.config.llm_tool_selection:
                    try:
                        chosen, plan = await plan_tools(self.config, query, service)
                        metadata["tool_selection_source"] = "llm"
                    except (httpx.HTTPError, KeyError, ValueError, TypeError):
                        metadata["tool_selection_source"] = "rules_fallback"
                        span.update(
                            status="ERROR",
                            error="Model tool selection unavailable or invalid; used bounded rules fallback",
                        )
                if (
                    scenario
                    in ["tool_timeout", "tool_500", "malformed_tool_json", "duplicate_tool_call"]
                    and "metrics_tool" not in chosen
                ):
                    chosen.append("metrics_tool")
                span["output_summary"] = chosen
                return {"selected_tools": chosen, "tool_plan": plan, "execution_metadata": metadata}

        async def execute_tools(state):
            visit(state, "execute_tools")
            calls, results = [], []
            chosen = list(state["selected_tools"])
            if scenario == "duplicate_tool_call":
                chosen.append(chosen[0])
            with recorder.span("ToolExecution", chosen):
                for name in chosen:
                    visit(state, name)
                    with recorder.span(
                        "MetricsTool" if name == "metrics_tool" else "IncidentTool",
                        {"service": service},
                    ) as span:
                        error, result = None, None
                        try:
                            if scenario == "tool_timeout":
                                # A real deadline expires, rather than merely labeling a successful call.
                                await asyncio.wait_for(pause(3.0), timeout=max(0.001, 2.5 * scale))
                                raise TimeoutError("Tool deadline exceeded")
                            await pause(0.09)
                            if scenario == "tool_500":
                                raise RuntimeError("HTTP 500 from simulated tool service")
                            if scenario == "malformed_tool_json":
                                ServiceMetrics.model_validate_json('{"cpu":"not-a-number"}')
                            result = (
                                metrics_tool(service)
                                if name == "metrics_tool"
                                else incident_tool(service, query)
                            )
                        except (TimeoutError, RuntimeError, ValueError) as exc:
                            error = str(exc)[:500] or "Tool deadline exceeded"
                            span.update(status="ERROR", error=error)
                        span["output_summary"] = result
                    calls.append(
                        {
                            "id": span["span_id"],
                            "name": name,
                            "arguments": {"service": service},
                            "result": result,
                            "status": span["status"],
                            "error": error,
                            "duration_ms": span["duration_ms"],
                        }
                    )
                    results.append({"name": name, "result": result, "error": error})
            return {"tool_calls": calls, "tool_results": results}

        async def generate_answer(state):
            visit(state, "generate_answer")
            with recorder.span("Generation", {"attempt": state["retry_count"] + 1}) as span:
                if state["safe_response"]:
                    answer = (
                        "I cannot reveal internal prompts or credentials. I can help debug a service using sanitized symptoms."
                        if state["security_event"]
                        else 'This question is outside the runbook demo, with no language model enabled. I cannot produce a reliable general answer in this mode. Enable live inference for custom answers, or ask a service troubleshooting question such as "Why is my pod Pending?".'
                    )
                else:
                    docs = state["retrieved_documents"]
                    if sum(len(d["text"]) for d in docs) > 16000:
                        state["validation_errors"].append("context_overflow")
                        remaining = 16000
                        trimmed = []
                        for doc in docs:
                            if remaining <= 0:
                                break
                            trimmed.append({**doc, "text": doc["text"][:remaining]})
                            remaining -= len(trimmed[-1]["text"])
                        docs = trimmed
                        state["retrieved_documents"] = docs
                    await pause(2.2 if scenario == "slow_llm" else 0.16)
                    if scenario == "generation_failure":
                        span.update(status="ERROR", error="Injected generation failure")
                        state["validation_errors"].append("generation_failure")
                        answer = ""
                    elif self.config.demo_mode:
                        answer = (
                            "\n\n".join(
                                f"{d['text'].split('Updated:')[-1][11:].strip()} [{d['id']}]"
                                for d in docs[:2]
                            )
                            if docs
                            else "I could not find reliable context. Share the service logs and recent changes; verify the incident evidence before taking action."
                        )
                        observations = []
                        for call in state["tool_calls"]:
                            result = call["result"]
                            if call["status"] != "OK" or not result:
                                continue
                            if call["name"] == "metrics_tool":
                                observations.append(
                                    f"Simulated metrics for {result['service']}: CPU {result['cpu']}%, memory {result['memory']}%, P95 {result['p95_latency_ms']} ms, error rate {result['error_rate']:.1%}. These are fixture values, not live measurements."
                                )
                            else:
                                incidents = result.get("incidents", [])
                                observations.append(
                                    f"Simulated incident history for {result['service']}: "
                                    + (
                                        json.dumps(incidents)
                                        if incidents
                                        else "no matching incidents."
                                    )
                                )
                        answer = "\n\n".join([*observations, answer])
                        if any(c["status"] != "OK" for c in state["tool_calls"]):
                            answer += "\n\nThe diagnostic tool is unavailable; the guidance above is based on runbooks only."
                    else:
                        try:
                            answer = await live_answer(
                                self.config,
                                query,
                                docs,
                                state["tool_results"],
                                state.get("tool_plan"),
                                retry=state["retry_count"] > 0,
                            )
                        except (httpx.HTTPError, KeyError, ValueError) as exc:
                            answer = ""
                            state["validation_errors"].append("generation_failure")
                            span.update(status="ERROR", error=str(exc)[:300])
                    if scenario == "hallucinated_citation":
                        answer += "\n\nRestart the entire cluster immediately. [KB-FAKE]"
                span["token_estimate"] = max(1, len(answer) // 4)
                span["output_summary"] = answer[:500]
                return {
                    "generated_answer": answer,
                    "retrieved_documents": state["retrieved_documents"],
                }

        async def validate_answer(state):
            visit(state, "validate_answer")
            with recorder.span("Validation", state["generated_answer"][:300]) as span:
                citation = citation_validity(
                    state["generated_answer"], state["retrieved_documents"]
                )
                valid = (
                    bool(state["generated_answer"].strip())
                    and citation["valid"]
                    and len(state["generated_answer"]) <= 12000
                )
                if not citation["valid"]:
                    state["validation_errors"].append("citation_failure")
                span["output_summary"] = {"valid": valid, **citation}
                if not valid:
                    span["status"] = "ERROR"
                    span["error"] = "Answer validation failed"
                return {"validation_results": {"valid": valid}, "citations": citation["citations"]}

        async def retry(state):
            state["retry_count"] += 1
            return state

        async def finalize_response(state):
            visit(state, "finalize_response")
            with recorder.span("FinalizeResponse") as span:
                fallback = not state["validation_results"]["valid"]
                if fallback:
                    state["generated_answer"] = (
                        "I could not produce a validated answer. Please share sanitized service logs and verify the runbooks below before taking action. "
                        + " ".join(f"[{d['id']}]" for d in state["retrieved_documents"])
                    )
                    state["citations"] = [d["id"] for d in state["retrieved_documents"]]
                    observations = []
                    for call in state["tool_calls"]:
                        if call["status"] == "OK" and call["name"] == "metrics_tool":
                            result = call["result"]
                            observations.append(
                                f"Verified tool output (simulated): {result['service']} CPU {result['cpu']}%, memory {result['memory']}%, P95 latency {result['p95_latency_ms']} ms, error rate {result['error_rate']:.1%}."
                            )
                    if observations:
                        state["generated_answer"] = (
                            "\n\n".join(observations) + "\n\n" + state["generated_answer"]
                        )
                span["output_summary"] = {"fallback": fallback}
                return {
                    "fallback": fallback,
                    "generated_answer": state["generated_answer"],
                    "citations": state["citations"],
                }

        graph = StateGraph(AgentState)
        for name, node in [
            ("analyze_query", analyze_query),
            ("retrieve_context", retrieve_context),
            ("select_tools", choose_tools),
            ("execute_tools", execute_tools),
            ("generate_answer", generate_answer),
            ("validate_answer", validate_answer),
            ("retry", retry),
            ("finalize_response", finalize_response),
        ]:
            graph.add_node(name, node)
        graph.add_edge(START, "analyze_query")
        graph.add_conditional_edges(
            "analyze_query",
            lambda s: (
                "generate_answer"
                if s["safe_response"] or s["query_category"] == "general"
                else "retrieve_context"
            ),
        )
        graph.add_edge("retrieve_context", "select_tools")
        graph.add_conditional_edges(
            "select_tools", lambda s: "execute_tools" if s["selected_tools"] else "generate_answer"
        )
        graph.add_edge("execute_tools", "generate_answer")
        graph.add_edge("generate_answer", "validate_answer")
        graph.add_conditional_edges(
            "validate_answer",
            lambda s: (
                "retry"
                if not s["validation_results"]["valid"]
                and s["retry_count"]
                < (1 if self.config.demo_mode else self.config.live_generation_retries)
                else "finalize_response"
            ),
        )
        graph.add_edge("retry", "generate_answer")
        graph.add_edge("finalize_response", END)
        initial: AgentState = {
            "query": query,
            "trace_id": recorder.trace_id,
            "retrieved_documents": [],
            "retrieval_scores": [],
            "selected_tools": [],
            "tool_calls": [],
            "tool_results": [],
            "retry_count": 0,
            "trajectory": [],
            "validation_errors": [],
            "execution_metadata": {"scenario": scenario, "demo_mode": self.config.demo_mode},
        }
        return await graph.compile().ainvoke(initial)
