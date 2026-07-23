import { useEffect, useState } from "react";
import { type OpenPort, listOpenPorts } from "../api/client";
import { useErrorMessage } from "../i18n/useErrorMessage";
import EmptyState from "../components/EmptyState";
import InfoCallout from "../components/InfoCallout";
import PageHeader from "../components/PageHeader";
import Pagination, { usePagination } from "../components/Pagination";
import SearchInput from "../components/SearchInput";
import { type Column, TableHead, processRows, useColumnFilters } from "../components/tableView";
import { useSort } from "../components/useSort";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

const PROTOCOLS = ["tcp", "udp"] as const;
const CRIT_BADGE: Record<string, string> = {
  critical: "bg-red-900 text-red-300",
  high: "bg-orange-900 text-orange-200",
  medium: "bg-amber-900 text-amber-300",
  low: "bg-slate-700 text-slate-300",
};

export default function PortsPage() {
  const { t } = useI18n();
  const errorMessage = useErrorMessage();
  const [ports, setPorts] = useState<OpenPort[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const { sort, toggleSort } = useSort();
  const { filters, setFilter } = useColumnFilters();
  const [search, setSearch] = useState("");

  const columns: Column<OpenPort>[] = [
    { key: "host", label: t("ports.col.host"), filter: "text", get: (p) => p.hostname ?? p.ip },
    { key: "ip", label: t("ports.col.ip"), filter: "text", get: (p) => p.ip },
    { key: "port", label: t("ports.col.port"), filter: "text", get: (p) => p.port },
    {
      key: "protocol",
      label: t("ports.col.protocol"),
      filter: PROTOCOLS.map((p) => ({ value: p, label: p.toUpperCase() })),
      get: (p) => p.protocol,
    },
    { key: "service", label: t("ports.col.service"), filter: "text", get: (p) => p.service ?? "" },
    { key: "version", label: t("ports.col.version"), filter: "text", get: (p) => p.version ?? "" },
    { key: "seen", label: t("ports.col.seen"), filter: "text", get: (p) => p.last_seen_open_at ?? "" },
  ];

  const processed = processRows(ports, columns, sort, filters, search);
  const page = usePagination(processed, 20);
  const onColFilter = (key: string, v: string) => {
    setFilter(key, v);
    page.setPage(0);
  };

  useEffect(() => {
    void (async () => {
      setLoading(true);
      try {
        setPorts(await listOpenPorts());
      } catch (e) {
        setError(errorMessage(e));
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // A clickable value that filters the table to it (e.g. click a port to see
  // every host with that port open, or an IP to see all of that host's ports).
  function filterLink(value: string) {
    return (
      <button
        className="hover:text-emerald-400"
        onClick={() => {
          setSearch(value);
          page.setPage(0);
        }}
      >
        {value}
      </button>
    );
  }

  function renderRow(p: OpenPort) {
    return (
      <tr key={`${p.ip}-${p.port}-${p.protocol}`} className="bg-slate-950">
        <td className="px-4 py-2 text-slate-100">
          {p.hostname ?? <span className="text-slate-500">{t("ports.noHostname")}</span>}
          {p.criticality && (
            <span className={`ml-2 rounded-full px-2 py-0.5 text-[10px] ${CRIT_BADGE[p.criticality] ?? ""}`}>
              {t(`crit.${p.criticality}` as TKey)}
            </span>
          )}
        </td>
        <td className="px-4 py-2 font-mono text-slate-300">{filterLink(p.ip)}</td>
        <td className="px-4 py-2 font-mono text-slate-100">{filterLink(String(p.port))}</td>
        <td className="px-4 py-2 uppercase text-slate-400">{p.protocol}</td>
        <td className="px-4 py-2 text-slate-300">{p.service || <span className="text-slate-600">-</span>}</td>
        <td className="px-4 py-2 text-slate-400">{p.version || <span className="text-slate-600">-</span>}</td>
        <td className="px-4 py-2 text-xs text-slate-500">
          {p.last_seen_open_at ? new Date(p.last_seen_open_at).toLocaleString() : "-"}
        </td>
      </tr>
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader title={t("ports.title")} subtitle={t("ports.subtitle")} docsGuide="scanning" />
      <InfoCallout>{t("ports.info")}</InfoCallout>
      {error && <p className="text-sm text-red-400">{error}</p>}

      {!loading && ports.length > 0 && (
        <div className="flex justify-end">
          <SearchInput value={search} onChange={setSearch} />
        </div>
      )}

      {loading ? (
        <div className="rounded-xl border border-slate-800 p-4 text-sm text-slate-500">
          {t("common.loading")}
        </div>
      ) : ports.length === 0 ? (
        <EmptyState icon="🔌" title={t("ports.empty")} body={t("ports.emptyBody")} />
      ) : processed.length === 0 ? (
        <div className="rounded-xl border border-slate-800 p-4 text-center text-sm text-slate-500">
          {t("common.noData")}
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
              />
              <tbody className="divide-y divide-slate-800">{page.slice.map(renderRow)}</tbody>
            </table>
          </div>
          <Pagination
            page={page.page}
            pageCount={page.pageCount}
            total={page.total}
            onPage={page.setPage}
            pageSize={page.pageSize}
            onPageSize={page.setPageSize}
          />
        </>
      )}
    </div>
  );
}
