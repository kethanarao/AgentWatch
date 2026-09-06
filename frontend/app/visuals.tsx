import type { ReactNode } from "react";
import {
  AreaChart,
  Area,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  BarChart,
  Bar,
  Cell,
} from "recharts";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Trace } from "./types";

export const pct = (n: number | null | undefined) =>
  n == null ? "—" : `${(n * 100).toFixed(1)}%`;
export const ms = (n: number) =>
  n >= 1000 ? `${(n / 1000).toFixed(2)}s` : `${Math.round(n)}ms`;
export const human = (s: string) => s.replaceAll("_", " ").toLowerCase();
export const date = (s: string) =>
  new Date(s).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function Panel({
  title,
  extra,
  children,
  className = "",
}: {
  title: string;
  extra?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-title">
        <h2>{title}</h2>
        {extra}
      </div>
      {children}
    </section>
  );
}
export function Stat({
  label,
  value,
  note,
  tone = "",
}: {
  label: string;
  value: ReactNode;
  note: string;
  tone?: string;
}) {
  return (
    <div className={`stat ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </div>
  );
}
const tooltipStyle = {
  background: "#192331",
  border: "1px solid #354358",
  borderRadius: 8,
  color: "#e8f0f8",
  fontSize: 13,
};
export function Trend({
  data,
  dataKey,
  color = "#75edbd",
  percent = false,
}: {
  data: Record<string, unknown>[];
  dataKey: string;
  color?: string;
  percent?: boolean;
}) {
  return (
    <div className="chart">
      <ResponsiveContainer
        width="100%"
        height="100%"
        minWidth={0}
        initialDimension={{ width: 400, height: 220 }}
      >
        <AreaChart
          data={data}
          margin={{ top: 12, right: 10, left: -18, bottom: 0 }}
        >
          <defs>
            <linearGradient id={`fill-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.24} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid
            stroke="#26313e"
            strokeDasharray="3 5"
            vertical={false}
          />
          <XAxis
            dataKey="time"
            tickFormatter={(v) => String(v).slice(11, 16)}
            stroke="#7789a1"
            tickLine={false}
            axisLine={false}
            fontSize={12}
            minTickGap={30}
          />
          <YAxis
            tickFormatter={(v) =>
              percent
                ? `${Math.round(Number(v) * 100)}%`
                : String(Math.round(Number(v)))
            }
            stroke="#7789a1"
            tickLine={false}
            axisLine={false}
            fontSize={12}
            domain={percent ? [0, 1] : ["auto", "auto"]}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(v) => (percent ? pct(Number(v)) : Number(v).toFixed(1))}
          />
          <Area
            type="monotone"
            dataKey={dataKey}
            stroke={color}
            strokeWidth={2.5}
            fill={`url(#fill-${dataKey})`}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
export function Bars({ data }: { data: { name: string; value: number }[] }) {
  return (
    <div className="chart short">
      <ResponsiveContainer
        width="100%"
        height="100%"
        minWidth={0}
        initialDimension={{ width: 400, height: 175 }}
      >
        <BarChart data={data} layout="vertical" margin={{ left: 0, right: 20 }}>
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="name"
            width={135}
            tick={{ fill: "#a2b0c4", fontSize: 12 }}
            tickFormatter={human}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip contentStyle={tooltipStyle} />
          <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={16}>
            {data.map((d, i) => (
              <Cell
                key={d.name}
                fill={
                  ["#75edbd", "#74adfa", "#c299f7", "#f6b86a", "#ee819b"][i % 5]
                }
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
export function TraceTable({
  traces,
  onOpen,
}: {
  traces: Trace[];
  onOpen: (id: string) => void;
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          {[
            "Request / Trace ID",
            "Status",
            "Duration",
            "Evaluation",
            "Diagnosis",
            "Time",
          ].map((h) => (
            <TableHead key={h}>{h}</TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {traces.map((t) => (
          <TableRow key={t.trace_id}>
            <TableCell>
              <button className="trace-link" onClick={() => onOpen(t.trace_id)}>
                {t.query}
              </button>
              <div className="mono dim">{t.trace_id.slice(0, 16)}</div>
            </TableCell>
            <TableCell>
              <Badge tone={t.status === "OK" ? "good" : "bad"}>
                {t.status === "OK" ? "● Healthy" : "● Flagged"}
              </Badge>
            </TableCell>
            <TableCell className="mono">{ms(t.duration_ms)}</TableCell>
            <TableCell>
              <div className="score">
                <span>{pct(t.evaluation.quality_score)}</span>
                <i style={{ width: `${t.evaluation.quality_score * 58}px` }} />
              </div>
            </TableCell>
            <TableCell>
              <span className="diagnosis">
                {t.failures[0] ? human(t.failures[0].failure_category) : "—"}
              </span>
            </TableCell>
            <TableCell className="dim">{date(t.timestamp)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
