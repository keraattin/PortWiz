import { type FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ApiError,
  type Agent,
  type EnrolledAgent,
  enrollAgent,
  fetchSettings,
  listAgents,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import AgentDeployPanel from "../components/AgentDeployPanel";
import Button from "../components/Button";
import PageHeader from "../components/PageHeader";
import Pagination, { usePagination } from "../components/Pagination";
import { type Column, TableHead, processRows, useColumnFilters } from "../components/tableView";
import { useSort } from "../components/useSort";
import { useToast } from "../components/Toast";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

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

// A single status category per agent, for filtering and sorting.
function agentCategory(a: Agent, windowMs: number): string {
  if (!a.enabled) return "disabled";
  if (!a.last_seen_at) return "neverSeen";
  return Date.now() - new Date(a.last_seen_at).getTime() < windowMs ? "online" : "offline";
}

const STATUS_OPTIONS = ["online", "offline", "neverSeen", "disabled"] as const;

const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500";

export default function AgentsPage() {
  const { user } = useAuth();
  const toast = useToast();
  const { t } = useI18n();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";

  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [segment, setSegment] = useState("");
  const [enrolled, setEnrolled] = useState<EnrolledAgent | null>(null);
  const [copied, setCopied] = useState(false);
  const [onlineMs, setOnlineMs] = useState(DEFAULT_ONLINE_MS);
  const [pollSeconds, setPollSeconds] = useState(15);

  const { sort, toggleSort } = useSort();
  const { filters, setFilter } = useColumnFilters();
  const columns: Column<Agent>[] = [
    { key: "name", label: t("agents.col.name"), filter: "text", get: (a) => a.name },
    { key: "segment", label: t("agents.col.segment"), filter: "text", get: (a) => a.segment ?? "" },
    {
      key: "status",
      label: t("agents.col.status"),
      filter: STATUS_OPTIONS.map((s) => ({ value: s, label: t(`agents.status.${s}` as TKey) })),
      get: (a) => agentCategory(a, onlineMs),
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
    // Online cut-off and poll cadence are admin-tunable system settings.
    fetchSettings()
      .then((s) => {
        setOnlineMs(s.agent_online_seconds * 1000);
        setPollSeconds(s.agent_poll_seconds);
      })
      .catch(() => {
        /* keep the defaults if settings can't be read */
      });
  }, []);

  async function onEnroll(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setCopied(false);
    try {
      const result = await enrollAgent(name, segment || null);
      setEnrolled(result);
      setName("");
      setSegment("");
      toast.success(t("agents.enrolled"));
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title={t("agents.title")} subtitle={t("agents.subtitle")} />

      {enrolled && (
        <div className="space-y-2 rounded-xl border border-emerald-800 bg-emerald-950/40 p-4">
          <p className="text-sm text-emerald-300">
            {t("agents.enrolledNotice", { name: enrolled.name })}
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 overflow-x-auto rounded bg-slate-900 px-3 py-2 font-mono text-xs text-slate-200">
              {enrolled.token}
            </code>
            <button
              onClick={() => {
                void navigator.clipboard?.writeText(enrolled.token);
                setCopied(true);
              }}
              className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-500"
            >
              {copied ? t("agents.copied") : t("agents.copy")}
            </button>
            <button
              onClick={() => {
                setEnrolled(null);
                setCopied(false);
              }}
              className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 hover:bg-slate-800"
            >
              {t("agents.dismiss")}
            </button>
          </div>
          <AgentDeployPanel name={enrolled.name} token={enrolled.token} pollSeconds={pollSeconds} />
        </div>
      )}

      {isAdmin && (
        <form onSubmit={onEnroll} className="flex flex-wrap gap-3">
          <input
            className={`${inputClass} flex-1`}
            placeholder={t("agents.namePlaceholder")}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <input
            className={`${inputClass} sm:w-48`}
            placeholder={t("agents.segmentPlaceholder")}
            value={segment}
            onChange={(e) => setSegment(e.target.value)}
          />
          <Button type="submit" className="whitespace-nowrap">
            {t("agents.enroll")}
          </Button>
        </form>
      )}

      {error && <p className="text-sm text-red-400">{error}</p>}

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
            ) : agents.length === 0 ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={6}>
                  {t("agents.empty")}
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
                const status = agentStatus(a.last_seen_at, onlineMs);
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
                    <td className="px-4 py-2 text-xs text-slate-400">
                      {a.last_seen_at ? new Date(a.last_seen_at).toLocaleString() : "-"}
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-400">
                      {new Date(a.created_at).toLocaleString()}
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
    </div>
  );
}
