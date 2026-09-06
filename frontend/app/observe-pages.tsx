import { useState } from "react";
import {
  Activity,
  ArrowUpRight,
  Bell,
  Radar,
  Search,
  ShieldCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "./api";
import {
  Badge,
  Bars,
  Panel,
  Stat,
  TraceTable,
  Trend,
  human,
  ms,
  pct,
} from "./visuals";
import type { PageProps } from "./dashboard";

export function ObservePages({
  page,
  data,
  busy,
  action,
  openTrace,
  navigate,
}: PageProps) {
  const { overview, traces, evaluations, drift, alerts } = data;
  const currentEvaluations = evaluations.filter(
    (e) => e.evaluator_version === "2.0",
  );
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const filtered = traces.filter(
    (t) =>
      (status === "all" || t.status === status) &&
      (t.query + t.trace_id).toLowerCase().includes(search.toLowerCase()),
  );
  const avg = (key: string) => {
    const ns = currentEvaluations
      .map((e) => e[key])
      .filter((v): v is number => typeof v === "number");
    return ns.length ? ns.reduce((a, b) => a + b, 0) / ns.length : null;
  };
  if (page === "overview")
    return (
      <>
        <div className="signal-strip">
          <Activity />
          <span>Every answer. Accounted for.</span>
          <small>
            {overview?.demo_mode === false
              ? "Live LLM · simulated diagnostics"
              : "Runbook demo · no LLM"}{" "}
            · Measured traces · Sampled evaluation
          </small>
          <Badge>LIVE PIPELINE</Badge>
        </div>
        {overview ? (
          <>
            <div className="stats-grid">
              <Stat
                label="Total requests"
                value={overview.total_requests.toLocaleString()}
                note="Stored execution traces"
              />
              <Stat
                label="Success rate"
                value={pct(overview.success_rate)}
                note="Requests without detected failures"
                tone="mint"
              />
              <Stat
                label="P95 latency"
                value={ms(overview.p95_latency_ms)}
                note={`P50 ${ms(overview.p50_latency_ms)} · P99 ${ms(overview.p99_latency_ms)}`}
              />
              <Stat
                label="Evaluation score"
                value={pct(overview.average_evaluation_score)}
                note="Deterministic quality composite"
                tone="mint"
              />
              <Stat
                label="Tool failure rate"
                value={pct(overview.tool_failure_rate)}
                note="Failures / actual tool calls"
              />
              <Stat
                label="Retrieval quality"
                value={overview.retrieval_quality.toFixed(3)}
                note="Mean top-result similarity"
              />
              <Stat
                label="Estimated tokens"
                value={overview.estimated_tokens.toLocaleString()}
                note={`${Math.round(overview.tokens_per_request)} tokens / request`}
              />
              <Stat
                label="Active alerts"
                value={overview.active_alerts}
                note="Recent 50-request window"
                tone="amber"
              />
            </div>
            <div className="two-col">
              <Panel
                title="Quality score over time"
                extra={<Badge tone="good">● Composite score</Badge>}
              >
                <Trend data={overview.timeline} dataKey="quality" percent />
              </Panel>
              <Panel
                title="Latency over time"
                extra={<Badge>● P95 · milliseconds</Badge>}
              >
                <Trend
                  data={overview.timeline}
                  dataKey="latency"
                  color="#80aafa"
                />
              </Panel>
            </div>
            <div className="three-col">
              <Panel title="Failure categories">
                <Bars data={overview.failure_categories.slice(0, 5)} />
              </Panel>
              <Panel title="Request volume">
                <Trend
                  data={overview.timeline}
                  dataKey="requests"
                  color="#b89bee"
                />
              </Panel>
              <Panel title="Tool usage">
                <Bars data={overview.tool_usage} />
                <div className="cost-note">
                  <b>SIMULATED COST ${overview.simulated_cost.toFixed(4)}</b>
                  <span>
                    Stored window · $
                    {(
                      overview.simulated_cost /
                      Math.max(1, overview.total_requests)
                    ).toFixed(6)}{" "}
                    / request. Local model API spend: $0.
                  </span>
                </div>
              </Panel>
            </div>
            <Panel
              title="Recent executions"
              extra={
                <Button variant="ghost" onClick={() => navigate("traces")}>
                  All traces <ArrowUpRight size={15} />
                </Button>
              }
            >
              <TraceTable traces={traces.slice(0, 6)} onOpen={openTrace} />
            </Panel>
          </>
        ) : (
          <div className="stats-grid">
            {Array.from({ length: 8 }, (_, i) => (
              <Skeleton key={i} className="h-32" />
            ))}
          </div>
        )}
      </>
    );
  if (page === "traces")
    return (
      <Panel
        title={`${filtered.length} executions`}
        extra={<Badge>Latest 1,000 requests</Badge>}
      >
        <div className="filterbar">
          <div className="search-box">
            <Search size={17} />
            <Input
              aria-label="Search traces"
              placeholder="Search query or trace ID…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <Select value={status} onValueChange={(v) => setStatus(v ?? "all")}>
            <SelectTrigger aria-label="Trace status">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="OK">Healthy</SelectItem>
              <SelectItem value="ERROR">Flagged</SelectItem>
            </SelectContent>
          </Select>
        </div>
        {filtered.length ? (
          <TraceTable traces={filtered} onOpen={openTrace} />
        ) : (
          <div className="empty">
            No matching executions. Run an agent request or change your filters.
          </div>
        )}
      </Panel>
    );
  if (page === "evaluations")
    return (
      <>
        <div className="stats-grid six">
          {[
            "faithfulness",
            "answer_relevance",
            "context_precision",
            "context_recall",
            "citation_accuracy",
            "trajectory_efficiency",
          ].map((k) => (
            <Stat
              key={k}
              label={
                k === "faithfulness"
                  ? "Evidence overlap"
                  : k === "answer_relevance"
                    ? "Query overlap"
                    : k === "citation_accuracy"
                      ? "Citation ID validity"
                      : human(k)
              }
              value={pct(avg(k))}
              note={`${currentEvaluations.filter((e) => typeof e[k] === "number").length} evaluated · ${k.startsWith("context_") ? "labeled only" : "proxy / check"}`}
            />
          ))}
        </div>
        <div className="signal-strip">
          <ShieldCheck />
          <span>Know what your score means.</span>
          <small>
            Lexical scores do not measure correctness. Citation checks validate
            IDs, not claims.
          </small>
        </div>
        <div className="two-col">
          <Panel title="Quality distribution">
            <Bars
              data={Array.from({ length: 5 }, (_, i) => ({
                name: `${i * 20}–${(i + 1) * 20}%`,
                value: currentEvaluations.filter(
                  (e) =>
                    e.quality_score >= i / 5 &&
                    (i === 4
                      ? e.quality_score <= 1
                      : e.quality_score < (i + 1) / 5),
                ).length,
              }))}
            />
          </Panel>
          <Panel title="Evaluation coverage">
            <div className="coverage-row">
              <span>Deterministic checks</span>
              <b>
                {currentEvaluations.length} current ·{" "}
                {evaluations.length - currentEvaluations.length} legacy
              </b>
            </div>
            <div className="coverage-row">
              <span>Sampled judge completed</span>
              <b>
                {
                  currentEvaluations.filter(
                    (e) =>
                      e.judge.status === "completed" &&
                      e.judge.source !== "simulated_judge",
                  ).length
                }
              </b>
            </div>
            <div className="coverage-row">
              <span>Labeled retrieval examples</span>
              <b>
                {
                  currentEvaluations.filter(
                    (e) => typeof e.context_recall === "number",
                  ).length
                }
              </b>
            </div>
            <div className="coverage-row">
              <span>Judge unavailable</span>
              <b>
                {
                  evaluations.filter((e) => e.judge.status === "unavailable")
                    .length
                }
              </b>
            </div>
            <p className="dim small">
              Demo mode performs no LLM judgment. Legacy scores are excluded
              from these summaries. Live judge scores are model opinions, not
              ground truth.
            </p>
          </Panel>
        </div>
        <Panel title="Inspect evaluation evidence">
          <TraceTable traces={traces.slice(0, 8)} onOpen={openTrace} />
        </Panel>
      </>
    );
  if (page === "drift" && drift)
    return (
      <>
        <div className="drift-hero">
          <div
            className={`drift-gauge ${drift.status === "CRITICAL" ? "danger" : ""}`}
          >
            <strong>{drift.drift_score}</strong>
            <span>DRIFT SCORE</span>
          </div>
          <div>
            <Badge tone={drift.status === "NORMAL" ? "good" : "bad"}>
              {drift.status}
            </Badge>
            <h2>Baseline vs. recent traffic</h2>
            <p>
              {drift.baseline_count} baseline requests · {drift.recent_count}{" "}
              recent requests
            </p>
            <p className="dim small">{drift.explanation}</p>
            <Button
              variant="outline"
              disabled={!!busy}
              onClick={() =>
                void action("Generating 30 shifted requests", async () => {
                  await api("/drift/demo", {});
                })
              }
            >
              <Radar size={16} />
              Simulate traffic shift
            </Button>
          </div>
        </div>
        <Panel
          title="Distribution changes"
          extra={<Badge>{drift.embedding_source ?? "Collecting data"}</Badge>}
        >
          <Table>
            <TableHeader>
              <TableRow>
                {["Signal", "Baseline", "Recent", "Change", "Drift level"].map(
                  (h) => (
                    <TableHead key={h}>{h}</TableHead>
                  ),
                )}
              </TableRow>
            </TableHeader>
            <TableBody>
              {drift.metrics.map((m) => (
                <TableRow key={m.name}>
                  <TableCell>{human(m.name)}</TableCell>
                  <TableCell className="mono">
                    {m.baseline.toFixed(3)}
                  </TableCell>
                  <TableCell className="mono">{m.recent.toFixed(3)}</TableCell>
                  <TableCell>
                    {m.change_percent === null
                      ? "Centroid distance"
                      : `${m.change_percent > 0 ? "+" : ""}${m.change_percent.toFixed(1)}%`}
                  </TableCell>
                  <TableCell>
                    <Badge
                      tone={
                        m.status === "NORMAL"
                          ? "good"
                          : m.status === "WARNING"
                            ? "warn"
                            : "bad"
                      }
                    >
                      {m.status}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Panel>
      </>
    );
  if (page === "alerts")
    return (
      <div className="alert-grid">
        {alerts.map((a) => (
          <div
            className={`panel alert-panel ${a.active ? "active" : ""}`}
            key={a.id}
          >
            <Bell size={22} />
            <Badge tone={a.active ? "bad" : "good"}>
              {a.active ? "ACTIVE" : "RESOLVED"}
            </Badge>
            <h2>{a.title}</h2>
            <p>{a.evidence}</p>
            <Button
              variant="ghost"
              onClick={() => navigate(a.id === "drift" ? "drift" : "traces")}
            >
              Investigate <ArrowUpRight size={15} />
            </Button>
          </div>
        ))}
      </div>
    );
  return null;
}
