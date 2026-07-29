import { type ReactNode, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  type ChangeEvent,
  type ChangeType,
  type Observation,
  type ScanProfile,
  type ScanRun,
  type ScanRunStatus,
  exportRunToJira,
  fetchSettings,
  getScanRun,
  listChanges,
  listRunObservations,
  listScanProfiles,
} from "../api/client";
import { useErrorMessage } from "../i18n/useErrorMessage";
import { useAuth } from "../auth/AuthContext";
import Button from "../components/Button";
import Pagination, { usePagination } from "../components/Pagination";
import SearchInput from "../components/SearchInput";
import { type Column, TableHead, processRows, useColumnFilters } from "../components/tableView";
import { useSort } from "../components/useSort";
import { useToast } from "../components/Toast";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

const STATUS_BADGE: Record<ScanRunStatus, string> = {
  pending: "bg-slate-700 text-slate-300",
  running: "bg-sky-900 text-sky-300",
  completed: "bg-emerald-900 text-emerald-300",
  partial: "bg-amber-900 text-amber-300",
  failed: "bg-red-900 text-red-300",
};

// Provenance of a service/version: agent nmap probe (most trusted), a
// deterministic server-side banner match, or an AI guess (treat with caution).
const SOURCE_CLASS: Record<string, string> = {
  agent: "bg-emerald-500/10 text-emerald-400",
  heuristic: "bg-sky-500/10 text-sky-400",
  ai: "bg-amber-500/10 text-amber-400",
};
const SOURCES = ["agent", "heuristic", "ai"];

const CHANGE_BADGE: Record<ChangeType, string> = {
  opened: "bg-sky-900 text-sky-300",
  closed: "bg-slate-700 text-slate-300",
  service_changed: "bg-amber-900 text-amber-300",
  version_changed: "bg-orange-900 text-orange-200",
};
const SEVERITY_BADGE: Record<string, string> = {
  high: "bg-red-900 text-red-300",
  medium: "bg-amber-900 text-amber-300",
  low: "bg-slate-700 text-slate-300",
};
const CHANGE_STATUS_BADGE: Record<string, string> = {
  open: "border border-sky-700 text-sky-300",
  acknowledged: "border border-amber-700 text-amber-300",
  resolved: "border border-emerald-700 text-emerald-300",
};

export default function ScanRunDetailPage() {
  const { runId = "" } = useParams();
  const { t } = useI18n();
  const { user } = useAuth();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const canWrite = user?.role === "admin" || user?.role === "operator";

  const [run, setRun] = useState<ScanRun | null>(null);
  const [profiles, setProfiles] = useState<ScanProfile[]>([]);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [changes, setChanges] = useState<ChangeEvent[]>([]);
  const [jiraConfigured, setJiraConfigured] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const { sort, toggleSort } = useSort();
  const { filters, setFilter } = useColumnFilters();
  const [search, setSearch] = useState("");

  async function load() {
    setLoading(true);
    try {
      const [r, obs, chg] = await Promise.all([
        getScanRun(runId),
        listRunObservations(runId),
        listChanges({ scan_run_id: runId }),
      ]);
      setRun(r);
      setObservations(obs);
      setChanges(chg);
      // Independent, best-effort lookups: a missing profile name or Jira status
      // must not blank out the whole page.
      listScanProfiles()
        .then(setProfiles)
        .catch(() => {});
      fetchSettings()
        .then((s) => setJiraConfigured(s.jira_configured))
        .catch(() => {});
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  async function onExport() {
    setExporting(true);
    try {
      const res = await exportRunToJira(runId);
      toast.success(
        t("scans.jiraExported", { exported: res.exported, linked: res.already_linked }),
      );
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setExporting(false);
    }
  }

  const columns: Column<Observation>[] = [
    { key: "host", label: t("scans.col.host"), filter: "text", get: (o) => o.ip },
    {
      key: "port",
      label: t("scans.col.port"),
      filter: "text",
      get: (o) => `${o.port}/${o.protocol}`,
    },
    { key: "state", label: t("scans.col.state"), filter: "text", get: (o) => o.state },
    { key: "service", label: t("scans.col.service"), filter: "text", get: (o) => o.service ?? "" },
    {
      key: "version",
      label: t("scans.col.version"),
      filter: "text",
      get: (o) => [o.product, o.version].filter(Boolean).join(" "),
    },
    {
      key: "source",
      label: t("scans.col.source"),
      filter: SOURCES.map((s) => ({ value: s, label: t(`fingerprint.${s}` as TKey) })),
      get: (o) => o.fingerprint_source ?? "",
    },
  ];
  const processed = processRows(observations, columns, sort, filters, search);
  const obsPage = usePagination(processed, 15);
  const onFilter = (key: string, v: string) => {
    setFilter(key, v);
    obsPage.setPage(0);
  };

  const profileName = (id: string | null) =>
    id ? (profiles.find((p) => p.id === id)?.name ?? id.slice(0, 8)) : "-";

  const back = (
    <Link to="/scans" className="text-sm text-slate-400 hover:text-slate-200">
      ← {t("scans.back")}
    </Link>
  );

  if (loading) {
    return (
      <div className="space-y-4">
        {back}
        <p className="text-sm text-slate-500">{t("common.loading")}</p>
      </div>
    );
  }
  if (!run) {
    return (
      <div className="space-y-4">
        {back}
        <p className="text-sm text-red-400">{error ?? t("scans.runNotFound")}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {back}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-2xl font-semibold text-slate-100">
            {t("scans.runDetailTitle")} {run.id.slice(0, 8)}
          </h1>
          <span className={`rounded-full px-2 py-0.5 text-xs ${STATUS_BADGE[run.status]}`}>
            {t(`runStatus.${run.status}` as TKey)}
          </span>
        </div>
        {canWrite && (
          <div className="flex flex-col items-end gap-1">
            <Button variant="outline" onClick={onExport} disabled={exporting || !jiraConfigured}>
              {exporting ? t("scans.exporting") : t("scans.exportJira")}
            </Button>
            {!jiraConfigured && (
              <span className="text-xs text-amber-400">{t("scans.jiraNotConfigured")}</span>
            )}
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4 rounded-xl border border-slate-800 bg-slate-900 p-5 sm:grid-cols-3">
        <Meta label={t("scans.col.profile")}>
          {run.scan_profile_id ? (
            <Link
              to="/scans"
              className="text-emerald-400 hover:text-emerald-300"
            >
              {profileName(run.scan_profile_id)}
            </Link>
          ) : (
            "-"
          )}
        </Meta>
        <Meta label={t("scans.meta.agent")}>{run.agent_id ?? "-"}</Meta>
        <Meta label={t("scans.meta.scanSource")}>{run.scan_source}</Meta>
        <Meta label={t("scans.col.started")}>
          {run.started_at ? new Date(run.started_at).toLocaleString() : "-"}
        </Meta>
        <Meta label={t("scans.col.finished")}>
          {run.finished_at ? new Date(run.finished_at).toLocaleString() : "-"}
        </Meta>
        <Meta label={t("scans.meta.created")}>{new Date(run.created_at).toLocaleString()}</Meta>
        {run.error && (
          <div className="col-span-2 sm:col-span-3">
            <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-slate-500">
              {t("scans.meta.error")}
            </p>
            <p className="text-sm text-red-400">{run.error}</p>
          </div>
        )}
      </div>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-medium text-slate-300">
            {t("scans.observationsTitle")} ({observations.length})
          </h2>
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
              {observations.length === 0 ? (
                <tr>
                  <td className="px-4 py-3 text-slate-500" colSpan={6}>
                    {t("scans.noOpenPorts")}
                  </td>
                </tr>
              ) : obsPage.slice.length === 0 ? (
                <tr>
                  <td className="px-4 py-6 text-center text-slate-500" colSpan={6}>
                    {t("common.noData")}
                  </td>
                </tr>
              ) : (
                obsPage.slice.map((o) => (
                  <tr key={o.id} className="bg-slate-950">
                    <td className="px-4 py-2 font-mono text-slate-100">{o.ip}</td>
                    <td className="px-4 py-2 text-slate-300">
                      {o.port}/{o.protocol}
                    </td>
                    <td className="px-4 py-2 text-emerald-400">{o.state}</td>
                    <td className="px-4 py-2 text-slate-300">{o.service ?? "-"}</td>
                    <td className="px-4 py-2 text-slate-400">
                      {[o.product, o.version].filter(Boolean).join(" ") || "-"}
                    </td>
                    <td className="px-4 py-2">
                      {o.fingerprint_source ? (
                        <span
                          className={`rounded px-2 py-0.5 text-xs ${
                            SOURCE_CLASS[o.fingerprint_source] ?? "bg-slate-700 text-slate-300"
                          }`}
                        >
                          {t(`fingerprint.${o.fingerprint_source}` as TKey)}
                        </span>
                      ) : (
                        <span className="text-slate-600">-</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <Pagination
          page={obsPage.page}
          pageCount={obsPage.pageCount}
          total={obsPage.total}
          onPage={obsPage.setPage}
          pageSize={obsPage.pageSize}
          onPageSize={obsPage.setPageSize}
        />
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-slate-300">
          {t("scans.changesTitle")} ({changes.length})
        </h2>
        {changes.length === 0 ? (
          <p className="rounded-xl border border-slate-800 bg-slate-900 p-6 text-center text-sm text-slate-600">
            {t("scans.noChanges")}
          </p>
        ) : (
          <ul className="divide-y divide-slate-800 rounded-xl border border-slate-800 bg-slate-900">
            {changes.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center gap-3 px-4 py-2">
                <Link
                  to={`/changes/${c.id}`}
                  className="font-mono text-sm text-emerald-400 hover:text-emerald-300"
                >
                  {c.ip}:{c.port}/{c.protocol}
                </Link>
                <span className={`rounded-full px-2 py-0.5 text-xs ${CHANGE_BADGE[c.change_type]}`}>
                  {t(`changeType.${c.change_type}` as TKey)}
                </span>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs ${
                    SEVERITY_BADGE[c.severity] ?? SEVERITY_BADGE.low
                  }`}
                >
                  {t(`severity.${c.severity}` as TKey)}
                </span>
                <span
                  className={`ml-auto rounded-full px-2 py-0.5 text-xs ${
                    CHANGE_STATUS_BADGE[c.status] ?? ""
                  }`}
                >
                  {t(`changeStatus.${c.status}` as TKey)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Meta({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="text-sm text-slate-200">{children}</p>
    </div>
  );
}
