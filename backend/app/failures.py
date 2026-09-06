"""Evidence-first, multi-label failure attribution. Never infer a fault from its chaos label."""


def analyze_failures(trace: dict):
    failures = []

    def add(category, component, severity, evidence, action):
        failures.append(
            {
                "failure_category": category,
                "likely_component": component,
                "severity": severity,
                "evidence": [evidence],
                "recommended_action": action,
            }
        )

    e = trace["evaluation"]
    docs = trace["retrieved_documents"]
    if not docs and not trace["safe_response"] and trace.get("query_category") != "general":
        add(
            "RETRIEVAL_FAILURE",
            "Retriever",
            "HIGH",
            "No context returned for an in-domain query.",
            "Inspect indexing and query coverage.",
        )
    elif docs and max(d["score"] for d in docs) < 0.08:
        add(
            "LOW_RETRIEVAL_CONFIDENCE",
            "Retriever",
            "MEDIUM",
            "Top similarity below 0.08.",
            "Review corpus coverage and query routing.",
        )
    if any(d.get("stale") for d in docs):
        add(
            "RETRIEVAL_FAILURE",
            "KnowledgeBase",
            "MEDIUM",
            "Retrieved an expired runbook revision.",
            "Refresh documents and enforce freshness policy.",
        )
    if trace["validation_errors"]:
        if any("citation" in error for error in trace["validation_errors"]):
            add(
                "CITATION_FAILURE",
                "CitationValidator",
                "HIGH",
                "Fabricated or missing citation detected in an attempted answer.",
                "Constrain references to retrieved IDs and re-evaluate the prompt.",
            )
        if "context_overflow" in trace["validation_errors"]:
            add(
                "CONTEXT_OVERFLOW",
                "Retriever",
                "HIGH",
                "Context exceeded the 16,000 character budget and was truncated.",
                "Reduce top-k or enforce chunk budgets.",
            )
        if "generation_failure" in trace["validation_errors"]:
            add(
                "MODEL_FAILURE",
                "Generation",
                "HIGH",
                "Generation failed after a bounded retry.",
                "Inspect local model health and preserve a safe fallback.",
            )
    for call in trace["tool_calls"]:
        if call["status"] != "OK":
            add(
                "TOOL_EXECUTION_ERROR",
                call["name"],
                "HIGH",
                call["error"],
                "Inspect tool schema, status and deadlines.",
            )
    if e["tool_selection"] is not None and e["tool_selection"] < 1:
        add(
            "TOOL_SELECTION_ERROR",
            "ToolSelection",
            "MEDIUM",
            "Selected tools differ from labeled expectations.",
            "Review routing against expected tool intent.",
        )
    if e["redundant_tool_calls"]:
        add(
            "REDUNDANT_TOOL_USAGE",
            "ToolExecution",
            "MEDIUM",
            f"{e['redundant_tool_calls']} duplicate call(s).",
            "Deduplicate tool arguments before dispatch.",
        )
    if e["faithfulness"] is not None and e["faithfulness"] < 0.5 and docs and not trace["fallback"]:
        add(
            "LOW_GROUNDING_PROXY",
            "Generation",
            "HIGH",
            "Low lexical overlap with context; requires human verification.",
            "Review grounding and sampled semantic judge results.",
        )
    if e["response_structure"] < 1:
        add(
            "PROMPT_FAILURE",
            "Validation",
            "HIGH",
            "Final response failed structural validation.",
            "Enforce response schema and citation format.",
        )
    if trace["security_event"]:
        add(
            "SAFETY_FAILURE",
            "QueryAnalysis",
            "HIGH",
            "Prompt injection attempt detected; request safely refused."
            if trace["safe_response"]
            else "Unsafe input was not refused.",
            "Review the security event; keep untrusted content isolated.",
        )
    slow = [
        s
        for s in trace["spans"]
        if s["duration_ms"] > trace.get("span_latency_budget_ms", 2000)
        and s["name"] not in ["SupportAgent", "ToolExecution"]
    ]
    if slow or trace["duration_ms"] > trace.get("request_latency_budget_ms", 5000):
        offender = (
            max(slow, key=lambda s: s["duration_ms"])
            if slow
            else {"name": "SupportAgent", "duration_ms": trace["duration_ms"]}
        )
        add(
            "LATENCY_FAILURE",
            offender["name"],
            "HIGH",
            f"Measured duration {offender['duration_ms']:.0f} ms.",
            "Inspect the slow span and bound latency with timeouts.",
        )
    if (
        e["quality_score"] < 0.6
        and not failures
        and (docs or trace["tool_calls"])
        and not trace["safe_response"]
    ):
        add(
            "UNKNOWN",
            "SupportAgent",
            "MEDIUM",
            "Quality score is below 0.60.",
            "Send the trace for human review.",
        )
    # Latency first makes the timeout scenario's operational symptom immediately visible.
    failures.sort(
        key=lambda f: (f["failure_category"] != "LATENCY_FAILURE", f["severity"] != "HIGH")
    )
    return failures
