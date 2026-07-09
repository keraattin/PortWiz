import { useEffect, useState } from "react";
import {
  type ChangeEvent,
  type ChangeStatus,
  type ChangeType,
  type PortSnapshot,
  type ScanProfile,
  listChanges,
  listScanProfiles,
  updateChangeStatus,
} from "../api/client";
import { useErrorMessage } from "../i18n/useErrorMessage";
import { useAuth } from "../auth/AuthContext";
import InfoCallout from "../components/InfoCallout";
import PageHeader from "../components/PageHeader";
import Pagination, { usePagination } from "../components/Pagination";
import SearchInput from "../components/SearchInput";
import { type Column, TableHead, processRows, useColumnFilters } from "../components/tableView";
import { useSort } from "../components/useSort";
import { useToast } from "../components/Toast";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

// Change type is a category, not a verdict: avoid green/red here so a new port
// ("opened") doesn't read as "success" to a non-technical reader. Severity
// carries the good/bad signal instead.
const CHANGE_BADGE: Record<ChangeType, string> = {
  opened: "bg-sky-900 text-sky-300",
  closed: "bg-slate-700 text-slate-300",
  service_changed: "bg-amber-900 text-amber-300",
  version_changed: "bg-orange-900 text-orange-200",
};

// Severity = filled badges (how bad).
const SEVERITY_BADGE: Record<string, string> = {
  high: "bg-red-900 text-red-300",
  medium: "bg-amber-900 text-amber-300",
  low: "bg-slate-700 text-slate-300",
};

// Status = outline pills (what stage) so it reads distinctly from severity.
const STATUS_BADGE: Record<ChangeStatus, string> = {
  open: "border border-sky-700 text-sky-300",
  acknowledged: "border border-amber-700 text-amber-300",
  resolved: "border border-emerald-700 text-emerald-300",
};

const STATUS_FILTERS = ["all", "open", "acknowledged", "resolved"] as const;
const CHANGE_TYPES: ChangeType[] = ["opened", "closed", "service_changed", "version_changed"];
const SEVERITIES = ["low", "medium", "high"] as const;
// Rank so severity sorts by impact, not alphabetically.
const SEV_RANK: Record<string, number> = { low: 0, medium: 1, high: 2 };

type Translate = (key: TKey, vars?: Record<string, string | number>) => string;

function describe(snapshot: PortSnapshot, t: Translate): string {
  if (snapshot.state !== "open") {
    return t("changes.closed");
  }
  const detail = [snapshot.service, snapshot.version].filter(Boolean).join(" ");
  return detail ? t("changes.openWith", { detail }) : t("changes.open");
}

export default function ChangesPage() {
  const { user } = useAuth();
  const toast = useToast();
  const { t } = useI18n();
  const errorMessage = useErrorMessage();
  const canWrite = user?.role === "admin" || user?.role === "operator";
  const [changes, setChanges] = useState<ChangeEvent[]>([]);
  const [profiles, setProfiles] = useState<ScanProfile[]>([]);
  const [statusFilter, setStatusFilter] = useState<(typeof STATUS_FILTERS)[number]>("all");
  const [groupBy, setGroupBy] = useState<"none" | "host" | "scan">("none");
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const { sort, toggleSort } = useSort();
  const { filters, setFilter } = useColumnFilters();
  const [search, setSearch] = useState("");
  const profileName = (id: string) =>
    profiles.find((p) => p.id === id)?.name ?? t("scans.deletedProfile");
  const columns: Column<ChangeEvent>[] = [
    { key: "detected", label: t("changes.col.detected"), get: (c) => c.detected_at },
    { key: "host", label: t("changes.col.host"), filter: "text", get: (c) => c.ip },
    {
      key: "change",
      label: t("changes.col.change"),
      filter: CHANGE_TYPES.map((c) => ({ value: c, label: t(`changeType.${c}` as TKey) })),
      get: (c) => c.change_type,
    },
    { key: "beforeAfter", label: t("changes.col.beforeAfter"), sortable: false, get: () => null },
    {
      key: "severity",
      label: t("changes.col.severity"),
      filter: SEVERITIES.map((s) => ({ value: s, label: t(`severity.${s}` as TKey) })),
      info: t("changes.severityInfo"),
      get: (c) => c.severity,
      rank: SEV_RANK,
    },
    { key: "status", label: t("changes.col.status"), get: (c) => c.status },
  ];
  const processed = processRows(changes, columns, sort, filters, search);
  const changesPage = usePagination(processed, 15);
  const onColFilter = (key: string, v: string) => {
    setFilter(key, v);
    changesPage.setPage(0);
  };

  async function reload(filter = statusFilter) {
    setLoading(true);
    try {
      setChanges(await listChanges(filter === "all" ? undefined : { status: filter }));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
    listScanProfiles()
      .then(setProfiles)
      .catch(() => {
        /* grouping by scan falls back to profile ids */
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onStatusChange(id: string, status: ChangeStatus) {
    try {
      await updateChangeStatus(id, status);
      toast.success(t("changes.marked", { status: t(`changeStatus.${status}` as TKey) }));
      await reload();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  function onFilter(filter: (typeof STATUS_FILTERS)[number]) {
    setStatusFilter(filter);
    changesPage.setPage(0);
    void reload(filter);
  }

  function toggleGroup(key: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const groups =
    groupBy === "none"
      ? []
      : Object.entries(
          processed.reduce<Record<string, ChangeEvent[]>>((acc, c) => {
            const key = groupBy === "host" ? c.ip : profileName(c.scan_profile_id);
            (acc[key] ??= []).push(c);
            return acc;
          }, {}),
        ).sort((a, b) => a[0].localeCompare(b[0]));

  function renderRow(c: ChangeEvent) {
    return (
      <tr key={c.id} className="bg-slate-950">
        <td className="px-4 py-2 text-xs text-slate-400">
          {new Date(c.detected_at).toLocaleString()}
        </td>
        <td className="px-4 py-2 font-mono text-slate-100">
          {c.ip}:{c.port}/{c.protocol}
        </td>
        <td className="px-4 py-2">
          <span className={`rounded-full px-2 py-0.5 text-xs ${CHANGE_BADGE[c.change_type]}`}>
            {t(`changeType.${c.change_type}` as TKey)}
          </span>
        </td>
        <td className="px-4 py-2 text-xs">
          <span className="text-slate-500">{t("changes.before")} </span>
          <span className="text-slate-400">{describe(c.before, t)}</span>
          <span className="px-1.5 text-slate-600">→</span>
          <span className="text-slate-500">{t("changes.after")} </span>
          <span className="text-slate-100">{describe(c.after, t)}</span>
        </td>
        <td className="px-4 py-2">
          <span className={`rounded-full px-2 py-0.5 text-xs ${SEVERITY_BADGE[c.severity] ?? SEVERITY_BADGE.low}`}>
            {t(`severity.${c.severity}` as TKey)}
          </span>
        </td>
        <td className="px-4 py-2">
          <span className={`rounded-full px-2 py-0.5 text-xs ${STATUS_BADGE[c.status]}`}>
            {t(`changeStatus.${c.status}` as TKey)}
          </span>
        </td>
        <td className="px-4 py-2 text-right">
          {canWrite && c.status !== "acknowledged" && (
            <button
              onClick={() => onStatusChange(c.id, "acknowledged")}
              className="mr-3 text-xs text-amber-400 hover:text-amber-300"
            >
              {t("changes.acknowledge")}
            </button>
          )}
          {canWrite && c.status !== "resolved" && (
            <button
              onClick={() => onStatusChange(c.id, "resolved")}
              className="text-xs text-emerald-400 hover:text-emerald-300"
            >
              {t("changes.resolve")}
            </button>
          )}
        </td>
      </tr>
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("changes.title")}
        actions={STATUS_FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => onFilter(f)}
            className={`rounded-lg px-3 py-1.5 text-sm capitalize ${
              statusFilter === f
                ? "bg-slate-800 text-emerald-400"
                : "text-slate-400 hover:bg-slate-900"
            }`}
          >
            {f === "all" ? t("filters.all") : t(`changeStatus.${f}` as TKey)}
          </button>
        ))}
      />

      <p className="text-sm text-slate-500">{t("changes.subtitle")}</p>

      <InfoCallout>{t("changes.info")}</InfoCallout>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {changes.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-slate-400">
            {t("changes.groupBy")}
            <select
              value={groupBy}
              onChange={(e) => setGroupBy(e.target.value as "none" | "host" | "scan")}
              className="rounded-lg border border-slate-700 bg-slate-800 px-2 py-1 text-sm text-slate-100 outline-none focus:border-emerald-500"
            >
              <option value="none">{t("changes.group.none")}</option>
              <option value="host">{t("changes.group.host")}</option>
              <option value="scan">{t("changes.group.scan")}</option>
            </select>
          </label>
          <div className="ml-auto">
            <SearchInput value={search} onChange={setSearch} />
          </div>
        </div>
      )}

      {loading ? (
        <div className="rounded-xl border border-slate-800 p-4 text-sm text-slate-500">
          {t("common.loading")}
        </div>
      ) : changes.length === 0 ? (
        <div className="rounded-xl border border-slate-800 p-4 text-sm text-slate-500">
          {t("changes.empty")}
        </div>
      ) : processed.length === 0 ? (
        <div className="rounded-xl border border-slate-800 p-4 text-center text-sm text-slate-500">
          {t("common.noData")}
        </div>
      ) : groupBy !== "none" ? (
        <div className="space-y-3">
          {groups.map(([key, items]) => (
            <div key={key} className="overflow-x-auto rounded-xl border border-slate-800">
              <button
                onClick={() => toggleGroup(key)}
                aria-expanded={!collapsed.has(key)}
                className="flex w-full items-center justify-between bg-slate-900 px-4 py-2 text-left text-sm font-medium text-slate-200"
              >
                <span>
                  {key} <span className="text-slate-500">({items.length})</span>
                </span>
                <span className="text-slate-500" aria-hidden="true">
                  {collapsed.has(key) ? "▸" : "▾"}
                </span>
              </button>
              {!collapsed.has(key) && (
                <table className="w-full text-left text-sm">
                  <tbody className="divide-y divide-slate-800">{items.map(renderRow)}</tbody>
                </table>
              )}
            </div>
          ))}
        </div>
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-left text-sm">
              <TableHead
                columns={columns}
                sort={sort}
                toggleSort={toggleSort}
                filters={filters}
                setFilter={onColFilter}
                trailing
              />
              <tbody className="divide-y divide-slate-800">
                {changesPage.slice.map(renderRow)}
              </tbody>
            </table>
          </div>
          <Pagination
            page={changesPage.page}
            pageCount={changesPage.pageCount}
            total={changesPage.total}
            onPage={changesPage.setPage}
            pageSize={changesPage.pageSize}
            onPageSize={changesPage.setPageSize}
          />
        </>
      )}
    </div>
  );
}
