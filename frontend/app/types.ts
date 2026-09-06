export type Failure = {
  failure_category: string;
  likely_component: string;
  severity: string;
  evidence: string[];
  recommended_action: string;
};
export type Evaluation = {
  [key: string]: unknown;
  quality_score: number;
  faithfulness: number | null;
  answer_relevance: number;
  context_precision: number | null;
  context_recall: number | null;
  citation_accuracy: number;
  trajectory_efficiency: number;
  tool_success: number;
  safety: number;
  expected: string[];
  actual: string[];
  judge: {
    status: string;
    source: string;
    reason?: string;
    result: Record<string, number | string> | null;
  };
};
export type Span = {
  span_id: string;
  parent_id: string | null;
  name: string;
  duration_ms: number;
  offset_ms: number;
  status: string;
  input: unknown;
  output_summary: unknown;
  error: string | null;
  model: string;
  token_estimate: number;
};
export type Trace = {
  demo_mode?: boolean;
  execution_metadata?: { tool_selection_source?: string };
  trace_id: string;
  query: string;
  status: string;
  duration_ms: number;
  timestamp: string;
  evaluation: Evaluation;
  failures: Failure[];
  scenario: string | null;
  model: string;
  answer: string;
  spans: Span[];
  retrieved_documents: {
    id: string;
    title: string;
    text: string;
    score: number;
    stale: boolean;
  }[];
  tool_calls: {
    id: string;
    name: string;
    status: string;
    duration_ms: number;
    result: unknown;
    error: string | null;
  }[];
  retry_count: number;
  tokens: {
    input: number;
    output: number;
    total: number;
    simulated_cost: number;
  };
  request_latency_ms: number;
  evaluation_latency_ms: number;
};
export type Overview = {
  demo_mode: boolean;
  total_requests: number;
  success_rate: number;
  p95_latency_ms: number;
  p50_latency_ms: number;
  p99_latency_ms: number;
  average_evaluation_score: number;
  tool_failure_rate: number;
  retrieval_quality: number;
  estimated_tokens: number;
  active_alerts: number;
  simulated_cost: number;
  tokens_per_request: number;
  simulated_cost_per_request: number;
  window: string;
  timeline: {
    time: string;
    requests: number;
    quality: number;
    latency: number;
  }[];
  failure_categories: { name: string; value: number }[];
  tool_usage: { name: string; value: number }[];
};
export type Drift = {
  status: string;
  drift_score: number;
  explanation: string;
  baseline_count: number;
  recent_count: number;
  embedding_source?: string;
  metrics: {
    name: string;
    baseline: number;
    recent: number;
    change_percent: number | null;
    score: number;
    status: string;
  }[];
};
export type Experiment = {
  id: string;
  timestamp: string;
  a: Record<string, number>;
  b: Record<string, number>;
  winner: string;
  cases: number;
  rationale: string;
};
export type Regression = {
  id: string;
  timestamp: string;
  status: string;
  passed: number;
  total: number;
  reasons: string[];
  metrics: Record<string, number>;
  comparisons: {
    metric: string;
    baseline: number;
    current: number;
    difference: number;
  }[];
  cases: { id: string; query: string; passed: boolean }[];
};
export type Alert = {
  id: string;
  title: string;
  active: boolean;
  severity: string;
  evidence: string;
};
export type Candidate = {
  id: string;
  query: string;
  trace_id: string;
  status: string;
  source: string;
  reason?: string;
};
export type Scenario = {
  id: string;
  name: string;
  description: string;
  group: string;
};
