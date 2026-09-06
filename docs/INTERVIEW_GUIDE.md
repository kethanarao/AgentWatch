# Interview guide

## Opening narrative

“I built a small DevOps support agent so I could focus on how to know whether it is reliable. Every execution creates a trace and independent evaluations. I can inject a fault, inspect where it happened, review user feedback, and prevent the same regression from passing a release gate. The demo works without cloud models, so the full reliability workflow is easy to reproduce.”

## Evaluation versus observability

Observability explains what happened: the request path, retrieved context, tool calls, status and latency. Evaluation asks whether that behavior was good: was evidence relevant, were sources valid, did the expected tool run, and did quality regress? A fast successful HTTP response can still be wrong. A final valid fallback can conceal repeated invalid generation attempts unless attempt-level evidence is retained.

## Offline versus online

Offline evaluation provides repeatable comparisons on a versioned golden dataset with ground truth. Online checks identify novel failures and real traffic changes, but most production requests lack reference answers. AgentWatch leaves unlabeled precision/recall null. Cheap exact checks run on every request; expensive local semantic judging is sampled. Neither layer replaces human review.

## RAG failure localization

Precision, recall, hit rate and MRR evaluate evidence selection when labels exist. Generation grounding and citation checks evaluate answer behavior. Poor context with a fluent answer suggests retrieval failure; good context with fabricated references suggests generation/validation failure. Citation membership proves only that a cited ID was retrieved, not that the cited document supports the claim. Lexical overlap cannot establish entailment.

## LLM-as-a-judge limitations

Judges can show position, verbosity and style biases, follow injected text, and produce malformed schemas. A small local judge can be particularly inconsistent. Use strict output validation, bounded retries, sampling, human calibration and independent deterministic checks. Demo judge values in this project are explicitly simulated; do not present them as benchmarked LLM quality. The real local DeepEval suite uses five built-in semantic metrics with an Ollama adapter.

## Agent trajectories

Tool success alone misses waste. A tool can return 200 twice even when the second call is unnecessary. Expected/actual ordered paths expose redundant tools, extra retrieval and retries. The efficiency score combines expected-to-actual length with sequence similarity. It is transparent but not a universal optimality metric: a different valid path may deserve a different reference or set-based evaluation.

## Golden datasets and production-derived cases

The committed dataset spans ordinary questions, hard variants, tools, unsafe requests and ambiguous/irrelevant inputs. Production failure candidates enter a separate table. Approval exports a candidate; a reviewer must add real labels and submit a dataset change. This prevents noisy feedback or adversarial input from automatically redefining the release benchmark. Dataset hashes and baseline mode are recorded for provenance.

## Drift and regression

Regression is quality loss on a controlled reference set after a change. Drift is a change in traffic or system distributions; it may be benign. This implementation uses effect-size heuristics, minimum sample counts and centroid distance. It reports the affected signals rather than claiming causal proof or statistical significance. A production extension should calibrate windows, seasonality and alert thresholds using operational data.

## P50, P95 and P99

P50 describes the typical request; P95/P99 describe tail experience. A system can maintain median latency while a few tool deadlines dominate its tail. AgentWatch stores request timings and Prometheus histograms, with agent latency separated from evaluation overhead. Demo waits and timing variability are disclosed. Relative latency gates include an absolute noise floor so tiny scheduling changes do not masquerade as meaningful degradation.

## Reliability and CI/CD

Bound concurrency, retries, timeouts, answer/context sizes and external dependencies. A failed optional judge does not discard a completed response or exact metrics. A failed citation validator triggers one retry and then safe fallback. CI enforces both absolute floors and relative changes against a committed baseline. Intentionally degraded retrieval proves the gate blocks, rather than relying on a green badge alone.

## Prompt regression and A/B tradeoffs

Prompt changes can alter tool use, answer structure or grounding even if retrieval is unchanged. Compare configurations against identical cases and inspect several metrics. AgentWatch compares top-k 3 and 5; extra context may improve recall while reducing precision or increasing latency. Its utility formula is explicit and reports ties, with no significance claim. A production rollout needs paired confidence intervals and representative traffic.

## Cost engineering

Local inference has no per-token API bill, but CPU/GPU time, power and latency are real resources. Character-based token estimates are approximate and exclude judge tokens here. Hypothetical input/output prices demonstrate accounting under a clearly marked SIMULATED COST profile. Avoid claiming dollar savings without an actual workload baseline.

## Failure injection

Show the difference between a cosmetic error flag and actual behavioral changes. AgentWatch removes retrieval results, injects expired evidence, waits past a tool deadline, validates malformed tool JSON, duplicates calls, delays generation, fabricates citations, overflows context or fails generation. The failure classifier sees resulting evidence rather than the chosen scenario label. Chaos is scoped to a single request and uses mock tools, so it does not affect real infrastructure.

## Honest production gaps

Discuss why one worker, JSON persistence, regex safety and lexical metrics make this easy to inspect but not production-complete. Priorities for a real service: durable worker queue, schema migrations, input redaction, SSO/RBAC, rate limits, retention, calibrated semantic evaluation, adversarial tests and a stronger retrieval corpus. The ability to name these boundaries is part of the engineering story.
