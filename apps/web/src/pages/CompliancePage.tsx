import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  type AuditEvent,
  type ChainVerification,
  type ComplianceStatusItem,
  type ScanProfile,
  downloadEvidenceJson,
  downloadEvidencePdf,
  fetchComplianceStatus,
  listAudit,
  listScanProfiles,
  verifyAudit,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useErrorMessage } from "../i18n/useErrorMessage";
import DocsLink from "../components/DocsLink";
import Pagination, { usePagination } from "../components/Pagination";
import SearchInput from "../components/SearchInput";
import { useToast } from "../components/Toast";
import { type Column, TableHead, processRows, useColumnFilters } from "../components/tableView";
import { useSort } from "../components/useSort";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

// The audit log is browsed client-side (search, per-column filters, page size);
// load the most recent events up to this cap. Older events remain in the
// authoritative evidence export.
const AUDIT_CAP = 1000;

const CADENCE_BADGE: Record<string, string> = {
  compliant: "bg-emerald-900 text-emerald-300",
  due_soon: "bg-amber-900 text-amber-300",
  overdue: "bg-red-900 text-red-300",
  never: "bg-slate-700 text-slate-400",
};

const FRAMEWORK_LABEL: Record<string, string> = {
  pci: "PCI-DSS",
  hipaa: "HIPAA",
  soc2: "SOC 2",
  iso27001: "ISO 27001",
  nist: "NIST",
};

// A few audit actions read better with a hand-written phrase than the generic
// code-to-words fallback below.
const ACTION_LABELS: Record<string, string> = {
  "auth.login.success": "Login success",
  "auth.login.failed": "Login failed",
  "user.seeded_admin": "Initial admin created",
  "asset.pushed": "Assets pushed to inventory",
  "scan_run.ingested": "Scan results ingested",
  "task.jira_linked": "Task linked to Jira",
  "task.jira_synced": "Task synced to Jira",
};

// Words that must keep their canonical casing when a code is humanised.
const ACTION_ACRONYMS: Record<string, string> = {
  cve: "CVE",
  ip: "IP",
  vlan: "VLAN",
  jira: "Jira",
};

// Turn a machine action code like "auth.login.success" into a readable label
// ("Login success"). Everything stays derivable from the code, so a new action
// added on the server still renders sensibly without a frontend change.
function humanizeAction(action: string): string {
  const preset = ACTION_LABELS[action];
  if (preset) return preset;
  const words = action.replace(/[._]/g, " ").split(" ").filter(Boolean);
  return words
    .map((w, i) => {
      if (ACTION_ACRONYMS[w]) return ACTION_ACRONYMS[w];
      return i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w;
    })
    .join(" ");
}

function fmtVal(v: unknown): string {
  if (v === null || v === undefined) return "none";
  if (typeof v === "boolean") return v ? "true" : "false";
  return String(v);
}

function isOldNew(v: unknown): v is { old?: unknown; new?: unknown } {
  return typeof v === "object" && v !== null && ("old" in v || "new" in v);
}

// A readable summary of an audit event's payload: the subject and what changed
// (old -> new where the backend records it), falling back to the raw target
// reference when there is no payload. Powers the audit log's detail column.
function formatAuditDetails(e: AuditEvent): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(e.payload ?? {})) {
    if (v === null || v === undefined) continue;
    if (Array.isArray(v)) {
      if (v.length) parts.push(`${k}: ${v.map(fmtVal).join(", ")}`);
    } else if (isOldNew(v)) {
      parts.push(`${k}: ${fmtVal(v.old)} → ${fmtVal(v.new)}`);
    } else if (typeof v === "object") {
      for (const [fk, fv] of Object.entries(v as Record<string, unknown>)) {
        if (isOldNew(fv)) parts.push(`${fk}: ${fmtVal(fv.old)} → ${fmtVal(fv.new)}`);
        else parts.push(`${fk}: ${fmtVal(fv)}`);
      }
    } else {
      parts.push(`${k}: ${fmtVal(v)}`);
    }
  }
  const summary = parts.join(" · ");
  if (summary) return summary;
  return e.target_type ? `${e.target_type}:${(e.target_id ?? "").slice(0, 8)}` : "";
}

// The in-app page an audit event's target points at, so a reviewer can jump from
// "who touched what" straight to that record. null when the type has no page.
// Note: /users/:id is admin-only, so the caller gates that link on the role.
function targetHref(type: string | null, id: string | null): string | null {
  switch (type) {
    case "asset":
      return id ? `/assets/${id}` : "/assets";
    case "change_event":
      return id ? `/changes/${id}` : "/changes";
    case "scan_run":
      return id ? `/scans/${id}` : "/scans";
    case "scan_profile":
      return "/scans";
    case "agent":
      return id ? `/agents/${id}` : "/agents";
    case "vlan":
    case "ip_range":
      return "/vlans";
    case "task":
      return "/tasks";
    case "user":
      return id ? `/users/${id}` : "/users";
    default:
      return null;
  }
}

export default function CompliancePage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const errorMessage = useErrorMessage();
  const toast = useToast();
  // The user detail page (and so the actor/user-target links) is admin-only.
  const isAdmin = user?.role === "admin";

  // A localised label per audit action code, falling back to the code-derived
  // humanised form for any action not (yet) in the dictionary.
  const actionLabel = (action: string): string => {
    const key = `audit.action.${action.replace(/\./g, "_")}` as TKey;
    const label = t(key);
    return label === key ? humanizeAction(action) : label;
  };
  const [chain, setChain] = useState<ChainVerification | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [profiles, setProfiles] = useState<ScanProfile[]>([]);
  const [cadence, setCadence] = useState<ComplianceStatusItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const { sort: cadenceSort, toggleSort: cadenceToggle } = useSort();
  const { filters: cadenceFilters, setFilter: setCadenceFilter } = useColumnFilters();
  const cadenceColumns: Column<ComplianceStatusItem>[] = [
    { key: "profile", label: t("compliance.col.profile"), filter: "text", get: (c) => c.profile_name },
    {
      key: "framework",
      label: t("compliance.col.framework"),
      filter: Object.keys(FRAMEWORK_LABEL).map((f) => ({ value: f, label: FRAMEWORK_LABEL[f] })),
      get: (c) => c.framework,
    },
    { key: "required", label: t("compliance.col.required"), get: (c) => c.cadence_days },
    { key: "schedule", label: t("compliance.col.schedule"), get: (c) => (c.schedule_ok ? 1 : 0) },
    { key: "lastScan", label: t("compliance.col.lastScan"), get: (c) => c.last_scan_at },
    {
      key: "status",
      label: t("compliance.col.status"),
      filter: Object.keys(CADENCE_BADGE).map((s) => ({ value: s, label: t(`cadence.${s}` as TKey) })),
      get: (c) => c.status,
    },
    { key: "asv", label: t("compliance.col.asv"), sortable: false, get: () => null },
  ];
  const processedCadence = processRows(cadence, cadenceColumns, cadenceSort, cadenceFilters);
  const cadencePage = usePagination(processedCadence, 15);
  const onCadenceFilter = (key: string, v: string) => {
    setCadenceFilter(key, v);
    cadencePage.setPage(0);
  };

  const { sort: evidenceSort, toggleSort: evidenceToggle } = useSort();
  const { filters: evidenceFilters, setFilter: setEvidenceFilter } = useColumnFilters();
  const evidenceColumns: Column<ScanProfile>[] = [
    { key: "profile", label: t("compliance.col.profile"), filter: "text", get: (p) => p.name },
    {
      key: "targets",
      label: t("compliance.col.targets"),
      filter: "text",
      get: (p) => p.targets.join(", "),
    },
  ];
  const processedEvidence = processRows(profiles, evidenceColumns, evidenceSort, evidenceFilters);
  const evidencePage = usePagination(processedEvidence, 15);
  const onEvidenceFilter = (key: string, v: string) => {
    setEvidenceFilter(key, v);
    evidencePage.setPage(0);
  };

  // Audit log: same searchable/filterable/paginated table as the rest of the app.
  const { sort: auditSort, toggleSort: auditToggle } = useSort();
  const { filters: auditFilters, setFilter: setAuditFilter } = useColumnFilters();
  const [auditSearch, setAuditSearch] = useState("");
  const auditColumns: Column<AuditEvent>[] = [
    { key: "seq", label: t("compliance.col.seq"), get: (e) => e.seq },
    { key: "time", label: t("compliance.col.time"), filter: "text", get: (e) => e.created_at },
    {
      key: "actor",
      label: t("compliance.col.actor"),
      filter: "text",
      get: (e) => e.actor_email ?? t("compliance.system"),
    },
    { key: "action", label: t("compliance.col.action"), filter: "text", get: (e) => actionLabel(e.action) },
    {
      key: "target",
      label: t("compliance.col.target"),
      filter: "text",
      get: (e) => formatAuditDetails(e),
    },
  ];
  const processedAudit = processRows(events, auditColumns, auditSort, auditFilters, auditSearch);
  const auditPage = usePagination(processedAudit, 25);
  const onAuditFilter = (key: string, v: string) => {
    setAuditFilter(key, v);
    auditPage.setPage(0);
  };

  async function verify() {
    setError(null);
    try {
      setChain(await verifyAudit());
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function loadAudit() {
    setError(null);
    try {
      const res = await listAudit({ limit: AUDIT_CAP });
      setTotal(res.total);
      setEvents(res.events);
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  useEffect(() => {
    async function init() {
      await Promise.allSettled([
        verify(),
        loadAudit(),
        listScanProfiles()
          .then(setProfiles)
          .catch((e) => setError(errorMessage(e))),
        fetchComplianceStatus()
          .then(setCadence)
          .catch((e) => setError(errorMessage(e))),
      ]);
      setLoading(false);
    }
    void init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onDownload(fn: () => Promise<void>) {
    // Surface as a toast: the evidence table is far from the only inline error
    // slot, so a download failure would otherwise appear detached or unseen.
    try {
      await fn();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  return (
    <div className="space-y-8">
      {/* Scan cadence */}
      <section className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-200">{t("compliance.cadenceTitle")}</h2>
            <p className="text-sm text-slate-500">{t("compliance.cadenceSubtitle")}</p>
          </div>
          <DocsLink guide="compliance" />
        </div>
        {loading ? (
          <p className="text-sm text-slate-500">{t("common.loading")}</p>
        ) : cadence.length === 0 ? (
          <p className="text-sm text-slate-500">{t("compliance.noFrameworkProfiles")}</p>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-left text-sm">
              <TableHead
                columns={cadenceColumns}
                sort={cadenceSort}
                toggleSort={cadenceToggle}
                filters={cadenceFilters}
                setFilter={onCadenceFilter}
              />
              <tbody className="divide-y divide-slate-800">
                {processedCadence.length === 0 ? (
                  <tr>
                    <td className="px-4 py-6 text-center text-slate-500" colSpan={7}>
                      {t("common.noData")}
                    </td>
                  </tr>
                ) : (
                  cadencePage.slice.map((c) => (
                  <tr key={c.profile_id} className="bg-slate-950">
                    <td className="px-4 py-2 text-slate-100">{c.profile_name}</td>
                    <td className="px-4 py-2 text-slate-300">
                      {FRAMEWORK_LABEL[c.framework] ?? c.framework}
                    </td>
                    <td className="px-4 py-2 text-slate-400">
                      {t("compliance.everyDays", { days: c.cadence_days })}
                    </td>
                    <td className="px-4 py-2 text-xs">
                      {c.schedule_ok ? (
                        <span className="text-emerald-400">{t("compliance.scheduleOk")}</span>
                      ) : c.cron ? (
                        <span className="text-amber-400">
                          {t("compliance.scheduleSparse", { days: c.schedule_gap_days ?? 0 })}
                        </span>
                      ) : (
                        <span className="text-amber-400">{t("compliance.scheduleNone")}</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-400">
                      {c.last_scan_at
                        ? t("compliance.lastScanAgo", {
                            date: new Date(c.last_scan_at).toLocaleDateString(),
                            days: c.days_since ?? 0,
                          })
                        : t("compliance.never")}
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs ${CADENCE_BADGE[c.status] ?? CADENCE_BADGE.never}`}
                      >
                        {t(`cadence.${c.status}` as TKey)}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-xs">
                      {c.framework !== "pci" ? (
                        <span className="text-slate-600">-</span>
                      ) : c.asv_satisfied ? (
                        <span className="text-emerald-400">{t("compliance.asvExternal")}</span>
                      ) : (
                        <span className="text-amber-400">{t("compliance.asvInternal")}</span>
                      )}
                    </td>
                  </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
        <Pagination
          page={cadencePage.page}
          pageCount={cadencePage.pageCount}
          total={cadencePage.total}
          onPage={cadencePage.setPage}
          pageSize={cadencePage.pageSize}
          onPageSize={cadencePage.setPageSize}
        />
      </section>

      {/* Chain integrity */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-200">{t("compliance.chainTitle")}</h2>
          <button
            onClick={verify}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
          >
            {t("compliance.verify")}
          </button>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
          {chain === null ? (
            <span className="text-sm text-slate-400">{t("compliance.checking")}</span>
          ) : chain.ok ? (
            <div className="flex items-center gap-3">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-emerald-500" />
              <span className="text-sm text-emerald-400">{t("compliance.intact")}</span>
              <span className="text-sm text-slate-500">
                {t("compliance.intactDetail", { total: chain.total })}
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-red-500" />
              <span className="text-sm text-red-400">
                {t("compliance.broken", { seq: chain.broken_seq ?? 0 })}
              </span>
            </div>
          )}
        </div>
      </section>

      {/* Evidence export */}
      <section data-tour="evidence" className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-200">{t("compliance.evidenceTitle")}</h2>
        <p className="text-sm text-slate-500">{t("compliance.evidenceSubtitle")}</p>
        <div className="overflow-x-auto rounded-xl border border-slate-800">
          <table className="w-full text-left text-sm">
            <TableHead
              columns={evidenceColumns}
              sort={evidenceSort}
              toggleSort={evidenceToggle}
              filters={evidenceFilters}
              setFilter={onEvidenceFilter}
              trailing
            />
            <tbody className="divide-y divide-slate-800">
              {loading ? (
                <tr>
                  <td className="px-4 py-3 text-slate-500" colSpan={3}>
                    {t("common.loading")}
                  </td>
                </tr>
              ) : profiles.length === 0 ? (
                <tr>
                  <td className="px-4 py-3 text-slate-500" colSpan={3}>
                    {t("compliance.noProfiles")}
                  </td>
                </tr>
              ) : processedEvidence.length === 0 ? (
                <tr>
                  <td className="px-4 py-6 text-center text-slate-500" colSpan={3}>
                    {t("common.noData")}
                  </td>
                </tr>
              ) : (
                evidencePage.slice.map((p) => (
                  <tr key={p.id} className="bg-slate-950">
                    <td className="px-4 py-2 text-slate-100">{p.name}</td>
                    <td className="px-4 py-2 font-mono text-xs text-slate-400">
                      {p.targets.join(", ")}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <button
                        onClick={() => onDownload(() => downloadEvidenceJson(p.id, p.name))}
                        className="mr-3 text-xs font-medium text-sky-400 hover:text-sky-300"
                      >
                        {t("compliance.downloadJson")}
                      </button>
                      <button
                        onClick={() => onDownload(() => downloadEvidencePdf(p.id, p.name))}
                        className="text-xs font-medium text-emerald-400 hover:text-emerald-300"
                      >
                        {t("compliance.downloadPdf")}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <Pagination
          page={evidencePage.page}
          pageCount={evidencePage.pageCount}
          total={evidencePage.total}
          onPage={evidencePage.setPage}
          pageSize={evidencePage.pageSize}
          onPageSize={evidencePage.setPageSize}
        />
      </section>

      {/* Audit log */}
      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-slate-200">{t("compliance.auditTitle")}</h2>
          <SearchInput
            value={auditSearch}
            onChange={(v) => {
              setAuditSearch(v);
              auditPage.setPage(0);
            }}
          />
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        {total > events.length && (
          <p className="text-xs text-slate-500">
            {t("compliance.auditTruncated", { shown: events.length, total })}
          </p>
        )}

        <div className="overflow-x-auto rounded-xl border border-slate-800">
          <table className="w-full text-left text-sm">
            <TableHead
              columns={auditColumns}
              sort={auditSort}
              toggleSort={auditToggle}
              filters={auditFilters}
              setFilter={onAuditFilter}
            />
            <tbody className="divide-y divide-slate-800">
              {loading ? (
                <tr>
                  <td className="px-4 py-3 text-slate-500" colSpan={5}>
                    {t("common.loading")}
                  </td>
                </tr>
              ) : events.length === 0 ? (
                <tr>
                  <td className="px-4 py-3 text-slate-500" colSpan={5}>
                    {t("compliance.noAuditEvents")}
                  </td>
                </tr>
              ) : processedAudit.length === 0 ? (
                <tr>
                  <td className="px-4 py-6 text-center text-slate-500" colSpan={5}>
                    {t("common.noData")}
                  </td>
                </tr>
              ) : (
                auditPage.slice.map((e) => (
                  <tr key={e.seq} className="bg-slate-950">
                    <td className="px-4 py-2 font-mono text-slate-500">{e.seq}</td>
                    <td className="px-4 py-2 text-xs text-slate-400">
                      {new Date(e.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-slate-300">
                      {e.actor_email && e.actor_id && isAdmin ? (
                        <Link
                          to={`/users/${e.actor_id}`}
                          className="text-emerald-400 hover:text-emerald-300"
                        >
                          {e.actor_email}
                        </Link>
                      ) : (
                        (e.actor_email ?? t("compliance.system"))
                      )}
                    </td>
                    <td className="px-4 py-2 font-medium text-slate-100" title={e.action}>
                      {actionLabel(e.action)}
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-400">
                      {(() => {
                        const details = formatAuditDetails(e) || "-";
                        const href = targetHref(e.target_type, e.target_id);
                        const linkable = href && (e.target_type !== "user" || isAdmin);
                        return linkable ? (
                          <Link to={href} className="text-emerald-400 hover:text-emerald-300">
                            {details}
                          </Link>
                        ) : (
                          details
                        );
                      })()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <Pagination
          page={auditPage.page}
          pageCount={auditPage.pageCount}
          total={auditPage.total}
          onPage={auditPage.setPage}
          pageSize={auditPage.pageSize}
          onPageSize={auditPage.setPageSize}
        />
      </section>
    </div>
  );
}
