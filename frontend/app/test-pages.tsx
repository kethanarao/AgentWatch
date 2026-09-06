import { useState } from "react";
import {
  ArrowUpRight,
  MessageSquare,
  Play,
  Search,
  ShieldCheck,
  Terminal,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "./api";
import { Badge, Panel, human, ms } from "./visuals";
import type { PageProps } from "./dashboard";
import type { Candidate, Trace } from "./types";

export function TestPages({
  page,
  data,
  busy,
  action,
  openTrace,
  setSelected,
}: PageProps) {
  const { scenarios, experiments, regressions, candidates } = data;
  const [query, setQuery] = useState(
    "Why is checkout-api returning 503 errors?",
  );
  const [chaos, setChaos] = useState("tool_timeout");
  const [result, setResult] = useState<Trace | null>(null);
  const regression = regressions[0],
    experiment = experiments[0];
  if (page === "experiments")
    return (
      <>
        <div className="experiment-config">
          <div>
            <Badge>A · BASELINE</Badge>
            <h2>Focused retrieval</h2>
            <p>
              Top-k <strong>3</strong> · Prompt v1
            </p>
          </div>
          <span className="vs">VS</span>
          <div>
            <Badge>B · CHALLENGER</Badge>
            <h2>Expanded context</h2>
            <p>
              Top-k <strong>5</strong> · Prompt v1
            </p>
          </div>
          <Button
            disabled={!!busy}
            onClick={() =>
              void action("Benchmarking both configurations", async () => {
                await api("/experiments/run", {});
              })
            }
          >
            <Play size={16} />
            Run experiment
          </Button>
        </div>
        {experiment ? (
          <Panel
            title={`Result: ${experiment.winner === "TIE" ? "No meaningful winner" : `Configuration ${experiment.winner} wins`}`}
            extra={<Badge tone="good">{experiment.cases} paired cases</Badge>}
          >
            <p className="dim small">{experiment.rationale}</p>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Metric</TableHead>
                  <TableHead>Config A · k=3</TableHead>
                  <TableHead>Config B · k=5</TableHead>
                  <TableHead>Difference</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Object.keys(experiment.a).map((k) => (
                  <TableRow key={k}>
                    <TableCell>{human(k)}</TableCell>
                    <TableCell className="mono">
                      {experiment.a[k]?.toFixed(3) ?? "—"}
                    </TableCell>
                    <TableCell className="mono">
                      {experiment.b[k]?.toFixed(3) ?? "—"}
                    </TableCell>
                    <TableCell>
                      {(experiment.b[k] - experiment.a[k]).toFixed(3)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Panel>
        ) : (
          <div className="empty">
            Run the paired benchmark to compare configurations.
          </div>
        )}
      </>
    );
  if (page === "chaos")
    return (
      <div className="chaos-layout">
        <div>
          <div className="chaos-intro">
            <Badge tone="warn">
              <Zap size={12} /> CHAOS LAB
            </Badge>
            <span>12 fault scenarios · isolated to one request</span>
          </div>
          <div className="scenario-grid">
            {scenarios.map((s) => (
              <button
                key={s.id}
                className={`scenario ${chaos === s.id ? "selected" : ""}`}
                onClick={() => setChaos(s.id)}
                aria-pressed={chaos === s.id}
              >
                <span className="scenario-icon">
                  {s.group === "tools" ? (
                    <Terminal />
                  ) : s.group === "retrieval" ? (
                    <Search />
                  ) : s.group === "safety" ? (
                    <ShieldCheck />
                  ) : (
                    <Zap />
                  )}
                </span>
                <span className="scenario-group">{s.group}</span>
                <h3>{s.name}</h3>
                <p>{s.description}</p>
                <span className="selection-dot" />
              </button>
            ))}
          </div>
        </div>
        <aside className="chaos-console">
          <div className="console-heading">
            <span className="dot" /> INJECTION CONSOLE
          </div>
          <h2>
            {scenarios.find((s) => s.id === chaos)?.name ?? "Tool timeout"}
          </h2>
          <p className="dim">
            {scenarios.find((s) => s.id === chaos)?.description}
          </p>
          <label htmlFor="chaos-query">Test request</label>
          <Textarea
            id="chaos-query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            maxLength={4000}
          />
          <div className="console-path">
            <span>01</span> Execute modified agent
            <br />
            <span>02</span> Capture spans & evaluate
            <br />
            <span>03</span> Diagnose & create candidate
          </div>
          <Button
            className="chaos-run"
            disabled={!!busy || query.trim().length < 3}
            onClick={() =>
              void action(
                "Injecting failure and collecting evidence",
                async () => {
                  setResult(
                    await api<Trace>("/chaos/run", { query, scenario: chaos }),
                  );
                },
              )
            }
          >
            <Zap size={17} />
            Inject failure
          </Button>
          <p className="small dim">
            This runs the actual demo pipeline. Tool and generation delays are
            measured.
          </p>
          {result && (
            <div className="chaos-outcome">
              <Badge tone={result.failures.length ? "bad" : "good"}>
                {result.failures.length ? "DETECTED" : "NO FAILURE DETECTED"}
              </Badge>
              <h3>
                {result.failures[0]?.failure_category ?? "Execution completed"}
              </h3>
              <p>{result.failures[0]?.evidence.join(" ")}</p>
              <div className="coverage-row">
                <span>Component</span>
                <b>{result.failures[0]?.likely_component ?? "SupportAgent"}</b>
              </div>
              <div className="coverage-row">
                <span>Duration</span>
                <b>{ms(result.duration_ms)}</b>
              </div>
              <Button variant="outline" onClick={() => setSelected(result)}>
                Inspect evidence <ArrowUpRight size={15} />
              </Button>
            </div>
          )}
        </aside>
      </div>
    );
  if (page === "regression")
    return (
      <>
        <div
          className={`gate-banner ${regression?.status === "PASS" ? "pass" : "blocked"}`}
        >
          <ShieldCheck size={38} />
          <div>
            <span>RELEASE READINESS</span>
            <h2>{regression?.status ?? "Run the golden dataset"}</h2>
            <p>
              {regression
                ? `${regression.passed} / ${regression.total} cases passed`
                : "60 labeled cases · deterministic CI mode"}
            </p>
          </div>
          <div className="gate-actions">
            <Button
              disabled={!!busy}
              onClick={() =>
                void action("Running golden regression suite", async () => {
                  await api("/regression/run", { degraded: false });
                })
              }
            >
              <Play size={15} />
              Run regression
            </Button>
            <Button
              variant="outline"
              disabled={!!busy}
              onClick={() =>
                void action("Testing degraded deployment gate", async () => {
                  await api("/regression/run", { degraded: true });
                })
              }
            >
              Test degraded release
            </Button>
          </div>
        </div>
        {regression && (
          <>
            {regression.reasons.length > 0 && (
              <div className="failure-card">
                {regression.reasons.map((r) => (
                  <p key={r}>{r}</p>
                ))}
              </div>
            )}
            <Panel title="Baseline comparison">
              <Table>
                <TableHeader>
                  <TableRow>
                    {["Metric", "Baseline", "Current", "Difference"].map(
                      (h) => (
                        <TableHead key={h}>{h}</TableHead>
                      ),
                    )}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {regression.comparisons.map((c) => (
                    <TableRow key={c.metric}>
                      <TableCell>{human(c.metric)}</TableCell>
                      <TableCell className="mono">
                        {c.baseline.toFixed(3)}
                      </TableCell>
                      <TableCell className="mono">
                        {c.current.toFixed(3)}
                      </TableCell>
                      <TableCell className="mono">
                        {c.difference > 0 ? "+" : ""}
                        {c.difference.toFixed(3)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Panel>
            <Panel title="Golden dataset results">
              <div className="case-grid">
                {regression.cases.map((c) => (
                  <div key={c.id} className="case">
                    <Badge tone={c.passed ? "good" : "bad"}>{c.id}</Badge>
                    <span>{c.query}</span>
                    <small>{c.passed ? "PASS" : "FAIL"}</small>
                  </div>
                ))}
              </div>
            </Panel>
          </>
        )}
      </>
    );
  if (page === "feedback")
    return (
      <>
        <div className="signal-strip">
          <MessageSquare />
          <span>
            {candidates.filter((c) => c.status === "pending").length} candidates
            awaiting review
          </span>
          <small>
            Approvals are staged for export. The golden dataset is never changed
            automatically.
          </small>
        </div>
        <Panel
          title="Production-derived regression candidates"
          extra={
            <Button
              variant="outline"
              onClick={() =>
                void action("Exporting approved candidates", async () => {
                  const data = await api<Candidate[]>("/candidates/export");
                  const url = URL.createObjectURL(
                    new Blob([JSON.stringify(data, null, 2)], {
                      type: "application/json",
                    }),
                  );
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = "approved-regression-candidates.json";
                  a.click();
                  URL.revokeObjectURL(url);
                })
              }
            >
              Export approved
            </Button>
          }
        >
          <Table>
            <TableHeader>
              <TableRow>
                {[
                  "Production request",
                  "Source",
                  "Review status",
                  "Actions",
                ].map((h) => (
                  <TableHead key={h}>{h}</TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {candidates.map((c) => (
                <TableRow key={c.id}>
                  <TableCell>
                    <button
                      className="trace-link"
                      onClick={() => openTrace(c.trace_id)}
                    >
                      {c.query}
                    </button>
                  </TableCell>
                  <TableCell>{human(c.source)}</TableCell>
                  <TableCell>
                    <Badge tone={c.status === "approved" ? "good" : "neutral"}>
                      {c.status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex-line">
                      <Button
                        variant="outline"
                        disabled={!!busy || c.status !== "pending"}
                        onClick={() =>
                          void action("Approving candidate", async () => {
                            await api(`/candidates/${c.id}/review`, {
                              status: "approved",
                            });
                          })
                        }
                      >
                        Approve
                      </Button>
                      <Button
                        variant="ghost"
                        disabled={!!busy || c.status !== "pending"}
                        onClick={() =>
                          void action("Rejecting candidate", async () => {
                            await api(`/candidates/${c.id}/review`, {
                              status: "rejected",
                            });
                          })
                        }
                      >
                        Reject
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {!candidates.length && (
            <div className="empty">
              No candidates yet. Inject a fault or submit negative feedback.
            </div>
          )}
        </Panel>
      </>
    );
  return null;
}
