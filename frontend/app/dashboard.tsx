import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  Bell,
  CheckCheck,
  ChevronRight,
  FlaskConical,
  GitBranch,
  LayoutDashboard,
  LoaderCircle,
  MessageSquare,
  Play,
  Radar,
  RefreshCw,
  Settings,
  ShieldCheck,
  Terminal,
  Zap,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { api } from "./api";
import { Badge } from "./visuals";
import { TraceDetail } from "./trace-detail";
import { ObservePages } from "./observe-pages";
import { TestPages } from "./test-pages";
import type {
  Alert,
  Candidate,
  Drift,
  Evaluation,
  Experiment,
  Overview,
  Regression,
  Scenario,
  Trace,
} from "./types";

const navigation = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "traces", label: "Trace explorer", icon: GitBranch },
  { id: "evaluations", label: "Evaluations", icon: ShieldCheck },
  { id: "drift", label: "Drift monitor", icon: Radar },
  { id: "experiments", label: "Experiments", icon: FlaskConical },
  { id: "chaos", label: "Chaos Lab", icon: Zap },
  { id: "regression", label: "Regression tests", icon: CheckCheck },
  { id: "feedback", label: "Review queue", icon: MessageSquare },
  { id: "alerts", label: "Alerts", icon: Bell },
];
const copy: Record<string, [string, string]> = {
  overview: [
    "Production overview",
    "Follow quality, investigate failures, and ship with evidence.",
  ],
  traces: [
    "Trace explorer",
    "Every decision, document, and tool call in one execution record.",
  ],
  evaluations: [
    "Evaluation intelligence",
    "Separate grounding, retrieval, safety, and execution quality.",
  ],
  drift: [
    "Traffic drift monitor",
    "Compare baseline behavior with the most recent request window.",
  ],
  experiments: [
    "Experiment workbench",
    "Compare retrieval configurations against the same 60 labeled cases.",
  ],
  chaos: [
    "Find the failure. Before your users do.",
    "Inject controlled faults and watch the reliability pipeline diagnose them.",
  ],
  regression: [
    "Deployment quality gate",
    "Make release decisions with a versioned dataset and explicit thresholds.",
  ],
  feedback: [
    "From failure to regression",
    "Review production-derived candidates before promoting them to your dataset.",
  ],
  alerts: [
    "Reliability alerts",
    "Actionable signals from latency, retrieval, citations, tools, and drift.",
  ],
};
const examples = [
  "Why is my Kubernetes pod in CrashLoopBackOff?",
  "Why is my API returning 503 errors?",
  "How can I debug high P95 latency in checkout-api?",
  "Why is my container failing its readiness probe?",
];
export type Data = {
  overview: Overview | null;
  traces: Trace[];
  evaluations: Evaluation[];
  drift: Drift | null;
  alerts: Alert[];
  scenarios: Scenario[];
  experiments: Experiment[];
  regressions: Regression[];
  candidates: Candidate[];
};
export type PageProps = {
  page: string;
  data: Data;
  busy: string;
  action: (label: string, fn: () => Promise<void>) => Promise<void>;
  openTrace: (id: string) => void;
  navigate: (id: string) => void;
  setSelected: (t: Trace) => void;
};

export default function Dashboard() {
  const [page, setPage] = useState("overview");
  const [data, setData] = useState<Data>({
    overview: null,
    traces: [],
    evaluations: [],
    drift: null,
    alerts: [],
    scenarios: [],
    experiments: [],
    regressions: [],
    candidates: [],
  });
  const [selected, setSelected] = useState<Trace | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [query, setQuery] = useState(examples[0]);
  const [chatOpen, setChatOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [connection, setConnection] = useState("Connecting");
  const [lastUpdated, setLastUpdated] = useState("");
  const refresh = useCallback(async () => {
    try {
      const [o, t, e, d, a, s, x, r, c] = await Promise.all([
        api<Overview>("/metrics/overview"),
        api<{ items: Trace[] }>("/traces?limit=1000"),
        api<Evaluation[]>("/evaluations"),
        api<Drift>("/drift"),
        api<Alert[]>("/alerts"),
        api<Scenario[]>("/chaos/scenarios"),
        api<Experiment[]>("/experiments"),
        api<Regression[]>("/regression"),
        api<Candidate[]>("/candidates"),
      ]);
      setData({
        overview: o,
        traces: t.items,
        evaluations: e,
        drift: d,
        alerts: a,
        scenarios: s,
        experiments: x,
        regressions: r,
        candidates: c,
      });
      setConnection("Connected");
      setLastUpdated(new Date().toLocaleTimeString());
      setError("");
    } catch (e) {
      setConnection("Offline");
      setError(
        e instanceof Error ? e.message : "Unable to connect to the API.",
      );
    }
  }, []);
  useEffect(() => {
    void refresh();
    const interval = setInterval(() => void refresh(), 15000);
    return () => clearInterval(interval);
  }, [refresh]);
  useEffect(() => {
    const apply = () => {
      const id = window.location.hash.slice(1);
      if (navigation.some((n) => n.id === id)) setPage(id);
    };
    apply();
    window.addEventListener("hashchange", apply);
    return () => window.removeEventListener("hashchange", apply);
  }, []);
  const navigate = (id: string) => {
    setPage(id);
    window.location.hash = id;
  };
  async function action(label: string, fn: () => Promise<void>) {
    setBusy(label);
    setError("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }
  const openTrace = (id: string) => {
    void action("Opening trace", async () =>
      setSelected(await api<Trace>(`/traces/${id}`)),
    );
  };
  async function runChat() {
    await action("Running support agent", async () => {
      const t = await api<Trace>("/chat", { query });
      setChatOpen(false);
      setSelected(t);
    });
  }
  // Optional WebMCP uses the same API and evidence panel as the visible request flow.
  useEffect(() => {
    type Context = {
      registerTool: (
        tool: {
          name: string;
          description: string;
          inputSchema: object;
          annotations: object;
          execute: (input: unknown) => Promise<unknown>;
        },
        options: { signal: AbortSignal },
      ) => void | Promise<void>;
    };
    const context = (document as Document & { modelContext?: Context })
      .modelContext;
    if (!context?.registerTool) return;
    const controller = new AbortController();
    void Promise.resolve(
      context.registerTool(
        {
          name: "run_support_request",
          description:
            "Run a support question and display its trace and evaluations.",
          inputSchema: {
            type: "object",
            properties: {
              query: { type: "string", minLength: 3, maxLength: 4000 },
            },
            required: ["query"],
            additionalProperties: false,
          },
          annotations: { readOnlyHint: false, untrustedContentHint: true },
          execute: async (input) => {
            if (
              typeof input !== "object" ||
              input === null ||
              !("query" in input) ||
              typeof input.query !== "string" ||
              input.query.length < 3 ||
              input.query.length > 4000
            )
              throw Error("query must contain 3–4000 characters");
            const t = await api<Trace>("/chat", { query: input.query });
            setSelected(t);
            await refresh();
            return {
              trace_id: t.trace_id,
              status: t.status,
              quality: t.evaluation.quality_score,
            };
          },
        },
        { signal: controller.signal },
      ),
    ).catch(() => {});
    return () => controller.abort();
  }, [refresh]);
  const props = { page, data, busy, action, openTrace, navigate, setSelected };
  return (
    <SidebarProvider>
      <Sidebar>
        <SidebarHeader>
          <div className="brand">
            <Activity />
            <strong>
              AgentWatch<span>RELIABILITY PLATFORM</span>
            </strong>
          </div>
          <div className="workspace-pill">
            <span className="workspace-icon">AW</span>
            <div>
              Support agent<small>Local workspace</small>
            </div>
            <ChevronRight size={16} />
          </div>
        </SidebarHeader>
        <SidebarContent>
          <div className="nav-label">OBSERVE & EVALUATE</div>
          <SidebarMenu>
            {navigation.map((n, i) => (
              <SidebarMenuItem key={n.id}>
                {i === 5 && (
                  <div className="nav-label inset">TEST & IMPROVE</div>
                )}
                <SidebarMenuButton
                  isActive={page === n.id}
                  onClick={() => navigate(n.id)}
                >
                  <n.icon />
                  <span>{n.label}</span>
                  {n.id === "chaos" && <span className="nav-tag">LAB</span>}
                  {n.id === "alerts" && !!data.overview?.active_alerts && (
                    <span className="alert-count">
                      {data.overview.active_alerts}
                    </span>
                  )}
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarContent>
        <SidebarFooter>
          <div className="local-card">
            <span
              className={`dot ${connection === "Connected" ? "" : "offline"}`}
            />{" "}
            {connection}
            <small>Ollama optional · no paid APIs</small>
          </div>
          <Button variant="ghost" onClick={() => setSettingsOpen(true)}>
            <Settings size={16} />
            Connection settings
          </Button>
          <a
            className="docs-link"
            href="/docs"
            target="_blank"
            rel="noreferrer"
          >
            API documentation <ArrowUpRight size={13} />
          </a>
        </SidebarFooter>
      </Sidebar>
      <main className="workspace">
        <div className="topbar">
          <div className="flex-line">
            <SidebarTrigger />
            <span>
              Workspace <span className="slash">/</span>{" "}
              <b>{navigation.find((n) => n.id === page)?.label}</b>
            </span>
          </div>
          <div className="flex-line">
            <Badge tone="good">
              ●{" "}
              {data.overview?.demo_mode === false
                ? "Local model"
                : "Demo environment"}
            </Badge>
            <button
              aria-label="Open alerts"
              className="icon-button"
              onClick={() => navigate("alerts")}
            >
              <Bell size={18} />
            </button>
            <div className="avatar">AW</div>
          </div>
        </div>
        <header className="page-heading">
          <div>
            <p className="eyebrow">
              {page === "chaos"
                ? "CONTROLLED FAULT INJECTION"
                : "AI RELIABILITY & EVALUATION CONTROL CENTER"}
            </p>
            <h1>{copy[page][0]}</h1>
            <p>{copy[page][1]}</p>
          </div>
          <div className="heading-actions">
            <Button
              variant="outline"
              disabled={!!busy}
              onClick={() => void refresh()}
              aria-label="Refresh dashboard"
            >
              <RefreshCw size={15} />
            </Button>
            <Button onClick={() => setChatOpen(true)}>
              <Terminal size={16} />
              Run agent <ChevronRight size={15} />
            </Button>
          </div>
        </header>
        {error && (
          <div className="error-banner" role="alert">
            {error}
            <Button variant="outline" onClick={() => void refresh()}>
              Retry
            </Button>
          </div>
        )}
        {busy && (
          <div className="busy-banner" role="status">
            <LoaderCircle className="spin" size={17} />
            {busy}…
          </div>
        )}
        <ObservePages {...props} />
        <TestPages {...props} />
        <footer className="page-footer">
          <span>
            <span className="dot" /> {connection} ·{" "}
            {lastUpdated ? `Updated ${lastUpdated}` : "Waiting for backend"}
          </span>
          <span>
            AgentWatch v1.0 <span className="slash">/</span> Free & local-first
          </span>
        </footer>
      </main>
      <TraceDetail
        trace={selected}
        onClose={() => setSelected(null)}
        onFeedback={() => void refresh()}
      />
      <Dialog open={chatOpen} onOpenChange={setChatOpen}>
        <DialogContent className="agent-dialog">
          <DialogHeader>
            <DialogTitle>Run the support agent</DialogTitle>
            <DialogDescription>
              Ask a DevOps question. Inspect the trace, evidence, and evaluation
              after execution.
            </DialogDescription>
          </DialogHeader>
          <label htmlFor="support-query">Support question</label>
          <Textarea
            id="support-query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            maxLength={4000}
          />
          <div className="example-list">
            {examples.map((q) => (
              <button key={q} onClick={() => setQuery(q)}>
                {q}
                <ChevronRight size={14} />
              </button>
            ))}
          </div>
          <Button
            disabled={!!busy || query.trim().length < 3}
            onClick={() => void runChat()}
          >
            {busy ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <Play size={16} />
            )}
            Run & trace
          </Button>
        </DialogContent>
      </Dialog>
      <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Connection settings</DialogTitle>
            <DialogDescription>
              Only needed if the backend has API_KEY configured. Stored for this
              browser session.
            </DialogDescription>
          </DialogHeader>
          <Input
            type="password"
            aria-label="Backend API key"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Optional API key"
          />
          <Button
            onClick={() => {
              sessionStorage.setItem("agentwatch-api-key", apiKey);
              setSettingsOpen(false);
              void refresh();
            }}
          >
            Save connection
          </Button>
        </DialogContent>
      </Dialog>
    </SidebarProvider>
  );
}
