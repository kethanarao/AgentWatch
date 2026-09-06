# Implementation boundaries and verification

AgentWatch is a working portfolio reference with synthetic data. Its core reliability workflows are implemented, not static dashboard fixtures.

## Verified on this host

- Python 3.12: **35 tests passed, 1 skipped**. The skip is the explicitly optional Ollama semantic metric test. Backend statement coverage: **89.6%**.
- Real HTTP smoke test: **31 successful checks**, including all 12 fault scenarios, feedback approval/export, A/B execution, traffic drift and both gate outcomes.
- A fresh SQLite startup executed **200 traces**, then served a populated dashboard without external credentials or seeding errors. Full tracing creates more than 500 spans.
- Normal golden release gate: **PASS**, with **57/60 per-case passes**, **93.75% recall**, **100% final citation accuracy**, and **100% lexical grounding proxy**. Three lexical-retrieval misses remain in this baseline; the configured aggregate gate permits them. This does not mean all answers are semantically correct.
- Degraded retrieval: **DEPLOYMENT BLOCKED** with recall-related reasons, verified by automated tests and the HTTP smoke run.
- TypeScript strict checks, Vite production build, ESLint and Ruff checks passed. Frontend formatting uses Prettier.
- Docker Compose v2.39.4's actual parser accepted both the default configuration and the optional observability/local-LLM profiles, including `.env.example` substitution. The downloaded parser binary was checked against its published SHA-256.

## Not verified here

- Docker Engine is not installed on this Windows host. Container image builds, Linux startup and Compose health orchestration were not executed here. The GitHub Actions workflow includes these checks for a Docker-capable runner; it has been authored, not run remotely.
- No Ollama model, sentence-transformers model, FAISS live index, PostgreSQL server, Langfuse instance or Grafana server was launched here. Those optional code paths and deployment configurations are included; they still need an integration run in their target environment.
- No cloud account was used and no public deployment was created. The Docker Space deployment guide is ready for a user-owned hosting account.
- A local preview was opened and served through the API proxy. No screenshot-based or automated browser-interaction QA was performed. The optional WebMCP tool is feature-detected but was not exercised in a supported WebMCP validation context.

## Intentional simplifications

- Demo generation copies retrieved runbook guidance; its judge is a labeled simulation. Deterministic faithfulness/relevance are lexical proxies, not semantic judgments. Real DeepEval built-in metrics require the optional local model.
- Safety detection is a small regex filter, not a comprehensive prompt-injection defense. Use only sanitized demo questions. Raw internal traces are persisted, without a full PII-redaction pipeline.
- Tools always return synthetic operational data. They never contact Kubernetes or execute shell remediation commands.
- Online evaluation is completed within the HTTP request and stored in a distinct phase; it is not a durable background evaluation queue. Latency shown as agent latency excludes queue wait and judge overhead, which are separately labeled in trace details.
- SQLite/SQLAlchemy uses fresh-table creation and JSON records, without migrations, tenant isolation, retention or an async storage layer. Dashboards read the latest 1,000 stored requests. Prometheus counters rehydrate that bounded history after restart, not lifetime totals beyond the retained query window.
- Concurrency is bounded within one process. Benchmark execution is serial for controlled measurements; production-like seed traffic remains concurrent. A 100 ms deadband is applied alongside the relative latency gate to reduce host scheduling noise. This is configurable, not a claim of hardware-independent benchmarking.
- Drift scores are effect-size heuristics, not significance tests. A/B utility is a declared policy with a tie threshold, not statistical proof of a winner.
- Approved feedback candidates are exported for manual labeling and a reviewed dataset PR. Approval does not automatically invent expected answers or edit the golden dataset.
- Token accounting uses character estimates and excludes judge tokens. All dollar figures are hypothetical and clearly labeled SIMULATED COST; local inference carries no paid API charge.
- The dashboard's chart/UI bundle is about 247 KB compressed. Vite emits a non-fatal chunk-size advisory; route/chart splitting is a future optimization.

## Before use with real traffic

Add SSO/RBAC, request rate limits, sensitive-data redaction, retention, durable jobs, schema migrations, calibrated semantic judging, stronger adversarial testing and infrastructure-specific deployment verification. Rebuild a reviewed baseline when changing model mode or golden data; a hash/mode mismatch blocks release.
