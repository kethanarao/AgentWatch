import { useState } from "react";
import { ThumbsUp, ThumbsDown, FileText, Clock, GitBranch } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { Trace, Span } from "./types";
import { api } from "./api";
import { Badge, Panel, human, ms, pct } from "./visuals";

export function TraceDetail({
  trace,
  onClose,
  onFeedback,
}: {
  trace: Trace | null;
  onClose: () => void;
  onFeedback: () => void;
}) {
  const [selected, setSelected] = useState<Span | null>(null);
  const [reason, setReason] = useState("");
  const [comment, setComment] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  async function feedback(rating: "up" | "down") {
    if (!trace) return;
    setSending(true);
    try {
      await api("/feedback", {
        trace_id: trace.trace_id,
        rating,
        reason,
        comment,
      });
      setMessage("Feedback saved. Negative feedback enters the review queue.");
      onFeedback();
    } catch (e) {
      setMessage(String(e));
    } finally {
      setSending(false);
    }
  }
  const max = trace
    ? Math.max(...trace.spans.map((s) => s.offset_ms + s.duration_ms), 1)
    : 1;
  return (
    <Sheet
      open={!!trace}
      onOpenChange={(open) => {
        if (!open) {
          setSelected(null);
          setMessage("");
          onClose();
        }
      }}
    >
      <SheetContent className="trace-sheet">
        <SheetHeader>
          <SheetTitle>Trace inspection</SheetTitle>
          <SheetDescription>{trace?.trace_id}</SheetDescription>
        </SheetHeader>
        {trace && (
          <div className="detail-body">
            <div className="flex-line">
              <Badge tone={trace.status === "OK" ? "good" : "bad"}>
                {trace.status === "OK"
                  ? "Healthy execution"
                  : "Failure detected"}
              </Badge>
              <span className="mono dim">
                {ms(trace.duration_ms)} · {trace.model}
              </span>
            </div>
            <h2 className="trace-question">{trace.query}</h2>
            <Tabs defaultValue="waterfall">
              <TabsList>
                <TabsTrigger value="waterfall">Waterfall</TabsTrigger>
                <TabsTrigger value="evidence">Evidence</TabsTrigger>
                <TabsTrigger value="evaluation">Evaluation</TabsTrigger>
              </TabsList>
              <TabsContent value="waterfall">
                <Panel title="Execution timeline" extra={<Clock size={16} />}>
                  <div className="waterfall">
                    {trace.spans.map((s) => (
                      <button
                        key={s.span_id}
                        className={`span-row ${s.status === "ERROR" ? "span-error" : ""}`}
                        onClick={() => setSelected(s)}
                      >
                        <span style={{ paddingLeft: s.parent_id ? 12 : 0 }}>
                          {s.name}
                        </span>
                        <div className="span-track">
                          <i
                            style={{
                              marginLeft: `${(s.offset_ms / max) * 100}%`,
                              width: `${Math.max(0.8, (s.duration_ms / max) * 100)}%`,
                            }}
                          />
                        </div>
                        <small>{ms(s.duration_ms)}</small>
                      </button>
                    ))}
                  </div>
                  <p className="dim small">
                    Select a span to inspect its input and output. Total API
                    time: {ms(trace.request_latency_ms)} including{" "}
                    {ms(trace.evaluation_latency_ms)} evaluation.
                  </p>
                  {selected && (
                    <div className="span-inspect">
                      <b>{selected.name}</b>
                      <p>{selected.error}</p>
                      <pre>
                        {JSON.stringify(
                          {
                            input: selected.input,
                            output: selected.output_summary,
                            model: selected.model,
                            estimated_tokens: selected.token_estimate,
                          },
                          null,
                          2,
                        )}
                      </pre>
                    </div>
                  )}
                </Panel>
                <Panel title="Agent trajectory" extra={<GitBranch size={16} />}>
                  <p className="dim small">
                    {trace.evaluation.ground_truth_available
                      ? "LABELED EXPECTATION"
                      : "EXECUTION SHAPE (NOT GROUND TRUTH)"}
                  </p>
                  <div className="trajectory">
                    {trace.evaluation.expected.map((s, i) => (
                      <span key={i}>{human(s)}</span>
                    ))}
                  </div>
                  <p className="dim small">ACTUAL</p>
                  <div className="trajectory actual">
                    {trace.evaluation.actual.map((s, i) => (
                      <span key={i}>{human(s)}</span>
                    ))}
                  </div>
                  <p className="small dim">
                    Efficiency {pct(trace.evaluation.trajectory_efficiency)} ·{" "}
                    {trace.retry_count} retries
                  </p>
                </Panel>
              </TabsContent>
              <TabsContent value="evidence">
                <Panel title="Retrieved context" extra={<FileText size={16} />}>
                  {trace.retrieved_documents.length === 0 ? (
                    <p className="dim">No context was retrieved.</p>
                  ) : (
                    trace.retrieved_documents.map((d, i) => (
                      <details className="document" key={`${d.id}-${i}`}>
                        <summary>
                          <span className="mono mint">{d.id}</span> {d.title}
                          <Badge tone={d.stale ? "bad" : "neutral"}>
                            {d.stale
                              ? "Expired"
                              : `Similarity ${d.score.toFixed(3)}`}
                          </Badge>
                        </summary>
                        <p>{d.text}</p>
                      </details>
                    ))
                  )}
                </Panel>
                <Panel title="Tool calls">
                  {trace.tool_calls.length === 0 ? (
                    <p className="dim">This request did not require a tool.</p>
                  ) : (
                    trace.tool_calls.map((c) => (
                      <details className="document" key={c.id}>
                        <summary>
                          {human(c.name)}
                          <Badge tone={c.status === "OK" ? "good" : "bad"}>
                            {c.status} · {ms(c.duration_ms)}
                          </Badge>
                        </summary>
                        <pre>
                          {JSON.stringify(
                            c.result ?? { error: c.error },
                            null,
                            2,
                          )}
                        </pre>
                      </details>
                    ))
                  )}
                </Panel>
              </TabsContent>
              <TabsContent value="evaluation">
                <div className="metric-grid">
                  {[
                    "faithfulness",
                    "answer_relevance",
                    "context_precision",
                    "context_recall",
                    "citation_accuracy",
                    "trajectory_efficiency",
                  ].map((k) => (
                    <div className="mini-metric" key={k}>
                      <span>
                        {k === "faithfulness"
                          ? "Evidence overlap (proxy)"
                          : k === "answer_relevance"
                            ? "Query overlap (proxy)"
                            : k === "citation_accuracy"
                              ? "Citation ID validity"
                              : human(k)}
                      </span>
                      <strong>
                        {pct(trace.evaluation[k] as number | null)}
                      </strong>
                    </div>
                  ))}
                </div>
                <p className="dim small">
                  Evaluator{" "}
                  {String(trace.evaluation.evaluator_version ?? "legacy")}.
                  Overlap is not semantic correctness. Citation validity does
                  not establish claim support. Unlabeled retrieval and
                  tool-selection accuracy are not calculated.
                </p>
                <Panel title="Sampled judge">
                  <Badge>{trace.evaluation.judge.source}</Badge>
                  <pre>
                    {JSON.stringify(
                      trace.evaluation.judge.result ?? {
                        status: trace.evaluation.judge.status,
                        reason: trace.evaluation.judge.reason,
                      },
                      null,
                      2,
                    )}
                  </pre>
                </Panel>
                <div className="cost-note">
                  <b>
                    SIMULATED COST ${trace.tokens.simulated_cost.toFixed(6)}
                  </b>
                  <span>
                    {trace.tokens.input} input + {trace.tokens.output} output
                    tokens, estimated. Local inference has no API charge.
                  </span>
                </div>
              </TabsContent>
            </Tabs>
            {trace.failures.map((f, i) => (
              <div className="failure-card" key={i}>
                <div className="flex-line">
                  <b>{f.failure_category}</b>
                  <Badge tone="bad">{f.severity}</Badge>
                </div>
                <p>
                  {f.likely_component} · {f.evidence.join(" ")}
                </p>
                <small>{f.recommended_action}</small>
              </div>
            ))}
            <Panel title="Final response">
              <p className="dim small">
                {trace.demo_mode
                  ? "Deterministic runbook answer · no LLM generation"
                  : "LLM-generated answer"}{" "}
                · Tool data is simulated. Tool selection:{" "}
                {trace.execution_metadata?.tool_selection_source ??
                  "not needed / legacy"}
                .
              </p>
              <div className="answer">{trace.answer}</div>
            </Panel>
            <Panel title="Human review">
              <p className="dim small">
                Help turn production failures into reviewed regression
                candidates.
              </p>
              <div className="flex-line">
                <Select
                  value={reason}
                  onValueChange={(v) => setReason(v ?? "")}
                >
                  <SelectTrigger aria-label="Feedback reason">
                    <SelectValue placeholder="Optional reason" />
                  </SelectTrigger>
                  <SelectContent>
                    {[
                      "Incorrect",
                      "Hallucinated",
                      "Missing information",
                      "Wrong tool",
                      "Bad citation",
                      "Too slow",
                    ].map((r) => (
                      <SelectItem key={r} value={r}>
                        {r}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  variant="outline"
                  disabled={sending}
                  onClick={() => feedback("up")}
                >
                  <ThumbsUp size={16} />
                  Helpful
                </Button>
                <Button
                  variant="outline"
                  disabled={sending}
                  onClick={() => feedback("down")}
                >
                  <ThumbsDown size={16} />
                  Needs review
                </Button>
              </div>
              <Textarea
                aria-label="Feedback comment"
                placeholder="Optional context for the reviewer"
                value={comment}
                maxLength={1000}
                onChange={(e) => setComment(e.target.value)}
              />
              <p role="status" className="mint small">
                {message}
              </p>
            </Panel>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
