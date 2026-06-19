import { useEffect, useState } from "react";
import {
  ApiError,
  type ChangeEvent,
  type ChangeStatus,
  type ChangeType,
  type PortSnapshot,
  listChanges,
  updateChangeStatus,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import Pagination, { usePagination } from "../components/Pagination";
import SearchInput from "../components/SearchInput";
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
  const [statusFilter, setStatusFilter] = useState<(typeof STATUS_FILTERS)[number]>("all");
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const q = query.trim().toLowerCase();
  const filteredChanges = q
    ? changes.filter((c) =>
        [c.ip, String(c.port), c.protocol, c.change_type, c.severity, c.status].some((v) =>
          v.toLowerCase().includes(q),
        ),
      )
    : changes;
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

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-200">{t("changes.title")}</h2>
        <div className="flex items-center gap-2">
          {STATUS_FILTERS.map((f) => (
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
        </div>
      </div>

      <p className="text-sm text-slate-500">{t("changes.subtitle")}</p>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {changes.length > 0 && (
        <div className="flex justify-end">
          <SearchInput
            value={query}
            onChange={(v) => {
              setQuery(v);
              changesPage.setPage(0);
            }}
          />
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900 text-slate-400">
            <tr>
              <th className="px-4 py-2 font-medium">{t("changes.col.detected")}</th>
              <th className="px-4 py-2 font-medium">{t("changes.col.host")}</th>
              <th className="px-4 py-2 font-medium">{t("changes.col.change")}</th>
              <th className="px-4 py-2 font-medium">{t("changes.col.beforeAfter")}</th>
              <th className="px-4 py-2 font-medium">{t("changes.col.severity")}</th>
              <th className="px-4 py-2 font-medium">{t("changes.col.status")}</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {changes.length === 0 ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={7}>
                  {t("changes.empty")}
                </td>
              </tr>
            ) : filteredChanges.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-center text-slate-500" colSpan={7}>
                  {t("common.noData")}
                </td>
              </tr>
            ) : (
              changesPage.slice.map((c) => (
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
              ))
            )}
          </tbody>
        </table>
      </div>
      <Pagination
        page={changesPage.page}
        pageCount={changesPage.pageCount}
        total={changesPage.total}
        onPage={changesPage.setPage}
      />
    </div>
  );
}
