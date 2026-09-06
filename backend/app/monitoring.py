from collections import Counter

import numpy as np
from prometheus_client import CollectorRegistry, Counter as PCounter, Histogram, generate_latest


def percentile(values, q):
    return round(float(np.percentile(values, q)), 2) if values else 0.0


class Metrics:
    def __init__(self):
        self.registry = CollectorRegistry()
        self.counters = {
            name: PCounter(name, name.replace("_", " "), registry=self.registry)
            for name in [
                "agent_requests_total",
                "agent_success_total",
                "agent_failure_total",
                "tool_calls_total",
                "tool_failures_total",
                "agent_retries_total",
                "citation_failures_total",
                "estimated_tokens_total",
                "online_eval_total",
            ]
        }
        self.histograms = {
            name: Histogram(
                name,
                name.replace("_", " "),
                registry=self.registry,
                buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 120),
            )
            for name in [
                "agent_latency_seconds",
                "retrieval_latency_seconds",
                "tool_latency_seconds",
                "generation_latency_seconds",
            ]
        }
        self.scores = {
            name: Histogram(
                name,
                name.replace("_", " "),
                registry=self.registry,
                buckets=(0, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 1),
            )
            for name in ["retrieval_score", "faithfulness_score", "answer_relevance_score"]
        }

    def record(self, trace):
        self.counters["agent_requests_total"].inc()
        self.counters[
            "agent_success_total" if trace["status"] == "OK" else "agent_failure_total"
        ].inc()
        self.counters["tool_calls_total"].inc(len(trace["tool_calls"]))
        self.counters["tool_failures_total"].inc(
            sum(c["status"] != "OK" for c in trace["tool_calls"])
        )
        self.counters["agent_retries_total"].inc(trace["retry_count"])
        self.counters["citation_failures_total"].inc(
            sum("citation" in s for s in trace["validation_errors"])
        )
        self.counters["estimated_tokens_total"].inc(trace["tokens"]["total"])
        self.counters["online_eval_total"].inc(
            trace["evaluation"]["judge"]["status"] == "completed"
        )
        self.histograms["agent_latency_seconds"].observe(trace["duration_ms"] / 1000)
        for span in trace["spans"]:
            key = {
                "Retrieval": "retrieval_latency_seconds",
                "ToolExecution": "tool_latency_seconds",
                "Generation": "generation_latency_seconds",
            }.get(span["name"])
            if key:
                self.histograms[key].observe(span["duration_ms"] / 1000)
        self.scores["retrieval_score"].observe(max(trace["retrieval_scores"], default=0))
        if trace["evaluation"]["faithfulness"] is not None:
            self.scores["faithfulness_score"].observe(trace["evaluation"]["faithfulness"])
        self.scores["answer_relevance_score"].observe(trace["evaluation"]["answer_relevance"])

    def render(self):
        return generate_latest(self.registry)


def overview(traces: list[dict]):
    n = len(traces)

    def avg(values):
        return round(sum(values) / max(1, len(values)), 4)

    calls = [c for t in traces for c in t["tool_calls"]]
    latency = [t["duration_ms"] for t in traces]
    chronological = sorted(traces, key=lambda t: t["timestamp"])
    buckets = {}
    for t in chronological:
        hour = t["timestamp"][:13] + ":00"
        buckets.setdefault(hour, []).append(t)
    timeline = [
        {
            "time": h,
            "requests": len(rows),
            "quality": avg([t["evaluation"]["quality_score"] for t in rows]),
            "latency": percentile([t["duration_ms"] for t in rows], 95),
        }
        for h, rows in buckets.items()
    ]
    counts = Counter(f["failure_category"] for t in traces for f in t["failures"])
    return {
        "total_requests": n,
        "success_rate": avg([float(t["status"] == "OK") for t in traces]),
        "p50_latency_ms": percentile(latency, 50),
        "p95_latency_ms": percentile(latency, 95),
        "p99_latency_ms": percentile(latency, 99),
        "average_evaluation_score": avg([t["evaluation"]["quality_score"] for t in traces]),
        "tool_failure_rate": avg([float(c["status"] != "OK") for c in calls]),
        "retrieval_quality": avg(
            [max(t["retrieval_scores"], default=0) for t in traces if not t["safe_response"]]
        ),
        "citation_accuracy": avg([t["evaluation"]["citation_accuracy"] for t in traces]),
        "estimated_tokens": sum(t["tokens"]["total"] for t in traces),
        "tokens_per_request": avg([t["tokens"]["total"] for t in traces]),
        "simulated_cost": sum(t["tokens"]["simulated_cost"] for t in traces),
        "simulated_cost_per_request": avg([t["tokens"]["simulated_cost"] for t in traces]),
        "timeline": timeline,
        "failure_categories": [{"name": k, "value": v} for k, v in counts.items()],
        "tool_usage": [
            {"name": k, "value": v} for k, v in Counter(c["name"] for c in calls).items()
        ],
        "window": f"Latest {n} stored requests (maximum 1000)",
        "simulated_cost_label": "SIMULATED COST",
    }
