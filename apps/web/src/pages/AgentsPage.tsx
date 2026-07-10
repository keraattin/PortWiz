import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  type Agent,
  type AgentStatus,
  type FleetSummary,
  fetchFleetSummary,
  listAgents,
} from "../api/client";
import { useErrorMessage } from "../i18n/useErrorMessage";
import { useAuth } from "../auth/AuthContext";
import Button from "../components/Button";
import PageHeader from "../components/PageHeader";
import Pagination, { usePagination } from "../components/Pagination";
import SearchInput from "../components/SearchInput";
import { type Column, TableHead, processRows, useColumnFilters } from "../components/tableView";
import { useSort } from "../components/useSort";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";
import { absoluteTime, timeAgo } from "../i18n/relativeTime";

// Server-computed status -> its i18n label key and badge/accent classes. The API
// returns "never"; the existing label key is "neverSeen".
const STATUS_META: Record<AgentStatus, { key: TKey; badge: string; accent: string }> = {
  online: {
    key: "agents.status.online",
    badge: "bg-emerald-900 text-emerald-300",
    accent: "text-emerald-400",
  },
  offline: { key: "agents.status.offline", badge: "bg-red-900 text-red-300", accent: "text-red-400" },
  never: {
    key: "agents.status.neverSeen",
    badge: "bg-slate-700 text-slate-400",
    accent: "text-slate-300",
  },
  disabled: {
    key: "agents.status.disabled",
    badge: "bg-slate-700 text-slate-400",
    accent: "text-slate-400",
  },
};

const STATUS_OPTIONS: AgentStatus[] = ["online", "offline", "never", "disabled"];

// The server computes status; fall back to "never" only if it is somehow absent.
function statusOf(a: Agent): AgentStatus {
  return a.status ?? "never";
}

export default function AgentsPage() {
  const { user } = useAuth();
  const { t, lang } = useI18n();
  const errorMessage = useErrorMessage();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";

  const [agents, setAgents] = useState<Agent[]>([]);
  const [fleet, setFleet] = useState<FleetSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const { sort, toggleSort } = useSort();
  const { filters, setFilter } = useColumnFilters();
  const [search, setSearch] = useState("");
  const columns: Column<Agent>[] = [
    { key: "name", label: t("agents.col.name"), filter: "text", get: (a) => a.name },
    { key: "segment", label: t("agents.col.segment"), filter: "text", get: (a) => a.segment ?? "" },
    {
      key: "status",
      label: t("agents.col.status"),
      filter: STATUS_OPTIONS.map((s) => ({ value: s, label: t(STATUS_META[s].key) })),
      get: (a) => statusOf(a),
    },
    { key: "version", label: t("agents.col.version"), filter: "text", get: (a) => a.version ?? "" },
    { key: "lastSeen", label: t("agents.col.lastSeen"), get: (a) => a.last_seen_at },
    { key: "enrolledAt", label: t("agents.col.enrolledAt"), get: (a) => a.created_at },
  ];
  const agentRows = processRows(agents, columns, sort, filters, search);
  const agentsPage = usePagination(agentRows, 15);
  const onFilter = (key: string, v: string) => {
    setFilter(key, v);
    agentsPage.setPage(0);
  };

  const summary = useMemo(() => {
    const counts: Record<AgentStatus, number> = { online: 0, offline: 0, never: 0, disabled: 0 };
    for (const a of agents) counts[statusOf(a)]++;
    return counts;
  }, [agents]);

  async function reload() {
    setLoading(true);
    try {
      const [ags, fl] = await Promise.all([
        listAgents(),
        fetchFleetSummary().catch(() => null), // coverage panel is best-effort
      ]);
      setAgents(ags);
      setFleet(fl);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
  }, []);

  const enrollButton = isAdmin && (
    <Button
      onClick={() => navigate("/agents/new")}
      data-tour="enroll-agent"
      className="whitespace-nowrap"
    >
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
          {STATUS_OPTIONS.map((s) => (
            <div key={s} className="rounded-xl border border-slate-800 bg-slate-900 p-4">
              <div className={`text-2xl font-semibold ${STATUS_META[s].accent}`}>{summary[s]}</div>
              <div className="mt-0.5 text-xs text-slate-400">{t(STATUS_META[s].key)}</div>
            </div>
          ))}
        </div>
      )}

      {fleet && fleet.segments.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-slate-300">{t("agents.coverage.title")}</h2>
          {fleet.gaps.length > 0 && (
            <div className="rounded-xl border border-amber-800 bg-amber-950/40 p-3 text-sm text-amber-300">
              {t("agents.coverage.gapsBody", { count: fleet.gaps.length })}
            </div>
          )}
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-2 font-medium">{t("agents.coverage.col.segment")}</th>
                  <th className="px-4 py-2 font-medium">{t("agents.coverage.col.agents")}</th>
                  <th className="px-4 py-2 font-medium">{t("agents.coverage.col.profiles")}</th>
                  <th className="px-4 py-2 font-medium">{t("agents.coverage.col.status")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {fleet.segments.map((s) => (
                  <tr key={s.segment ?? "__none__"} className="bg-slate-950">
                    <td className="px-4 py-2 text-slate-200">
                      {s.segment ?? (
                        <span className="text-slate-500">{t("agents.coverage.unsegmented")}</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-slate-300">
                      {s.agents_online}/{s.agents_total}
                    </td>
                    <td className="px-4 py-2 text-slate-300">{s.profiles}</td>
                    <td className="px-4 py-2">
                      {s.covered ? (
                        <span className="rounded-full bg-emerald-900 px-2 py-0.5 text-xs text-emerald-300">
                          {t("agents.coverage.covered")}
                        </span>
                      ) : s.profiles > 0 ? (
                        <span className="rounded-full bg-amber-900 px-2 py-0.5 text-xs text-amber-300">
                          {t("agents.coverage.gap")}
                        </span>
                      ) : (
                        <span className="text-xs text-slate-600">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
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
          <div className="flex justify-end">
            <SearchInput value={search} onChange={setSearch} />
          </div>
          <div className="overflow-x-auto rounded-xl border border-slate-800">
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
                    const meta = STATUS_META[statusOf(a)];
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
                          <span className={`rounded-full px-2 py-0.5 text-xs ${meta.badge}`}>
                            {t(meta.key)}
                          </span>
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
            pageSize={agentsPage.pageSize}
            onPageSize={agentsPage.setPageSize}
          />
        </>
      )}
    </div>
  );
}
