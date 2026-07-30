import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  type Agent,
  type FleetSummary,
  type ScanProfile,
  fetchFleetSummary,
  listAgents,
  listScanProfiles,
} from "../api/client";
import { useErrorMessage } from "../i18n/useErrorMessage";
import EmptyState from "../components/EmptyState";
import PageHeader from "../components/PageHeader";
import { useI18n } from "../i18n/I18nContext";

// Match the agent status dots used on the Agents page.
const STATUS_DOT: Record<string, string> = {
  online: "bg-emerald-500",
  offline: "bg-slate-600",
  never: "bg-amber-500",
  disabled: "bg-red-500",
};

const segKey = (s: string | null) => s ?? "";

export default function SegmentsPage() {
  const { t } = useI18n();
  const errorMessage = useErrorMessage();
  const [fleet, setFleet] = useState<FleetSummary | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [profiles, setProfiles] = useState<ScanProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [f, a, p] = await Promise.all([
          fetchFleetSummary(),
          listAgents(),
          listScanProfiles(),
        ]);
        setFleet(f);
        setAgents(a);
        setProfiles(p);
      } catch (e) {
        setError(errorMessage(e));
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Group agents and profiles by the segment they belong to.
  const agentsBySeg: Record<string, Agent[]> = {};
  for (const a of agents) (agentsBySeg[segKey(a.segment)] ??= []).push(a);
  const profilesBySeg: Record<string, ScanProfile[]> = {};
  for (const p of profiles) (profilesBySeg[segKey(p.segment)] ??= []).push(p);

  const header = <PageHeader title={t("segments.title")} subtitle={t("segments.subtitle")} />;

  if (loading) {
    return (
      <div className="space-y-6">
        {header}
        <p className="text-sm text-slate-500">{t("common.loading")}</p>
      </div>
    );
  }

  const segments = fleet?.segments ?? [];

  return (
    <div className="space-y-6">
      {header}
      {error && <p className="text-sm text-red-400">{error}</p>}

      {segments.length === 0 ? (
        <EmptyState icon="🗂️" title={t("segments.empty")} body={t("segments.emptyBody")} />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {segments.map((seg) => {
            const k = segKey(seg.segment);
            const segAgents = agentsBySeg[k] ?? [];
            const segProfiles = profilesBySeg[k] ?? [];
            const isGap = seg.profiles > 0 && seg.agents_online === 0;
            const badge = seg.covered
              ? { cls: "bg-emerald-900 text-emerald-300", label: t("segments.covered") }
              : isGap
                ? { cls: "bg-red-900 text-red-300", label: t("segments.gap") }
                : { cls: "bg-slate-700 text-slate-300", label: t("segments.idle") };
            return (
              <div
                key={k || "__none__"}
                className="space-y-3 rounded-xl border border-slate-800 bg-slate-900 p-5"
              >
                <div className="flex flex-wrap items-center gap-3">
                  <h2 className="font-medium text-slate-100">
                    {seg.segment ?? t("segments.unsegmented")}
                  </h2>
                  <span className={`rounded-full px-2 py-0.5 text-xs ${badge.cls}`}>
                    {badge.label}
                  </span>
                </div>

                <div>
                  <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-slate-500">
                    {t("segments.agents")} ({seg.agents_online}/{seg.agents_total})
                  </p>
                  {segAgents.length === 0 ? (
                    <p className="text-xs text-slate-600">{t("segments.noAgents")}</p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {segAgents.map((a) => (
                        <Link
                          key={a.id}
                          to={`/agents/${a.id}`}
                          className="inline-flex items-center gap-1.5 rounded-full border border-slate-700 px-2 py-0.5 text-xs text-slate-200 hover:border-emerald-600"
                        >
                          <span
                            className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[a.status ?? "offline"] ?? "bg-slate-600"}`}
                          />
                          {a.name}
                        </Link>
                      ))}
                    </div>
                  )}
                </div>

                <div>
                  <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-slate-500">
                    {t("segments.profiles")} ({seg.profiles})
                  </p>
                  {segProfiles.length === 0 ? (
                    <p className="text-xs text-slate-600">{t("segments.noProfiles")}</p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {segProfiles.map((p) => (
                        <Link
                          key={p.id}
                          to="/scans"
                          className="rounded-full border border-slate-700 px-2 py-0.5 text-xs text-slate-200 hover:border-emerald-600"
                        >
                          {p.name}
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
