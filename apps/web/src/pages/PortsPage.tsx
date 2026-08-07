import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  type OpenPort,
  type Suppression,
  createSuppression,
  deleteSuppression,
  listOpenPorts,
  listSuppressions,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useErrorMessage } from "../i18n/useErrorMessage";
import EmptyState from "../components/EmptyState";
import InfoCallout from "../components/InfoCallout";
import PageHeader from "../components/PageHeader";
import SearchInput from "../components/SearchInput";
import { CHECKBOX_CLS } from "../components/tableView";
import { useToast } from "../components/Toast";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

const keyOf = (p: { ip: string; port: number; protocol: string }) =>
  `${p.ip}:${p.port}:${p.protocol}`;

const CRIT_BADGE: Record<string, string> = {
  critical: "bg-red-900 text-red-300",
  high: "bg-orange-900 text-orange-200",
  medium: "bg-amber-900 text-amber-300",
  low: "bg-slate-700 text-slate-300",
};

interface HostGroup {
  ip: string;
  hostname: string | null;
  criticality: string | null;
  ports: OpenPort[];
}

// One row per (ip, port, protocol) from the API, grouped by host so the page
// answers "what is open on this host" directly.
function groupByHost(rows: OpenPort[]): HostGroup[] {
  const map = new Map<string, HostGroup>();
  for (const r of rows) {
    let g = map.get(r.ip);
    if (!g) {
      g = { ip: r.ip, hostname: r.hostname, criticality: r.criticality, ports: [] };
      map.set(r.ip, g);
    }
    g.ports.push(r);
  }
  const groups = [...map.values()];
  for (const g of groups) {
    g.ports.sort((a, b) => a.port - b.port || a.protocol.localeCompare(b.protocol));
  }
  groups.sort((a, b) => a.ip.localeCompare(b.ip));
  return groups;
}

export default function PortsPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const canWrite = user?.role === "admin" || user?.role === "operator";
  const [ports, setPorts] = useState<OpenPort[]>([]);
  const [suppMap, setSuppMap] = useState<Map<string, string>>(new Map());
  const [showSuppressed, setShowSuppressed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  // Hosts collapsed by the user; empty means every host is expanded (the default).
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  async function fetchData() {
    setLoading(true);
    try {
      const [pr, supp] = await Promise.all([
        listOpenPorts({ include_suppressed: showSuppressed }),
        canWrite ? listSuppressions() : Promise.resolve([] as Suppression[]),
      ]);
      setPorts(pr);
      setSuppMap(new Map(supp.map((s) => [keyOf(s), s.id])));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showSuppressed]);

  async function markFP(p: OpenPort) {
    try {
      await createSuppression({ ip: p.ip, port: p.port, protocol: p.protocol });
      toast.success(t("ports.fp.marked", { port: p.port }));
      await fetchData();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  async function restore(p: OpenPort) {
    const id = suppMap.get(keyOf(p));
    if (!id) return;
    try {
      await deleteSuppression(id);
      toast.success(t("ports.fp.restored", { port: p.port }));
      await fetchData();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  const allGroups = useMemo(() => groupByHost(ports), [ports]);

  // Search matches a host (by ip/hostname) to keep all its ports, or narrows to
  // the ports that match (by number/service/version/protocol).
  const groups = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return allGroups;
    const hostHit = (g: HostGroup) =>
      g.ip.toLowerCase().includes(q) || (g.hostname ?? "").toLowerCase().includes(q);
    const portHit = (p: OpenPort) =>
      String(p.port).includes(q) ||
      (p.service ?? "").toLowerCase().includes(q) ||
      (p.version ?? "").toLowerCase().includes(q) ||
      p.protocol.toLowerCase().includes(q);
    return allGroups
      .map((g) => (hostHit(g) ? g : { ...g, ports: g.ports.filter(portHit) }))
      .filter((g) => g.ports.length > 0);
  }, [allGroups, search]);

  function toggle(ip: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(ip)) next.delete(ip);
      else next.add(ip);
      return next;
    });
  }
  const expandAll = () => setCollapsed(new Set());
  const collapseAll = () => setCollapsed(new Set(groups.map((g) => g.ip)));

  return (
    <div className="space-y-5">
      <PageHeader title={t("ports.title")} subtitle={t("ports.subtitle")} docsGuide="scanning" />
      <InfoCallout>{t("ports.info")}</InfoCallout>
      {error && <p className="text-sm text-red-400">{error}</p>}

      {!loading && (
        <div className="flex flex-wrap items-center gap-3">
          <SearchInput value={search} onChange={setSearch} />
          <label className="flex items-center gap-2 text-xs text-slate-400">
            <input
              type="checkbox"
              className={CHECKBOX_CLS}
              checked={showSuppressed}
              onChange={(e) => setShowSuppressed(e.target.checked)}
            />
            {t("ports.fp.show")}
          </label>
          {groups.length > 0 && (
            <div className="ml-auto flex gap-2 text-xs">
              <button
                onClick={expandAll}
                className="rounded-lg border border-slate-700 px-3 py-1.5 text-slate-300 hover:bg-slate-800"
              >
                {t("ports.expandAll")}
              </button>
              <button
                onClick={collapseAll}
                className="rounded-lg border border-slate-700 px-3 py-1.5 text-slate-300 hover:bg-slate-800"
              >
                {t("ports.collapseAll")}
              </button>
            </div>
          )}
        </div>
      )}

      {loading ? (
        <div className="rounded-xl border border-slate-800 p-4 text-sm text-slate-500">
          {t("common.loading")}
        </div>
      ) : ports.length === 0 ? (
        <EmptyState icon="🔌" title={t("ports.empty")} body={t("ports.emptyBody")} />
      ) : groups.length === 0 ? (
        <div className="rounded-xl border border-slate-800 p-4 text-center text-sm text-slate-500">
          {t("common.noData")}
        </div>
      ) : (
        <div className="space-y-3">
          {groups.map((g) => {
            const open = !collapsed.has(g.ip);
            return (
              <div key={g.ip} className="overflow-hidden rounded-xl border border-slate-800">
                <button
                  onClick={() => toggle(g.ip)}
                  className="flex w-full items-center gap-3 bg-slate-900 px-4 py-3 text-left hover:bg-slate-800/60"
                >
                  <span className="text-slate-500">{open ? "▾" : "▸"}</span>
                  <span className="font-medium text-slate-100">
                    {g.hostname ?? <span className="font-mono">{g.ip}</span>}
                  </span>
                  {g.hostname && <span className="font-mono text-xs text-slate-500">{g.ip}</span>}
                  {g.criticality && (
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] ${CRIT_BADGE[g.criticality] ?? ""}`}
                    >
                      {t(`crit.${g.criticality}` as TKey)}
                    </span>
                  )}
                  <span className="ml-auto text-xs text-slate-500">
                    {t("ports.openCount", { count: g.ports.length })}
                  </span>
                </button>
                {open && (
                  <div className="overflow-x-auto border-t border-slate-800">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-slate-950 text-xs uppercase text-slate-500">
                        <tr>
                          <th className="px-4 py-2 font-medium">{t("ports.col.port")}</th>
                          <th className="px-4 py-2 font-medium">{t("ports.col.protocol")}</th>
                          <th className="px-4 py-2 font-medium">{t("ports.col.service")}</th>
                          <th className="px-4 py-2 font-medium">{t("ports.col.version")}</th>
                          <th className="px-4 py-2 font-medium">{t("ports.col.seen")}</th>
                          {canWrite && (
                            <th className="px-4 py-2 font-medium">{t("ports.col.actions")}</th>
                          )}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800">
                        {g.ports.map((p) => (
                          <tr
                            key={`${p.port}-${p.protocol}`}
                            className={`bg-slate-950 ${p.suppressed ? "opacity-60" : ""}`}
                          >
                            <td className="px-4 py-2 font-mono">
                              <Link
                                to={`/ports/${p.port}`}
                                className="text-emerald-400 hover:text-emerald-300"
                              >
                                {p.port}
                              </Link>
                              {p.suppressed && (
                                <span className="ml-2 rounded-full bg-slate-700 px-2 py-0.5 text-[10px] uppercase text-slate-300">
                                  {t("ports.fp.badge")}
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-2 uppercase text-slate-400">{p.protocol}</td>
                            <td className="px-4 py-2 text-slate-300">
                              {p.service || <span className="text-slate-600">-</span>}
                            </td>
                            <td className="px-4 py-2 text-slate-400">
                              {p.version || <span className="text-slate-600">-</span>}
                            </td>
                            <td className="px-4 py-2 text-xs text-slate-500">
                              {p.last_seen_open_at
                                ? new Date(p.last_seen_open_at).toLocaleString()
                                : "-"}
                            </td>
                            {canWrite && (
                              <td className="px-4 py-2 text-xs">
                                {p.suppressed ? (
                                  <button
                                    onClick={() => void restore(p)}
                                    className="text-emerald-400 hover:text-emerald-300"
                                  >
                                    {t("ports.fp.restore")}
                                  </button>
                                ) : (
                                  <button
                                    onClick={() => void markFP(p)}
                                    className="text-slate-400 hover:text-red-300"
                                  >
                                    {t("ports.fp.mark")}
                                  </button>
                                )}
                              </td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
