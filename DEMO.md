# Demo playbook

Start with `docker compose up --build` and open http://localhost:3000. Seeding executes 200 synthetic requests with fixed fixture selection, real tracing and real waits. IDs and measured latencies vary by host. The dashboard labels simulated judging and cost; do not describe these as measured model accuracy or paid expenditure.

| # | Scenario | Action | Evidence to show |
|---|---|---|---|
| 1 | Healthy RAG | Run agent: “Why is my Kubernetes pod in CrashLoopBackOff?” | Query analysis, embedding, retrieval, generation, validation, runbook IDs |
| 2 | Tool-assisted support | Ask about checkout-api P95 latency | MetricsTool span, deterministic CPU/latency/error output |
| 3 | Historical incidents | Ask for historical checkout-api incidents | IncidentTool results scoped to the requested service |
| 4 | Empty retrieval | Chaos Lab → Empty retrieval | Zero context, retrieval failure, transparent answer |
| 5 | Bad retrieval | Chaos Lab → Bad retrieval | Unrelated context and low similarity detected independently |
| 6 | Stale evidence | Chaos Lab → Outdated document | Expired revision in retrieved context |
| 7 | Tool timeout | Chaos Lab → Tool timeout | Actual 2.5s deadline, error span, LATENCY_FAILURE |
| 8 | Tool contract failure | Run Tool 500 and Malformed tool JSON | Server failure vs schema validation evidence |
| 9 | Redundant work | Chaos Lab → Duplicate tool call | Two actual calls, trajectory penalty and extra latency |
| 10 | Tail latency | Chaos Lab → Slow LLM | Generation waits at least 2.2s and is attributed as slow |
| 11 | Hallucinated citation | Chaos Lab → Hallucinated citation | Validation failure twice, one retry, safe fallback with real IDs |
| 12 | Injection attempt | Chaos Lab → Prompt injection | security_event, refusal, no retrieval or tools |
| 13 | Context/model limits | Run Long context and Generation failure | Bounded context; retry then fallback on failed generation |
| 14 | Distribution shift | Drift monitor → Simulate traffic shift | 30 executed repeated long queries, changed means and centroid |
| 15 | Release workflow | Run experiment, normal regression, then degraded release | Paired A/B metrics, PASS policy, DEPLOYMENT BLOCKED reasons |

After any failure, open its trace and submit negative feedback. In Review queue, approve the candidate and export JSON. The export is a review artifact; a developer still needs to annotate expected answers/documents/tools in a dataset PR.

To reset, choose a new SQLite database path or a fresh Compose volume. `docker compose down` preserves existing data. Only use `docker compose down -v` if you explicitly intend to delete local demo traces and feedback.

If the UI reports an offline backend, inspect `docker compose logs backend`. Initial startup waits for seeding; subsequent startup should be quick. If API_KEY is configured, enter it in Connection settings. If running without Docker, verify Vite is on 5173 and FastAPI on 8000.
