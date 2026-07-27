import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  type AuditEvent,
  type CVEFinding,
  type ChangeEvent,
  type ChangeStatus,
  type ChangeType,
  type PortSnapshot,
  fetchCVEFindings,
  getChange,
  listAudit,
  updateChangeStatus,
} from "../api/client";
import { useErrorMessage } from "../i18n/useErrorMessage";
import { useAuth } from "../auth/AuthContext";
import Button from "../components/Button";
import { useToast } from "../components/Toast";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

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
const STATUS_BADGE: Record<string, string> = {
  open: "border border-sky-700 text-sky-300",
  acknowledged: "border border-amber-700 text-amber-300",
  resolved: "border border-emerald-700 text-emerald-300",
};
const SEV_BADGE: Record<string, string> = {
  critical: "bg-red-900 text-red-300",
  high: "bg-orange-900 text-orange-200",
  medium: "bg-amber-900 text-amber-300",
  low: "bg-slate-700 text-slate-300",
  unknown: "bg-slate-700 text-slate-400",
};

type Translate = (key: TKey, vars?: Record<string, string | number>) => string;

function describe(s: PortSnapshot, t: Translate): string {
  if (s.state !== "open") return t("changes.closed");
  const detail = [s.service, s.version].filter(Boolean).join(" ");
  return detail ? t("changes.openWith", { detail }) : t("changes.open");
}

function auditLabel(action: string, t: Translate): string {
  const key = `audit.action.${action.replace(/\./g, "_")}` as TKey;
  const label = t(key);
  return label === key ? action : label;
}

export default function ChangeDetailPage() {
  const { id = "" } = useParams();
  const { t } = useI18n();
  const { user } = useAuth();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const canWrite = user?.role === "admin" || user?.role === "operator";
  const canReadAudit = user?.role === "admin" || user?.role === "auditor";

  const [change, setChange] = useState<ChangeEvent | null>(null);
  const [cves, setCves] = useState<CVEFinding[]>([]);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const c = await getChange(id);
      setChange(c);
      const findings = await fetchCVEFindings({ ip: c.ip });
      setCves(findings.filter((f) => f.port === c.port));
      if (canReadAudit) {
        const page = await listAudit({ target_type: "change_event", target_id: id });
        setAudit(page.events);
      }
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function onStatus(status: ChangeStatus) {
    if (!change) return;
    try {
      setChange(await updateChangeStatus(change.id, status));
      toast.success(t("changes.marked", { status: t(`changeStatus.${status}` as TKey) }));
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  const back = (
    <Link to="/changes" className="text-sm text-slate-400 hover:text-slate-200">
      ← {t("changeDetail.back")}
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
  if (!change) {
    return (
      <div className="space-y-4">
        {back}
        <p className="text-sm text-red-400">{error ?? t("changeDetail.notFound")}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {back}

      <div className="flex flex-wrap items-center gap-3">
        <h1 className="font-mono text-2xl font-semibold text-slate-100">
          {change.asset_id ? (
            <Link to={`/assets/${change.asset_id}`} className="text-emerald-400 hover:text-emerald-300">
              {change.ip}
            </Link>
          ) : (
            change.ip
          )}
          :
          <Link to={`/ports/${change.port}`} className="text-emerald-400 hover:text-emerald-300">
            {change.port}
          </Link>
          <span className="text-slate-500">/{change.protocol}</span>
        </h1>
        <span className={`rounded-full px-2 py-0.5 text-xs ${CHANGE_BADGE[change.change_type]}`}>
          {t(`changeType.${change.change_type}` as TKey)}
        </span>
        <span className={`rounded-full px-2 py-0.5 text-xs ${SEVERITY_BADGE[change.severity] ?? SEVERITY_BADGE.low}`}>
          {t(`severity.${change.severity}` as TKey)}
        </span>
        <span className={`rounded-full px-2 py-0.5 text-xs ${STATUS_BADGE[change.status] ?? ""}`}>
          {t(`changeStatus.${change.status}` as TKey)}
        </span>
      </div>
      <p className="text-xs text-slate-500">
        {t("changes.col.detected")}: {new Date(change.detected_at).toLocaleString()}
      </p>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-slate-500">
            {t("changes.before")}
          </p>
          <p className="text-sm text-slate-200">{describe(change.before, t)}</p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-slate-500">
            {t("changes.after")}
          </p>
          <p className="text-sm text-slate-200">{describe(change.after, t)}</p>
        </div>
      </div>

      {canWrite && change.status !== "resolved" && (
        <div className="flex gap-3">
          {change.status !== "acknowledged" && (
            <Button variant="outline" onClick={() => void onStatus("acknowledged")}>
              {t("changes.acknowledge")}
            </Button>
          )}
          <Button onClick={() => void onStatus("resolved")}>{t("changes.resolve")}</Button>
        </div>
      )}

      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
        <p className="mb-3 text-sm font-medium text-slate-300">{t("assetDetail.vulns")}</p>
        {cves.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-600">{t("assetDetail.noVulns")}</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-800">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2 font-medium">{t("cve.col.cve")}</th>
                  <th className="px-4 py-2 font-medium">{t("cve.col.cvss")}</th>
                  <th className="px-4 py-2 font-medium">{t("cve.col.severity")}</th>
                  <th className="px-4 py-2 font-medium">{t("cve.col.summary")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {cves
                  .slice()
                  .sort((a, b) => (b.cvss ?? 0) - (a.cvss ?? 0))
                  .map((c) => (
                    <tr key={c.id} className="bg-slate-950">
                      <td className="px-4 py-2">
                        <a
                          href={c.url}
                          target="_blank"
                          rel="noreferrer"
                          className="font-mono text-emerald-400 hover:text-emerald-300"
                        >
                          {c.cve_id}
                        </a>
                      </td>
                      <td className="px-4 py-2 text-slate-300">{c.cvss ?? "-"}</td>
                      <td className="px-4 py-2">
                        <span className={`rounded-full px-2 py-0.5 text-xs ${SEV_BADGE[c.severity] ?? ""}`}>
                          {c.severity}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-slate-400">{c.summary}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {canReadAudit && (
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <p className="mb-3 text-sm font-medium text-slate-300">{t("changeDetail.audit")}</p>
          {audit.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-600">{t("changeDetail.noAudit")}</p>
          ) : (
            <ol className="space-y-2 text-sm">
              {audit.map((a) => (
                <li key={a.seq} className="flex flex-wrap items-center gap-2 border-b border-slate-800/60 py-1">
                  <span className="text-slate-200">{auditLabel(a.action, t)}</span>
                  <span className="text-xs text-slate-500">{a.actor_email ?? "-"}</span>
                  <span className="ml-auto text-xs text-slate-500">
                    {new Date(a.created_at).toLocaleString()}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}
