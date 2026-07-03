import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, type Agent, fetchSettings, listAgents } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import Button from "../components/Button";
import PageHeader from "../components/PageHeader";
import Pagination, { usePagination } from "../components/Pagination";
import { type Column, TableHead, processRows, useColumnFilters } from "../components/tableView";
import { useSort } from "../components/useSort";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";
import { absoluteTime, timeAgo } from "../i18n/relativeTime";

function errorMessage(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong";
}

// Default online cut-off until the admin-configured value loads from /settings.
const DEFAULT_ONLINE_MS = 2 * 60 * 1000;

// Returns the i18n key for the status label plus its badge classes.
function agentStatus(lastSeen: string | null, windowMs: number): { key: TKey; cls: string } {
  if (!lastSeen) return { key: "agents.status.neverSeen", cls: "bg-slate-700 text-slate-400" };
  const ageMs = Date.now() - new Date(lastSeen).getTime();
  if (ageMs < windowMs)
    return { key: "agents.status.online", cls: "bg-emerald-900 text-emerald-300" };
  return { key: "agents.status.offline", cls: "bg-red-900 text-red-300" };
}

// Effective online window for an agent: its override, else the global default.
function effWindow(a: Agent, globalMs: number): number {
  return a.online_seconds_override ? a.online_seconds_override * 1000 : globalMs;
}

// A single status category per agent, for filtering, sorting and the summary.
function agentCategory(a: Agent, windowMs: number): string {
  if (!a.enabled) return "disabled";
  if (!a.last_seen_at) return "neverSeen";
  return Date.now() - new Date(a.last_seen_at).getTime() < windowMs ? "online" : "offline";
}

const STATUS_OPTIONS = ["online", "offline", "neverSeen", "disabled"] as const;

// Summary strip config: category -> label key + accent.
const SUMMARY: { cat: string; key: TKey; accent: string }[] = [
  { cat: "online", key: "agents.status.online", accent: "text-emerald-400" },
  { cat: "offline", key: "agents.status.offline", accent: "text-red-400" },
  { cat: "neverSeen", key: "agents.status.neverSeen", accent: "text-slate-300" },
  { cat: "disabled", key: "agents.status.disabled", accent: "text-slate-400" },
];

export default function AgentsPage() {
  const { user } = useAuth();
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";

  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [onlineMs, setOnlineMs] = useState(DEFAULT_ONLINE_MS);

  const { sort, toggleSort } = useSort();
  const { filters, setFilter } = useColumnFilters();
  const columns: Column<Agent>[] = [
    { key: "name", label: t("agents.col.name"), filter: "text", get: (a) => a.name },
    { key: "segment", label: t("agents.col.segment"), filter: "text", get: (a) => a.segment ?? "" },
    {
      key: "status",
      label: t("agents.col.status"),
      filter: STATUS_OPTIONS.map((s) => ({ value: s, label: t(`agents.status.${s}` as TKey) })),
      get: (a) => agentCategory(a, effWindow(a, onlineMs)),
    },
    { key: "version", label: t("agents.col.version"), filter: "text", get: (a) => a.version ?? "" },
    { key: "lastSeen", label: t("agents.col.lastSeen"), get: (a) => a.last_seen_at },
    { key: "enrolledAt", label: t("agents.col.enrolledAt"), get: (a) => a.created_at },
  ];
  const agentRows = processRows(agents, columns, sort, filters);
  const agentsPage = usePagination(agentRows, 15);
  const onFilter = (key: string, v: string) => {
    setFilter(key, v);
    agentsPage.setPage(0);
  };

  const summary = useMemo(() => {
    const counts: Record<string, number> = { online: 0, offline: 0, neverSeen: 0, disabled: 0 };
    for (const a of agents) counts[agentCategory(a, effWindow(a, onlineMs))]++;
    return counts;
  }, [agents, onlineMs]);

  async function reload() {
    setLoading(true);
    try {
      setAgents(await listAgents());
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
    fetchSettings()
      .then((s) => setOnlineMs(s.agent_online_seconds * 1000))
      .catch(() => {
        /* keep the default window if settings can't be read */
      });
  }, []);

  const enrollButton = isAdmin && (
    <Button onClick={() => navigate("/agents/new")} className="whitespace-nowrap">
      + {t("agents.enroll")}
    </Button>
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader title={t("agents.title")} subtitle={t("agents.subtitle")} />
        {enrollButton}
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {agents.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {SUMMARY.map(({ cat, key, accent }) => (
            <div key={cat} className="rounded-xl border border-slate-800 bg-slate-900 p-4">
              <div className={`text-2xl font-semibold ${accent}`}>{summary[cat]}</div>
              <div className="mt-0.5 text-xs text-slate-400">{t(key)}</div>
            </div>
          ))}
        </div>
      )}

      {!loading && agents.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-700 bg-slate-900/40 p-10 text-center">
          <p className="text-lg font-medium text-slate-200">{t("agents.emptyTitle")}</p>
          <p className="mx-auto mt-2 max-w-md text-sm text-slate-400">{t("agents.emptyBody")}</p>
          {isAdmin && (
            <div className="mt-5 flex justify-center">
              <Button onClick={() => navigate("/agents/new")}>{t("agents.enrollCta")}</Button>
            </div>
          )}
        </div>
      ) : (
        <>
          <div className="overflow-hidden rounded-xl border border-slate-800">
            <table className="w-full text-left text-sm">
              <TableHead
                columns={columns}
                sort={sort}
                toggleSort={toggleSort}
                filters={filters}
                setFilter={onFilter}
              />
              <tbody className="divide-y divide-slate-800">
                {loading ? (
                  <tr>
                    <td className="px-4 py-3 text-slate-500" colSpan={6}>
                      {t("common.loading")}
                    </td>
                  </tr>
                ) : agentRows.length === 0 ? (
                  <tr>
                    <td className="px-4 py-6 text-center text-slate-500" colSpan={6}>
                      {t("common.noData")}
                    </td>
                  </tr>
                ) : (
                  agentsPage.slice.map((a) => {
                    const status = agentStatus(a.last_seen_at, effWindow(a, onlineMs));
                    return (
                      <tr
                        key={a.id}
                        onClick={() => navigate(`/agents/${a.id}`)}
                        className="cursor-pointer bg-slate-950 hover:bg-slate-900"
                      >
                        <td className="px-4 py-2 text-slate-100">{a.name}</td>
                        <td className="px-4 py-2 text-slate-300">
                          {a.segment ?? <span className="text-slate-600">{t("agents.any")}</span>}
                        </td>
                        <td className="px-4 py-2">
                          {a.enabled ? (
                            <span className={`rounded-full px-2 py-0.5 text-xs ${status.cls}`}>
                              {t(status.key)}
                            </span>
                          ) : (
                            <span className="rounded-full bg-slate-700 px-2 py-0.5 text-xs text-slate-400">
                              {t("agents.status.disabled")}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-2 text-xs text-slate-400">
                          {a.version ?? <span className="text-slate-600">-</span>}
                        </td>
                        <td
                          className="px-4 py-2 text-xs text-slate-400"
                          title={absoluteTime(a.last_seen_at)}
                        >
                          {timeAgo(a.last_seen_at, lang)}
                        </td>
                        <td
                          className="px-4 py-2 text-xs text-slate-400"
                          title={absoluteTime(a.created_at)}
                        >
                          {timeAgo(a.created_at, lang)}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
          <Pagination
            page={agentsPage.page}
            pageCount={agentsPage.pageCount}
            total={agentsPage.total}
            onPage={agentsPage.setPage}
          />
        </>
      )}
    </div>
  );
}
