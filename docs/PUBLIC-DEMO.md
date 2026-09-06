# Public demo and live answers

Tested local CPU configuration: `OLLAMA_MODEL=llama3.2:1b`, `STRUCTURED_ANSWERS=true`, `LLM_TOOL_SELECTION=false`, `LLM_MAX_OUTPUT_TOKENS=220`, `LLM_TIMEOUT_SECONDS=60`, `PUBLIC_REQUEST_TIMEOUT_SECONDS=70`, `PUBLIC_MAX_ACTIVE=1`, `SPAN_LATENCY_BUDGET_MS=45000`, `REQUEST_LATENCY_BUDGET_MS=60000`. Structured mode uses the best matching runbook and validates model-selected reference IDs. These checks do not establish semantic correctness. The explicit local latency budgets are recorded in each trace; demo defaults remain 2 seconds per span and 5 seconds per request.

Keep `LIVE_GENERATION_RETRIES=0` for this CPU configuration. It executes rule-selected diagnostic tools and makes one bounded LLM generation call. Overlapping requests receive a retry message instead of queueing. The earlier 20-second timeout was too short and has been replaced. Model failures preserve verified simulated metrics in the fallback answer.

## Running with a real model locally

The default is still a credential-free runbook demo. It executes Python diagnostic tools with simulated data, uses rule-based selection, and performs no LLM generation or judgment. Successful tool values now appear in answers.

For custom answers, configure `.env` before starting the backend:

```dotenv
DEMO_MODE=false
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:latest
SEMANTIC_RETRIEVAL=false
SEED_ON_START=false
ONLINE_EVAL_SAMPLE_RATE=0
```

Use `ollama list` to choose an installed model supporting tool calling. Live mode asks the model to select from two allowlisted diagnostic tools, executes at most one call per tool, and supplies results back to the model for the final answer. Tool arguments are bound to the request's selected service; the model cannot run shell commands or arbitrary functions. A failed/invalid tool plan uses an explicitly traced rules fallback. General questions go directly to generation. No hidden chain-of-thought is recorded or displayed.

Both diagnostic tools still use simulated fixtures. Live generation does not make their telemetry real. No browsing/search tool is provided, so answers about current events are not verified. Generation has bounded retries and a timeout; a model failure produces an explicit fallback.

Set `ONLINE_EVAL_SAMPLE_RATE=0.10` to sample a separate model judgment. This adds latency and uses the same configured model, so it is not independent ground truth. TF-IDF retrieval works without model downloads; `SEMANTIC_RETRIEVAL=true` requires installing `.[local]` and loading the embedding model.

## Spaces

The Docker default stays in demo mode. Your computer's localhost Ollama endpoint is not reachable from a Space. Live mode on Spaces needs an Ollama server reachable by that container or a future hosted-provider integration. Do not set the local-only URL above in a Space expecting it to reach your computer.

## Public request protection

All POST `/api/` actions share 30 requests per minute and at most four active requests per server process. Experiments, regression runs and drift generation additionally share two starts per ten minutes, with only one active heavy action. Invalid requests also consume admission budget. Limits are configurable through the `PUBLIC_*` values in `.env.example`.

Requests are rejected with HTTP 429 and Retry-After instead of accumulating an unbounded queue. Bodies over 16 KiB are rejected before JSON parsing, including chunked bodies. A 180-second request deadline includes body reading and asynchronous execution; cancellation releases admission slots. Read endpoints remain available. These are global budgets, intentionally independent of spoofable forwarding headers. They are not a distributed rate limiter or a replacement for authentication; run one worker for this deployment or use an external shared limiter. Process restarts reset budgets. Python CPU-bound work cannot be preempted by an asyncio deadline.

## Evaluation version 2.0

- Evidence overlap includes successful tool outputs. It is a lexical proxy, not semantic faithfulness; no evidence means null.
- Clarifications/refusals no longer receive automatic perfect relevance or grounding scores.
- Unlabeled tool-selection accuracy is null. Online trajectory comparison measures execution shape, not independently labeled correctness.
- Citation ID validity checks references, not whether claims are supported.
- Demo mode returns no fabricated judge scores. The dashboard excludes simulated judgments from real judge coverage and excludes legacy evaluator versions from the evaluation summary.
- The quality composite averages applicable proxies/checks; it is not a probability of correctness and should not be compared between unrelated question types.
- Baselines carry an evaluator version. The old committed baseline intentionally blocks comparisons with version 2.0 until results are reviewed. Run `python scripts/evaluate.py` to inspect results. Only after review, run `python scripts/evaluate.py --write-baseline` and commit the reviewed baseline. CI must never update it automatically.

Existing traces are preserved with their original scores. New traces use version 2.0. The overview's historical request/quality timeline still includes old records; use the evaluation page for version-filtered summaries.
