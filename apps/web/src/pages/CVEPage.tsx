import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ApiError,
  type CVEFinding,
  fetchCVEFindings,
  fetchSettings,
  recheckCVEs,
  summarizeCVEs,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import Button from "../components/Button";
import PageHeader from "../components/PageHeader";
import { useToast } from "../components/Toast";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

function errorMessage(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong";
}

const SEVERITIES = ["critical", "high", "medium", "low", "unknown"] as const;

const SEV_CLASS: Record<string, string> = {
  critical: "bg-red-900 text-red-200",
  high: "bg-orange-900 text-orange-200",
  medium: "bg-amber-900 text-amber-200",
  low: "bg-slate-700 text-slate-300",
  unknown: "bg-slate-800 text-slate-400",
};

export default function CVEPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const toast = useToast();
  const canWrite = user?.role === "admin" || user?.role === "operator";

  const [findings, setFindings] = useState<CVEFinding[]>([]);
  const [loading, setLoading] = useState(true);
  const [rechecking, setRechecking] = useState(false);
  const [configured, setConfigured] = useState(true);
  const [aiConfigured, setAiConfigured] = useState(false);
  const [severity, setSeverity] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [brief, setBrief] = useState<string | null>(null);
  const [briefing, setBriefing] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setFindings(await fetchCVEFindings(severity ? { severity } : undefined));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    fetchSettings()
      .then((s) => {
        setConfigured(s.cve_configured);
        setAiConfigured(s.ai_configured);
      })
      .catch(() => {
        /* leave configured=true; the recheck will surface a real error */
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [severity]);

  async function onRecheck() {
    setRechecking(true);
    try {
      const r = await recheckCVEs();
      toast.success(t("cve.rechecked", { checked: r.checked, findings: r.findings }));
      await load();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setRechecking(false);
    }
  }

  async function onSummarize() {
    setBriefing(true);
    try {
      const r = await summarizeCVEs();
      setBrief(r.count === 0 ? t("cve.aiBriefEmpty") : r.summary);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBriefing(false);
    }
  }

  const inputClass =
    "rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader title={t("cve.title")} subtitle={t("cve.subtitle")} />
        {canWrite && (
          <Button onClick={() => void onRecheck()} disabled={rechecking || !configured}>
            {rechecking ? t("cve.rechecking") : t("cve.recheck")}
          </Button>
        )}
      </div>

      {!configured && (
        <p className="rounded-xl border border-amber-800 bg-amber-950/40 p-4 text-sm text-amber-300">
          {t("cve.notConfigured")}{" "}
          <Link to="/settings" className="underline">
            {t("nav.settings")}
          </Link>
        </p>
      )}

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="flex items-center gap-3">
        <label className="text-xs text-slate-400">{t("cve.filterSeverity")}</label>
        <select className={inputClass} value={severity} onChange={(e) => setSeverity(e.target.value)}>
          <option value="">{t("cve.allSeverities")}</option>
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>
              {t(`severity.${s}` as TKey)}
            </option>
          ))}
        </select>
        {aiConfigured && (
          <Button
            variant="outline"
            className="ml-auto"
            onClick={() => void onSummarize()}
            disabled={briefing || findings.length === 0}
          >
            {briefing ? t("cve.aiBriefing") : t("cve.aiBrief")}
          </Button>
        )}
      </div>

      {brief !== null && (
        <div className="rounded-xl border border-sky-900 bg-sky-950/30 p-4">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-sky-300">{t("cve.aiBriefTitle")}</h3>
            <button
              className="text-xs text-slate-500 hover:text-slate-300"
              onClick={() => setBrief(null)}
            >
              {t("common.close")}
            </button>
          </div>
          <p className="whitespace-pre-wrap text-sm text-slate-200">{brief}</p>
          <p className="mt-3 text-xs text-slate-500">{t("cve.aiBriefNote")}</p>
        </div>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900 text-xs uppercase text-slate-400">
            <tr>
              <th className="px-4 py-2">{t("cve.col.host")}</th>
              <th className="px-4 py-2">{t("cve.col.service")}</th>
              <th className="px-4 py-2">{t("cve.col.cve")}</th>
              <th className="px-4 py-2">{t("cve.col.cvss")}</th>
              <th className="px-4 py-2">{t("cve.col.severity")}</th>
              <th className="px-4 py-2">{t("cve.col.summary")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {loading ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={6}>
                  {t("common.loading")}
                </td>
              </tr>
            ) : findings.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-center text-slate-500" colSpan={6}>
                  {t("cve.empty")}
                </td>
              </tr>
            ) : (
              findings.map((f) => (
                <tr key={f.id} className="bg-slate-950">
                  <td className="px-4 py-2 font-mono text-xs text-slate-200">
                    {f.ip}:{f.port}
                  </td>
                  <td className="px-4 py-2 text-slate-300">
                    {f.service ?? "-"}
                    {f.version ? <span className="text-slate-500"> {f.version}</span> : null}
                  </td>
                  <td className="px-4 py-2">
                    <a
                      href={f.url}
                      target="_blank"
                      rel="noreferrer"
                      className="font-mono text-xs text-emerald-400 hover:text-emerald-300"
                    >
                      {f.cve_id}
                    </a>
                  </td>
                  <td className="px-4 py-2 text-slate-200">{f.cvss ?? "-"}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${SEV_CLASS[f.severity] ?? SEV_CLASS.unknown}`}
                    >
                      {t(`severity.${f.severity}` as TKey)}
                    </span>
                  </td>
                  <td className="max-w-md px-4 py-2 text-xs text-slate-400">
                    <span className="line-clamp-2">{f.summary}</span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
