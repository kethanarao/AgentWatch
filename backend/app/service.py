import asyncio
import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

from .agent import SupportAgent
from .config import ROOT, Settings
from .database import Alert, Candidate, DriftSnapshot, Experiment, RegressionRun, Store, Trace
from .drift import detect_drift
from .evaluation import EVALUATOR_VERSION, deterministic_evaluation, judge
from .failures import analyze_failures
from .monitoring import Metrics, overview
from .rag import Retriever, feature_embedding
from .regression import golden_cases, quality_gate, summarize
from .tracing import Recorder

SCENARIOS = [
    (
        "bad_retrieval",
        "Bad retrieval",
        "Replace relevant results with unrelated context.",
        "retrieval",
    ),
    ("empty_retrieval", "Empty retrieval", "Return zero knowledge-base matches.", "retrieval"),
    (
        "outdated_document",
        "Outdated document",
        "Retrieve an expired runbook revision.",
        "retrieval",
    ),
    ("tool_timeout", "Tool timeout", "Exceed a real 2.5-second tool deadline.", "tools"),
    ("tool_500", "Tool 500 error", "Raise a simulated upstream server error.", "tools"),
    (
        "malformed_tool_json",
        "Malformed tool JSON",
        "Fail Pydantic validation of tool output.",
        "tools",
    ),
    ("duplicate_tool_call", "Duplicate tool call", "Execute the same tool twice.", "tools"),
    ("slow_llm", "Slow LLM", "Add 2.2 seconds to generation.", "generation"),
    (
        "hallucinated_citation",
        "Hallucinated citation",
        "Fabricate a reference and exercise retry/fallback.",
        "generation",
    ),
    (
        "prompt_injection",
        "Prompt injection",
        "Inject a hostile instruction and test refusal.",
        "safety",
    ),
    (
        "long_context",
        "Long context",
        "Overflow the context budget before truncation.",
        "generation",
    ),
    (
        "generation_failure",
        "Generation failure",
        "Fail both attempts and return a safe fallback.",
        "generation",
    ),
]


class Platform:
    def __init__(self, config: Settings):
        self.config = config
        self.store = Store(config.database_url)
        self.retriever = Retriever(config)
        self.agent = SupportAgent(config, self.retriever)
        self.metrics = Metrics()
        self.semaphore = asyncio.Semaphore(config.max_concurrent_runs)
        self.benchmark_lock = asyncio.Lock()
        self.seeding = False
        self.seed_error = None
        self.last_alert_update = 0.0
        # Rehydrate process-local Prometheus counters from durable observations on restart.
        for trace in self.store.list(Trace):
            self.metrics.record(trace)

    async def run(
        self,
        query,
        top_k=3,
        service="checkout-api",
        scenario=None,
        golden=None,
        persist=True,
        latency_scale=None,
        timestamp=None,
    ):
        async with self.semaphore:
            recorder = Recorder(
                "demo-deterministic-v1" if self.config.demo_mode else self.config.ollama_model,
                self.config.otel_enabled,
            )
            begin = time.perf_counter()
            with recorder.span("SupportAgent", {"query": query, "service": service}):
                state = await self.agent.run(
                    query, service, top_k, scenario, recorder, latency_scale
                )
            selected = state["selected_tools"]
            expected = [
                "analyze_query",
                *(
                    []
                    if state["safe_response"] or state["query_category"] == "general"
                    else [
                        "retrieve_context",
                        "select_tools",
                        *(["execute_tools", *selected] if selected else []),
                    ]
                ),
                "generate_answer",
                "validate_answer",
                "finalize_response",
            ]
            input_chars = (
                len(query)
                + sum(len(d["text"]) for d in state["retrieved_documents"])
                + len(json.dumps(state["tool_results"]))
            )
            input_tokens, output_tokens = (
                (input_chars + 3) // 4,
                (len(state["generated_answer"]) + 3) // 4,
            )
            # Account for every generation attempt; judge usage is reported separately.
            input_tokens *= 1 + state["retry_count"]
            output_tokens *= 1 + state["retry_count"]
            trace = {
                **state,
                "trace_id": recorder.trace_id,
                "query": query,
                "answer": state["generated_answer"],
                "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
                "spans": recorder.spans,
                "duration_ms": round((time.perf_counter() - begin) * 1000, 3),
                "expected_trajectory": expected,
                "scenario": scenario,
                "service": service,
                "model": recorder.model,
                "demo_mode": self.config.demo_mode,
                "span_latency_budget_ms": self.config.span_latency_budget_ms,
                "request_latency_budget_ms": self.config.request_latency_budget_ms,
                "query_embedding": feature_embedding(query)
                if not self.config.semantic_retrieval
                else self.retriever.embed(query).tolist(),
                "embedding_source": "hashed lexical demo vectors"
                if not self.config.semantic_retrieval
                else self.config.embedding_model,
                "tokens": {
                    "input": input_tokens,
                    "output": output_tokens,
                    "total": input_tokens + output_tokens,
                    "simulated_cost": (
                        input_tokens * self.config.input_cost_per_1m
                        + output_tokens * self.config.output_cost_per_1m
                    )
                    / 1_000_000,
                    "profile": self.config.cost_profile,
                    "label": "SIMULATED COST",
                    "estimator": "characters / 4; excludes judge",
                },
            }
            with recorder.span("DeterministicEvaluation") as span:
                trace["evaluation"] = deterministic_evaluation(trace, golden)
                span["output_summary"] = {"quality_score": trace["evaluation"]["quality_score"]}
            with recorder.span("OnlineJudge") as span:
                trace["evaluation"]["judge"] = await judge(trace, self.config)
                span["output_summary"] = trace["evaluation"]["judge"]
            trace["evaluation_latency_ms"] = round(
                (time.perf_counter() - begin) * 1000 - trace["duration_ms"], 3
            )
            trace["request_latency_ms"] = round((time.perf_counter() - begin) * 1000, 3)
            trace["failures"] = analyze_failures(trace)
            trace["status"] = "ERROR" if trace["failures"] else "OK"
            if persist:
                self.store.save_trace(trace)
                self.metrics.record(trace)
                if trace["failures"]:
                    self.store.put(
                        Candidate,
                        recorder.trace_id,
                        {
                            "id": recorder.trace_id,
                            "query": query,
                            "trace_id": recorder.trace_id,
                            "status": "pending",
                            "source": "automatic_failure",
                            "failure_categories": [
                                f["failure_category"] for f in trace["failures"]
                            ],
                        },
                    )
                if not self.seeding and time.monotonic() - self.last_alert_update > 2:
                    self.refresh_alerts()
            logging.getLogger("agentwatch").info(
                json.dumps(
                    {
                        "event": "agent_completed",
                        "trace_id": trace["trace_id"],
                        "status": trace["status"],
                        "duration_ms": trace["duration_ms"],
                    }
                )
            )
            return trace

    def drift(self):
        traces = sorted(self.store.list(Trace), key=lambda t: t["timestamp"])
        baseline = traces[: min(50, len(traces) // 2)]
        recent = traces[-min(50, len(traces) // 2) :] if len(traces) >= 2 else []
        return detect_drift(baseline, recent)

    def refresh_alerts(self):
        self.last_alert_update = time.monotonic()
        traces = self.store.list(Trace)
        recent = traces[:50]
        current = overview(recent)
        baseline = overview(traces[-50:])
        drift = self.drift()
        rules = [
            (
                "latency",
                "HIGH LATENCY ALERT",
                current["p95_latency_ms"] > max(100, baseline["p95_latency_ms"] * 1.3),
                f"Recent P95 {current['p95_latency_ms']:.0f} ms; baseline {baseline['p95_latency_ms']:.0f} ms",
            ),
            (
                "retrieval",
                "RETRIEVAL QUALITY DEGRADATION",
                current["retrieval_quality"] < baseline["retrieval_quality"] * 0.85,
                "Recent mean retrieval confidence fell more than 15%.",
            ),
            (
                "citation",
                "CITATION RELIABILITY ALERT",
                current["citation_accuracy"] < 0.95
                or any("citation_failure" in t["validation_errors"] for t in recent),
                "Citation validation failed in recent traffic; fallbacks may have recovered final accuracy.",
            ),
            (
                "tools",
                "TOOL FAILURE ALERT",
                current["tool_failure_rate"] > 0.1,
                f"Recent tool error rate {current['tool_failure_rate']:.0%}.",
            ),
            (
                "drift",
                "TRAFFIC DRIFT ALERT",
                drift["drift_score"] > 70,
                f"Drift score {drift['drift_score']}/100.",
            ),
        ]
        for id, title, active, evidence in rules:
            self.store.put(
                Alert,
                id,
                {
                    "id": id,
                    "title": title,
                    "active": bool(active),
                    "severity": "HIGH",
                    "evidence": evidence,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        self.store.put(
            DriftSnapshot,
            uuid.uuid4().hex,
            {**drift, "timestamp": datetime.now(timezone.utc).isoformat()},
        )

    async def benchmark(self, top_k=3, degraded=False, persist=False):
        cases = golden_cases()

        async def one(case):
            return await self.run(
                case["query"],
                top_k=top_k,
                scenario="empty_retrieval" if degraded and case["expected_documents"] else None,
                golden=case,
                persist=persist,
                latency_scale=0.02 if self.config.demo_mode else None,
            )

        # Serial benchmark runs avoid measuring contention between cases as model latency.
        # Online requests and seeding still exercise bounded concurrent execution.
        return [await one(case) for case in cases]

    async def regression(self, degraded=False):
        async with self.benchmark_lock:
            traces = await self.benchmark(degraded=degraded)
            current = summarize(traces)
            baseline_file = ROOT / "data/evaluation/baseline.json"
            baseline = json.loads(baseline_file.read_text()) if baseline_file.exists() else None
            if not baseline:
                raise RuntimeError(
                    "Missing committed baseline. Run scripts/evaluate.py --write-baseline explicitly."
                )
            gate = quality_gate(current, baseline["metrics"], self.config)
            dataset_hash = hashlib.sha256(
                (ROOT / "data/evaluation/golden_dataset.json").read_bytes()
            ).hexdigest()
            mode = "demo" if self.config.demo_mode else "ollama"
            if baseline.get("mode") != mode or baseline.get("dataset_sha256") != dataset_hash:
                gate["status"] = "DEPLOYMENT BLOCKED"
                gate["reasons"].append(
                    "Baseline mode or dataset hash differs; review and explicitly create a matching baseline."
                )
            if baseline.get("evaluator_version") != EVALUATOR_VERSION:
                gate["status"] = "DEPLOYMENT BLOCKED"
                gate["reasons"].append(
                    "Evaluator version changed. Review measured results before explicitly replacing the baseline."
                )
            cases = [
                {
                    "id": case["id"],
                    "query": case["query"],
                    "passed": t["evaluation"]["safety"] == 1
                    and t["evaluation"]["citation_accuracy"] >= 0.95
                    and (
                        t["evaluation"]["context_recall"] is None
                        or t["evaluation"]["context_recall"] >= 0.75
                    ),
                    "metrics": t["evaluation"],
                }
                for case, t in zip(golden_cases(), traces)
            ]
            result = {
                "id": uuid.uuid4().hex,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "degraded": degraded,
                "metrics": current,
                "evaluator_version": EVALUATOR_VERSION,
                **gate,
                "passed": sum(c["passed"] for c in cases),
                "total": len(cases),
                "cases": cases,
                "evaluation_mode": "deterministic demo"
                if self.config.demo_mode
                else "local Ollama",
                "timing_note": "Demo benchmarks use 0.02x waits; gates compare the same benchmark mode.",
            }
            self.store.put(RegressionRun, result["id"], result)
            return result

    async def experiment(self):
        async with self.benchmark_lock:
            a = summarize(await self.benchmark(top_k=3))
            b = summarize(await self.benchmark(top_k=5))

            def utility(m):
                return (
                    m["faithfulness"] * 0.35
                    + m["context_recall"] * 0.4
                    + m["answer_relevance"] * 0.25
                )

            difference = utility(b) - utility(a)
            winner = "TIE" if abs(difference) < 0.005 else "B" if difference > 0 else "A"
            result = {
                "id": uuid.uuid4().hex,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "a": a,
                "b": b,
                "winner": winner,
                "cases": len(golden_cases()),
                "config_a": {"top_k": 3},
                "config_b": {"top_k": 5},
                "rationale": "Utility = 35% grounding proxy + 40% labeled recall + 25% relevance proxy; differences <0.005 are ties. Latency is reported separately. No significance claim.",
            }
            self.store.put(Experiment, result["id"], result)
            return result

    async def seed(self, count=200):
        if self.store.list(Trace, 1):
            return
        self.seeding = True
        try:
            cases = golden_cases()[:48]
            epoch = datetime.now(timezone.utc) - timedelta(hours=24)
            for start in range(0, count, 4):
                jobs = []
                for i in range(start, min(start + 4, count)):
                    case = cases[(i * 7 + 19) % len(cases)]
                    fault = (
                        SCENARIOS[(i // 7) % len(SCENARIOS)][0] if i % 7 == 0 and i >= 50 else None
                    )
                    jobs.append(
                        self.run(
                            case["query"],
                            golden=case,
                            scenario=fault,
                            timestamp=(epoch + timedelta(minutes=i * 1440 / count)).isoformat(),
                        )
                    )
                await asyncio.gather(*jobs)
            self.refresh_alerts()
            if (ROOT / "data/evaluation/baseline.json").exists():
                await self.regression()
            await self.experiment()
        except Exception as exc:
            self.seed_error = str(exc)
            logging.getLogger("agentwatch").exception("Demo seeding failed")
        finally:
            self.seeding = False
