# Evaluation design

The golden dataset has 60 cases: 36 canonical support questions, 12 harder variants, four prompt injections, four irrelevant requests and four ambiguous requests. All fixtures and mock incidents are synthetic. Expected documents, tools, keywords, paths, category and difficulty are committed. Ground truth is not inferred from retrieved results.

| Metric | Definition | Interpretation |
|---|---|---|
| Citation validity | Parsed citation IDs must belong to retrieved context; citations required when context exists | Reference integrity, not factual truth |
| Grounding proxy (`faithfulness`) | Unique answer terms overlapping context / unique answer terms | Lexical evidence overlap, not semantic entailment |
| Answer relevance proxy | Query term coverage in the answer | Surface relevance; wording-sensitive |
| Precision@K | Unique relevant retrieved documents / unique retrieved documents | Labeled cases only |
| Recall@K | Retrieved relevant documents / expected documents | Labeled cases only |
| Hit rate / MRR | Any expected match / reciprocal first relevant rank | Labeled cases only |
| Contextual relevancy | Mean retrieval similarity | Search confidence proxy |
| Tool success | Successful calls / all calls | Empty trajectory has score 1 |
| Tool selection | Selected tool set equals expected set | Only informative on labeled cases |
| Trajectory efficiency | `min(1, expected_steps/actual_steps) * sequence_similarity` | Penalizes extra work and sequence differences |
| Trajectory deviation | `1 - SequenceMatcher(expected, actual).ratio()` | Simple ordered-path difference |
| Structure | Nonempty, ≤12,000 characters, valid citations | Final response validity |
| Composite quality | Mean of grounding, relevance, citations, tool success and trajectory | A diagnostic summary, not a safety guarantee |

Missing retrieval labels produce `null`, not an invented score. Aggregates exclude nulls. Correct refusals count as grounded/relevant safe responses; that policy is explicit and should be revisited for a broader dataset. Safety attempts are flagged as operational security events even when successfully refused, so operational success and safety effectiveness are different measures.

## Online and offline layers

All requests get exact checks and lexical proxies. A hash of the unique trace ID samples local judge traffic at `ONLINE_EVAL_SAMPLE_RATE` (default 0.10). Demo sampling defaults to 1.0 and returns a result labeled `simulated_judge`. Live judging sends evidence to local Ollama, validates four bounded scores and reasoning with Pydantic, retries invalid JSON once, then records unavailability without discarding the exact checks. Small models can be inconsistent judges; sampled scores are advisory.

DeepEval's custom `CitationMetric` runs in CI without a model. The optional suite uses the built-in Answer Relevancy, Faithfulness, Contextual Precision, Contextual Recall and Contextual Relevancy metrics with an Ollama adapter. It passes each metric's requested JSON schema through Ollama, validates outputs and has a bounded retry. `RUN_LOCAL_JUDGE=true` explicitly opts into this slower layer. A local model must be pulled first; no default paid DeepEval model is constructed.

## Baselines and release gates

`python scripts/evaluate.py --write-baseline` explicitly measures and replaces a baseline. This is a human-reviewed maintenance action, not part of ordinary evaluation or CI. Normal `python scripts/evaluate.py` writes Markdown/JSON reports and returns exit code 1 for a blocked gate. `--degraded` intentionally empties retrieval to prove the gate is active.

Minimum grounding proxy, context recall and citation accuracy are 0.80, 0.75 and 0.95. Maximum P95 is 5,000 ms. Any tracked metric that worsens over 10% relative to baseline also blocks the release; lower is better for latency and tool-call count. A 50 ms denominator floor and a configurable 100 ms minimum absolute latency increase limit scheduling-noise alerts. Benchmarks execute serially, use demo waits scaled to 0.02 and exclude persistence; do not compare those latencies to production or to a different model mode. The baseline records dataset hash and mode for provenance.

An experiment compares top-k 3 and 5 on identical cases. Winner utility weights grounding 35%, recall 40% and relevance 25%; differences below 0.005 are reported as a tie. Precision, latency, tools and trajectory are reported separately. The result does not claim statistical significance.

## Drift

Signals are query length, answer length, retrieval similarity, tool count, agent latency, quality and centroid distance. Mean shifts are divided by `max(baseline_std, 0.1*abs(baseline_mean), 0.01)` and multiplied by 25. Centroid cosine distance is multiplied by 200. Each signal is capped at 100 and the largest becomes the headline drift score. Above 40 is WARNING; above 70 is CRITICAL. These are effect-size heuristics, not z-tests or calibrated probabilities. Demo embeddings are stable hashed lexical vectors; live mode uses sentence-transformers vectors.

## Failure interpretation

Failure rules inspect actual empty context, scores, stale timestamps, validator history, tool errors, duplicates, structural checks, low grounding and measured span duration. They do not inspect the chaos scenario name. Multiple diagnoses may coexist. A recovered final answer can have valid citations while the historical attempted citation failure still creates an alert and review candidate. A hallucination label from lexical overlap is a suspicion requiring review, not a semantic proof.

