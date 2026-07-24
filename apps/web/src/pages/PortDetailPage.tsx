import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { type OpenPort, listOpenPorts } from "../api/client";
import { portInfo } from "../data/portInfo";
import { useErrorMessage } from "../i18n/useErrorMessage";
import EmptyState from "../components/EmptyState";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

const CRIT_BADGE: Record<string, string> = {
  critical: "bg-red-900 text-red-300",
  high: "bg-orange-900 text-orange-200",
  medium: "bg-amber-900 text-amber-300",
  low: "bg-slate-700 text-slate-300",
};

export default function PortDetailPage() {
  const { port: portParam = "" } = useParams();
  const port = Number.parseInt(portParam, 10);
  const { t } = useI18n();
  const errorMessage = useErrorMessage();
  const [rows, setRows] = useState<OpenPort[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      setLoading(true);
      try {
        setRows(Number.isNaN(port) ? [] : await listOpenPorts({ port }));
      } catch (e) {
        setError(errorMessage(e));
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [port]);

  const info = portInfo(port);
  // Fall back to a service name observed on the wire when the port is not in the
  // well-known reference.
  const service = info?.service ?? rows.find((r) => r.service)?.service ?? null;

  const back = (
    <Link to="/ports" className="text-sm text-slate-400 hover:text-slate-200">
      ← {t("portDetail.back")}
    </Link>
  );

  return (
    <div className="space-y-6">
      {back}

      <div className="flex flex-wrap items-center gap-3">
        <h1 className="font-mono text-2xl font-semibold text-slate-100">
          {t("portDetail.heading", { port })}
        </h1>
        {service && (
          <span className="rounded-full bg-sky-900 px-2 py-0.5 text-xs text-sky-300">{service}</span>
        )}
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
        <p className="text-sm font-medium text-slate-300">{t("portDetail.usedFor")}</p>
        <p className="mt-1 text-sm text-slate-400">{info ? info.description : t("portDetail.unknown")}</p>
      </div>

      <div>
        <p className="mb-2 text-sm font-medium text-slate-300">{t("portDetail.hosts")}</p>
        {error && <p className="text-sm text-red-400">{error}</p>}
        {loading ? (
          <div className="rounded-xl border border-slate-800 p-4 text-sm text-slate-500">
            {t("common.loading")}
          </div>
        ) : rows.length === 0 ? (
          <EmptyState icon="🔌" title={t("portDetail.noHosts")} />
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-900 text-xs uppercase text-slate-400">
                <tr>
                  <th className="px-4 py-2 font-medium">{t("ports.col.host")}</th>
                  <th className="px-4 py-2 font-medium">{t("ports.col.ip")}</th>
                  <th className="px-4 py-2 font-medium">{t("ports.col.protocol")}</th>
                  <th className="px-4 py-2 font-medium">{t("ports.col.service")}</th>
                  <th className="px-4 py-2 font-medium">{t("ports.col.version")}</th>
                  <th className="px-4 py-2 font-medium">{t("ports.col.seen")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {rows
                  .slice()
                  .sort((a, b) => a.ip.localeCompare(b.ip) || a.protocol.localeCompare(b.protocol))
                  .map((r) => (
                    <tr key={`${r.ip}-${r.protocol}`} className="bg-slate-950">
                      <td className="px-4 py-2 text-slate-100">
                        {r.hostname ?? <span className="text-slate-500">{t("ports.noHostname")}</span>}
                        {r.criticality && (
                          <span
                            className={`ml-2 rounded-full px-2 py-0.5 text-[10px] ${
                              CRIT_BADGE[r.criticality] ?? ""
                            }`}
                          >
                            {t(`crit.${r.criticality}` as TKey)}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2 font-mono text-slate-300">
                        {r.asset_id ? (
                          <Link
                            to={`/assets/${r.asset_id}`}
                            className="text-emerald-400 hover:text-emerald-300"
                          >
                            {r.ip}
                          </Link>
                        ) : (
                          r.ip
                        )}
                      </td>
                      <td className="px-4 py-2 uppercase text-slate-400">{r.protocol}</td>
                      <td className="px-4 py-2 text-slate-300">
                        {r.service || <span className="text-slate-600">-</span>}
                      </td>
                      <td className="px-4 py-2 text-slate-400">
                        {r.version || <span className="text-slate-600">-</span>}
                      </td>
                      <td className="px-4 py-2 text-xs text-slate-500">
                        {r.last_seen_open_at ? new Date(r.last_seen_open_at).toLocaleString() : "-"}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
