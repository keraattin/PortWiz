import { type ReactNode, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ApiError,
  type DashboardCharts as Charts,
  type DashboardStats,
  fetchCharts,
  fetchHealth,
  fetchStats,
} from "../api/client";
import DashboardCharts from "../components/DashboardCharts";

function errorMessage(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong";
}

function Metric({
  to,
  label,
  value,
  accent,
}: {
  to: string;
  label: string;
  value: ReactNode;
  accent?: string;
}) {
  return (
    <Link
      to={to}
      className="rounded-xl border border-slate-800 bg-slate-900 p-5 transition hover:border-slate-700"
    >
      <div className={`text-3xl font-semibold ${accent ?? "text-slate-100"}`}>{value}</div>
      <div className="mt-1 text-sm text-slate-400">{label}</div>
    </Link>
  );
}

interface Step {
  label: string;
  done: boolean;
  to: string;
  cta: string;
  note?: string;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [charts, setCharts] = useState<Charts | null>(null);
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHealth()
      .then((h) => setApiHealthy(h.status === "ok"))
      .catch(() => setApiHealthy(false));
    fetchStats()
      .then(setStats)
      .catch((e) => setError(errorMessage(e)));
    fetchCharts()
      .then(setCharts)
      .catch((e) => setError(errorMessage(e)));
  }, []);

  const steps: Step[] = stats
    ? [
        { label: "Add a VLAN", done: stats.vlans > 0, to: "/vlans", cta: "VLANs" },
        { label: "Add assets to scan", done: stats.assets > 0, to: "/assets", cta: "Assets" },
        {
          label: "Enroll a scan agent",
          done: stats.agents_total > 0,
          to: "/agents",
          cta: "Agents",
          note:
            stats.agents_total > 0 && stats.agents_online === 0
              ? "enrolled, but none online"
              : undefined,
        },
        {
          label: "Create a scan profile and run it",
          done: stats.last_scan_at !== null,
          to: "/scans",
          cta: "Scans",
        },
        {
          label: "Review confirmed changes",
          done: stats.open_changes > 0,
          to: "/changes",
          cta: "Changes",
        },
      ]
    : [];

  return (
    <div className="space-y-8">
      <div className="flex items-center gap-3">
        <span
          className={`inline-block h-2.5 w-2.5 rounded-full ${
            apiHealthy === null ? "bg-slate-500" : apiHealthy ? "bg-emerald-500" : "bg-red-500"
          }`}
        />
        <span className="text-sm text-slate-400">
          API status:{" "}
          {apiHealthy === null ? "checking…" : apiHealthy ? "healthy" : "unreachable"}
        </span>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {stats && stats.pending_runs > 0 && stats.agents_online === 0 && (
        <div className="rounded-xl border border-amber-800 bg-amber-950/40 p-4 text-sm text-amber-300">
          {stats.pending_runs} scan run{stats.pending_runs === 1 ? "" : "s"} waiting, but no
          agent is online.{" "}
          <Link to="/agents" className="underline">
            Check your agents
          </Link>
          .
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <Metric to="/assets" label="Assets" value={stats?.assets ?? "…"} />
        <Metric to="/vlans" label="VLANs" value={stats?.vlans ?? "…"} />
        <Metric
          to="/agents"
          label="Agents online"
          value={stats ? `${stats.agents_online}/${stats.agents_total}` : "…"}
          accent={stats && stats.agents_online > 0 ? "text-emerald-400" : undefined}
        />
        <Metric
          to="/changes"
          label="Open changes"
          value={stats?.open_changes ?? "…"}
          accent={stats && stats.open_changes > 0 ? "text-amber-400" : undefined}
        />
        <Metric
          to="/tasks"
          label="Open tasks"
          value={stats?.open_tasks ?? "…"}
          accent={stats && stats.open_tasks > 0 ? "text-sky-400" : undefined}
        />
        <Metric to="/scans" label="Pending runs" value={stats?.pending_runs ?? "…"} />
      </div>

      {charts && <DashboardCharts data={charts} />}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-200">Getting started</h2>
        <p className="text-sm text-slate-500">
          Follow these steps to go from an empty install to confirmed change detection.
        </p>
        <ol className="space-y-2">
          {steps.map((s, i) => (
            <li
              key={s.to}
              className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-900 p-3"
            >
              <span
                className={`flex h-6 w-6 items-center justify-center rounded-full text-xs ${
                  s.done ? "bg-emerald-900 text-emerald-300" : "bg-slate-800 text-slate-400"
                }`}
              >
                {s.done ? "✓" : i + 1}
              </span>
              <span className="flex-1 text-sm text-slate-200">
                {s.label}
                {s.note && <span className="ml-2 text-xs text-amber-400">({s.note})</span>}
              </span>
              <Link to={s.to} className="text-xs font-medium text-emerald-400 hover:text-emerald-300">
                {s.cta} →
              </Link>
            </li>
          ))}
        </ol>
      </section>

      {stats?.last_scan_at && (
        <p className="text-xs text-slate-600">
          Last scan: {new Date(stats.last_scan_at).toLocaleString()}
        </p>
      )}
    </div>
  );
}
