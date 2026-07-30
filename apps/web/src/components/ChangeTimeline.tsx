import { useState } from "react";
import { Link } from "react-router-dom";
import {
  type ChangeEvent,
  type ChangeStatus,
  type ChangeType,
  type PortSnapshot,
} from "../api/client";
import Pagination, { usePagination } from "./Pagination";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

// Mirrors the change-type badge colours used on the Changes page.
const CHANGE_BADGE: Record<ChangeType, string> = {
  opened: "bg-sky-900 text-sky-300",
  closed: "bg-slate-700 text-slate-300",
  service_changed: "bg-amber-900 text-amber-300",
  version_changed: "bg-orange-900 text-orange-200",
};

const CHANGE_DOT: Record<ChangeType, string> = {
  opened: "bg-sky-400",
  closed: "bg-slate-500",
  service_changed: "bg-amber-400",
  version_changed: "bg-orange-400",
};

// Status = outline pills, matching the Changes page.
const STATUS_BADGE: Record<string, string> = {
  open: "border border-sky-700 text-sky-300",
  acknowledged: "border border-amber-700 text-amber-300",
  resolved: "border border-emerald-700 text-emerald-300",
};

const CHANGE_TYPES: ChangeType[] = ["opened", "closed", "service_changed", "version_changed"];
const SEVERITIES = ["low", "medium", "high"] as const;
const STATUSES = ["open", "acknowledged", "resolved"] as const;

type Translate = (key: TKey, vars?: Record<string, string | number>) => string;

function describe(snapshot: PortSnapshot, t: Translate): string {
  if (snapshot.state !== "open") return t("changes.closed");
  const detail = [snapshot.service, snapshot.version].filter(Boolean).join(" ");
  return detail ? t("changes.openWith", { detail }) : t("changes.open");
}

/** A vertical timeline of confirmed change events, newest first. `context`
 * picks the per-event identifier: the port (on a host's page) or the host (on a
 * port's page). Events are expected already ordered by detected_at descending. */
export default function ChangeTimeline({
  events,
  context = "port",
  canWrite = false,
  onStatusChange,
}: {
  events: ChangeEvent[];
  context?: "port" | "host";
  canWrite?: boolean;
  onStatusChange?: (id: string, status: ChangeStatus) => void;
}) {
  const { t } = useI18n();
  const [typeFilter, setTypeFilter] = useState("");
  const [sevFilter, setSevFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const filtered = events.filter(
    (e) =>
      (!typeFilter || e.change_type === typeFilter) &&
      (!sevFilter || e.severity === sevFilter) &&
      (!statusFilter || e.status === statusFilter),
  );
  const page = usePagination(filtered, 10);
  const selectCls =
    "rounded-md border border-slate-700 bg-slate-800 px-2 py-1 text-xs text-slate-100 outline-none focus:border-emerald-500";

  if (events.length === 0) {
    return <p className="py-6 text-center text-sm text-slate-600">{t("timeline.empty")}</p>;
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <select
          value={typeFilter}
          onChange={(e) => {
            setTypeFilter(e.target.value);
            page.setPage(0);
          }}
          className={selectCls}
        >
          <option value="">{t("filters.all")}</option>
          {CHANGE_TYPES.map((ct) => (
            <option key={ct} value={ct}>
              {t(`changeType.${ct}` as TKey)}
            </option>
          ))}
        </select>
        <select
          value={sevFilter}
          onChange={(e) => {
            setSevFilter(e.target.value);
            page.setPage(0);
          }}
          className={selectCls}
        >
          <option value="">{t("filters.all")}</option>
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>
              {t(`severity.${s}` as TKey)}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            page.setPage(0);
          }}
          className={selectCls}
        >
          <option value="">{t("filters.all")}</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {t(`changeStatus.${s}` as TKey)}
            </option>
          ))}
        </select>
      </div>

      {filtered.length === 0 ? (
        <p className="py-6 text-center text-sm text-slate-600">{t("common.noData")}</p>
      ) : (
        <ol className="relative space-y-4 border-l border-slate-800 pl-5">
          {page.slice.map((e) => (
            <li key={e.id} className="relative">
              <span
                className={`absolute -left-[1.42rem] top-1.5 h-2.5 w-2.5 rounded-full ring-2 ring-slate-950 ${CHANGE_DOT[e.change_type]}`}
              />
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded-full px-2 py-0.5 text-xs ${CHANGE_BADGE[e.change_type]}`}>
                  {t(`changeType.${e.change_type}` as TKey)}
                </span>
                <span className="font-mono text-xs text-slate-300">
                  {context === "host" ? e.ip : `${e.port}/${e.protocol}`}
                </span>
                <span className={`rounded-full px-2 py-0.5 text-xs ${STATUS_BADGE[e.status] ?? ""}`}>
                  {t(`changeStatus.${e.status}` as TKey)}
                </span>
                <Link
                  to={`/changes/${e.id}`}
                  className="text-xs text-slate-500 hover:text-emerald-400"
                >
                  {new Date(e.detected_at).toLocaleString()}
                </Link>
              </div>
              <p className="mt-1 text-sm text-slate-400">
                {describe(e.before, t)} <span className="text-slate-600">→</span>{" "}
                {describe(e.after, t)}
              </p>
              {canWrite && onStatusChange && e.status !== "resolved" && (
                <div className="mt-1 flex gap-3">
                  {e.status !== "acknowledged" && (
                    <button
                      onClick={() => onStatusChange(e.id, "acknowledged")}
                      className="text-xs text-amber-400 hover:text-amber-300"
                    >
                      {t("changes.acknowledge")}
                    </button>
                  )}
                  <button
                    onClick={() => onStatusChange(e.id, "resolved")}
                    className="text-xs text-emerald-400 hover:text-emerald-300"
                  >
                    {t("changes.resolve")}
                  </button>
                </div>
              )}
            </li>
          ))}
        </ol>
      )}

      {filtered.length > 0 && (
        <Pagination
          page={page.page}
          pageCount={page.pageCount}
          total={page.total}
          onPage={page.setPage}
          pageSize={page.pageSize}
          onPageSize={page.setPageSize}
        />
      )}
    </div>
  );
}
