import { type ReactNode, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  type DashboardCharts as Charts,
  type DashboardStats,
  type UpdateStatus,
  applyUpdate,
  fetchCharts,
  fetchHealth,
  fetchStats,
  fetchUpdateStatus,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useErrorMessage } from "../i18n/useErrorMessage";
import DashboardCharts from "../components/DashboardCharts";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";
import { absoluteTime, timeAgo } from "../i18n/relativeTime";

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
  labelKey: TKey;
  done: boolean;
  to: string;
  ctaKey: TKey;
  note?: TKey;
}

export default function DashboardPage() {
  const { t, lang } = useI18n();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const errorMessage = useErrorMessage();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [charts, setCharts] = useState<Charts | null>(null);
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null);
  const [update, setUpdate] = useState<UpdateStatus | null>(null);
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function startUpdate() {
    setApplying(true);
    applyUpdate()
      .then(() => setApplied(true))
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setApplying(false));
  }

  function load() {
    setError(null);
    fetchHealth()
      .then((h) => setApiHealthy(h.status === "ok"))
      .catch(() => setApiHealthy(false));
    fetchStats()
      .then(setStats)
      .catch((e) => setError(errorMessage(e)));
    fetchCharts()
      .then(setCharts)
      .catch((e) => setError(errorMessage(e)));
    if (isAdmin) {
      fetchUpdateStatus()
        .then(setUpdate)
        .catch(() => {
          /* update check is best-effort; never block the dashboard on it */
        });
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const steps: Step[] = stats
    ? [
        { labelKey: "dashboard.step.addVlan", done: stats.vlans > 0, to: "/vlans", ctaKey: "nav.vlans" },
        {
          labelKey: "dashboard.step.addAssets",
          done: stats.assets > 0,
          to: "/assets",
          ctaKey: "nav.assets",
        },
        {
          labelKey: "dashboard.step.enrollAgent",
          done: stats.agents_total > 0,
          to: "/agents",
          ctaKey: "nav.agents",
          note:
            stats.agents_total > 0 && stats.agents_online === 0
              ? "dashboard.enrolledNoneOnline"
              : undefined,
        },
        {
          // A scan has been set up once it has run or is at least queued.
          labelKey: "dashboard.step.createScan",
          done: stats.last_scan_at !== null || stats.pending_runs > 0,
          to: "/scans",
          ctaKey: "nav.scans",
        },
        {
          // "Caught up" when there are no open changes left to review; when
          // changes appear this flips to a call to action.
          labelKey: "dashboard.step.reviewChanges",
          done: stats.open_changes === 0,
          to: "/changes",
          ctaKey: "nav.changes",
          note: stats.open_changes > 0 ? "dashboard.changesToReview" : undefined,
        },
      ]
    : [];

  return (
    <div className="space-y-8">
      {update?.update_available && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-emerald-800 bg-emerald-950/40 p-4 text-sm text-emerald-200">
          <span>
            {applied
              ? t("update.inProgress")
              : t("update.available", { latest: update.latest ?? "", current: update.current })}
          </span>
          <div className="flex items-center gap-3">
            {update.url && (
              <a href={update.url} target="_blank" rel="noreferrer" className="underline">
                {t("update.whatsNew")}
              </a>
            )}
            {update.apply_available && !applied ? (
              <button
                onClick={startUpdate}
                disabled={applying}
                className="rounded-lg border border-emerald-700 bg-emerald-900/50 px-3 py-1 font-medium text-emerald-100 hover:bg-emerald-800/60 disabled:opacity-60"
              >
                {applying ? t("update.applying") : t("update.applyNow")}
              </button>
            ) : (
              !applied && (
                <Link to="/settings?tab=system" className="underline">
                  {t("update.howTo")}
                </Link>
              )
            )}
          </div>
        </div>
      )}
      <div className="flex items-center gap-3">
        <span
          className={`inline-block h-2.5 w-2.5 rounded-full ${
            apiHealthy === null ? "bg-slate-500" : apiHealthy ? "bg-emerald-500" : "bg-red-500"
          }`}
        />
        <span className="text-sm text-slate-400">
          {t("dashboard.apiStatus")}{" "}
          {apiHealthy === null
            ? t("dashboard.checking")
            : apiHealthy
              ? t("dashboard.healthy")
              : t("dashboard.unreachable")}
        </span>
      </div>

      {error && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
          <span>{error}</span>
          <button
            onClick={load}
            className="rounded-lg border border-red-800 px-3 py-1 text-red-200 hover:bg-red-900/40"
          >
            {t("common.retry")}
          </button>
        </div>
      )}

      {stats && stats.pending_runs > 0 && stats.agents_online === 0 && (
        <div className="rounded-xl border border-amber-800 bg-amber-950/40 p-4 text-sm text-amber-300">
          {t("dashboard.scanWaiting", { count: stats.pending_runs })}{" "}
          <Link to="/agents" className="underline">
            {t("dashboard.checkAgents")}
          </Link>
          .
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <Metric to="/assets" label={t("dashboard.metric.assets")} value={stats?.assets ?? "…"} />
        <Metric to="/vlans" label={t("dashboard.metric.vlans")} value={stats?.vlans ?? "…"} />
        <Metric
          to="/agents"
          label={t("dashboard.metric.agentsOnline")}
          value={stats ? `${stats.agents_online}/${stats.agents_total}` : "…"}
          accent={stats && stats.agents_online > 0 ? "text-emerald-400" : undefined}
        />
        <Metric
          to="/changes"
          label={t("dashboard.metric.openChanges")}
          value={stats?.open_changes ?? "…"}
          accent={stats && stats.open_changes > 0 ? "text-amber-400" : undefined}
        />
        <Metric
          to="/tasks"
          label={t("dashboard.metric.openTasks")}
          value={stats?.open_tasks ?? "…"}
          accent={stats && stats.open_tasks > 0 ? "text-sky-400" : undefined}
        />
        <Metric
          to="/scans"
          label={t("dashboard.metric.pendingRuns")}
          value={stats?.pending_runs ?? "…"}
        />
      </div>

      {stats && (
        <Link
          to="/agents"
          className="block rounded-xl border border-slate-800 bg-slate-900 p-5 transition hover:border-slate-700"
        >
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-medium text-slate-300">{t("dashboard.agentHealth")}</h2>
            <span className="text-xs text-slate-500">
              {t("dashboard.agentTotal", { count: stats.agents_total })}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {(
              [
                ["agents.status.online", stats.agents_online, "text-emerald-400"],
                ["agents.status.offline", stats.agents_offline, "text-red-400"],
                ["agents.status.neverSeen", stats.agents_never_seen, "text-slate-300"],
                ["agents.status.disabled", stats.agents_disabled, "text-slate-400"],
              ] as [TKey, number, string][]
            ).map(([label, value, accent]) => (
              <div key={label} className="rounded-lg border border-slate-800 bg-slate-950 p-3">
                <div className={`text-2xl font-semibold ${accent}`}>{value}</div>
                <div className="mt-0.5 text-xs text-slate-400">{t(label)}</div>
              </div>
            ))}
          </div>
        </Link>
      )}

      {charts && <DashboardCharts data={charts} />}

      <section data-tour="getting-started" className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-200">{t("dashboard.gettingStarted")}</h2>
        <p className="text-sm text-slate-500">{t("dashboard.gettingStartedHint")}</p>
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
                {t(s.labelKey)}
                {s.note && <span className="ml-2 text-xs text-amber-400">({t(s.note)})</span>}
              </span>
              <Link to={s.to} className="text-xs font-medium text-emerald-400 hover:text-emerald-300">
                {t(s.ctaKey)} →
              </Link>
            </li>
          ))}
        </ol>
      </section>

      {stats?.last_scan_at && (
        <p className="text-xs text-slate-600" title={absoluteTime(stats.last_scan_at)}>
          {t("dashboard.lastScan", { when: timeAgo(stats.last_scan_at, lang) })}
        </p>
      )}
    </div>
  );
}
