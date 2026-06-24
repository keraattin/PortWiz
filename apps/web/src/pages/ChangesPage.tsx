import { useEffect, useState } from "react";
import {
  ApiError,
  type ChangeEvent,
  type ChangeStatus,
  type ChangeType,
  type PortSnapshot,
  type ScanProfile,
  listChanges,
  listScanProfiles,
  updateChangeStatus,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import FilterSelect from "../components/FilterSelect";
import PageHeader from "../components/PageHeader";
import Pagination, { usePagination } from "../components/Pagination";
import SearchInput from "../components/SearchInput";
import SortHeader from "../components/SortHeader";
import { sortRows, useSort } from "../components/useSort";
import { useToast } from "../components/Toast";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

function errorMessage(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong";
}

const CHANGE_BADGE: Record<ChangeType, string> = {
  opened: "bg-emerald-900 text-emerald-300",
  closed: "bg-red-900 text-red-300",
  service_changed: "bg-amber-900 text-amber-300",
  version_changed: "bg-sky-900 text-sky-300",
};

const SEVERITY_BADGE: Record<string, string> = {
  high: "bg-red-900 text-red-300",
  medium: "bg-amber-900 text-amber-300",
  low: "bg-slate-700 text-slate-300",
};

const STATUS_BADGE: Record<ChangeStatus, string> = {
  open: "bg-sky-900 text-sky-300",
  acknowledged: "bg-amber-900 text-amber-300",
  resolved: "bg-emerald-900 text-emerald-300",
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
  const canWrite = user?.role === "admin" || user?.role === "operator";
  const [changes, setChanges] = useState<ChangeEvent[]>([]);
  const [profiles, setProfiles] = useState<ScanProfile[]>([]);
  const [statusFilter, setStatusFilter] = useState<(typeof STATUS_FILTERS)[number]>("all");
  const [query, setQuery] = useState("");
  const [sevFilter, setSevFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [groupBy, setGroupBy] = useState<"none" | "host" | "scan">("none");
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const { sort, toggleSort } = useSort();
  const profileName = (id: string) =>
    profiles.find((p) => p.id === id)?.name ?? t("scans.deletedProfile");
  const q = query.trim().toLowerCase();
  const filteredChanges = sortRows(
    changes.filter((c) => {
      const matchesQuery =
        !q ||
        [c.ip, String(c.port), c.protocol, c.change_type, c.severity, c.status].some((v) =>
          v.toLowerCase().includes(q),
        );
      return (
        matchesQuery &&
        (!sevFilter || c.severity === sevFilter) &&
        (!typeFilter || c.change_type === typeFilter)
      );
    }),
    sort,
    (c, key) => {
      switch (key) {
        case "detected":
          return c.detected_at;
        case "host":
          return c.ip;
        case "change":
          return c.change_type;
        case "severity":
          return SEV_RANK[c.severity] ?? 0;
        case "status":
          return c.status;
        default:
          return null;
      }
    },
  );
  const changesPage = usePagination(filteredChanges, 15);

  async function reload(filter = statusFilter) {
    try {
      setChanges(await listChanges(filter === "all" ? undefined : { status: filter }));
    } catch (e) {
      setError(errorMessage(e));
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
          filteredChanges.reduce<Record<string, ChangeEvent[]>>((acc, c) => {
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
        <td className="px-4 py-2 text-xs text-slate-300">
          <span className="text-slate-500">{describe(c.before, t)}</span>
          <span className="px-1 text-slate-500">{t("changes.to")}</span>
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

      {error && <p className="text-sm text-red-400">{error}</p>}

      {changes.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2">
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
          <div className="flex flex-wrap items-center gap-2">
            <FilterSelect
              value={sevFilter}
              onChange={(v) => {
                setSevFilter(v);
                changesPage.setPage(0);
              }}
              options={SEVERITIES.map((s) => ({ value: s, label: t(`severity.${s}` as TKey) }))}
              allLabel={t("changes.col.severity")}
            />
            <FilterSelect
              value={typeFilter}
              onChange={(v) => {
                setTypeFilter(v);
                changesPage.setPage(0);
              }}
              options={CHANGE_TYPES.map((c) => ({ value: c, label: t(`changeType.${c}` as TKey) }))}
              allLabel={t("changes.col.change")}
            />
            <SearchInput
              value={query}
              onChange={(v) => {
                setQuery(v);
                changesPage.setPage(0);
              }}
            />
          </div>
        </div>
      )}

      {changes.length === 0 ? (
        <div className="rounded-xl border border-slate-800 p-4 text-sm text-slate-500">
          {t("changes.empty")}
        </div>
      ) : filteredChanges.length === 0 ? (
        <div className="rounded-xl border border-slate-800 p-4 text-center text-sm text-slate-500">
          {t("common.noData")}
        </div>
      ) : groupBy !== "none" ? (
        <div className="space-y-3">
          {groups.map(([key, items]) => (
            <div key={key} className="overflow-hidden rounded-xl border border-slate-800">
              <button
                onClick={() => toggleGroup(key)}
                className="flex w-full items-center justify-between bg-slate-900 px-4 py-2 text-left text-sm font-medium text-slate-200"
              >
                <span>
                  {key} <span className="text-slate-500">({items.length})</span>
                </span>
                <span className="text-slate-500">{collapsed.has(key) ? "▸" : "▾"}</span>
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
          <div className="overflow-hidden rounded-xl border border-slate-800">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-900 text-slate-400">
                <tr>
                  <SortHeader
                    label={t("changes.col.detected")}
                    sortKey="detected"
                    sort={sort}
                    onSort={toggleSort}
                  />
                  <SortHeader
                    label={t("changes.col.host")}
                    sortKey="host"
                    sort={sort}
                    onSort={toggleSort}
                  />
                  <SortHeader
                    label={t("changes.col.change")}
                    sortKey="change"
                    sort={sort}
                    onSort={toggleSort}
                  />
                  <th className="px-4 py-2 font-medium">{t("changes.col.beforeAfter")}</th>
                  <SortHeader
                    label={t("changes.col.severity")}
                    sortKey="severity"
                    sort={sort}
                    onSort={toggleSort}
                  />
                  <SortHeader
                    label={t("changes.col.status")}
                    sortKey="status"
                    sort={sort}
                    onSort={toggleSort}
                  />
                  <th className="px-4 py-2"></th>
                </tr>
              </thead>
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
          />
        </>
      )}
    </div>
  );
}
