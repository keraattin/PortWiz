import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { type Certificate, listCertificates } from "../api/client";
import { useErrorMessage } from "../i18n/useErrorMessage";
import PageHeader from "../components/PageHeader";
import Pagination, { usePagination } from "../components/Pagination";
import SearchInput from "../components/SearchInput";
import { type Column, TableHead, processRows, useColumnFilters } from "../components/tableView";
import { useSort } from "../components/useSort";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

const STATUSES = ["expired", "expiring", "valid"] as const;

// Sort by urgency (worst first), not alphabetically.
const STATUS_RANK: Record<string, number> = { valid: 0, expiring: 1, expired: 2 };

const STATUS_CLASS: Record<string, string> = {
  expired: "bg-red-900 text-red-200",
  expiring: "bg-amber-900 text-amber-200",
  valid: "bg-emerald-900 text-emerald-200",
};

function fmtDate(iso: string | null): string {
  if (!iso) return "-";
  return new Date(iso).toISOString().slice(0, 10);
}

export default function CertificatesPage() {
  const { t } = useI18n();
  const errorMessage = useErrorMessage();

  const [certs, setCerts] = useState<Certificate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { sort, toggleSort } = useSort();
  const { filters, setFilter } = useColumnFilters();
  const [search, setSearch] = useState("");

  const columns: Column<Certificate>[] = [
    { key: "host", label: t("certs.col.host"), filter: "text", get: (c) => `${c.ip}:${c.port}` },
    {
      key: "name",
      label: t("certs.col.name"),
      filter: "text",
      get: (c) => c.subject_cn ?? c.hostname ?? "",
    },
    { key: "issuer", label: t("certs.col.issuer"), filter: "text", get: (c) => c.issuer ?? "" },
    { key: "expires", label: t("certs.col.expires"), get: (c) => c.not_after ?? "" },
    {
      key: "status",
      label: t("certs.col.status"),
      filter: STATUSES.map((s) => ({ value: s, label: t(`certs.status.${s}` as TKey) })),
      get: (c) => c.status,
      rank: STATUS_RANK,
    },
  ];
  const processed = processRows(certs, columns, sort, filters, search);
  const page = usePagination(processed, 15);
  const onColFilter = (key: string, v: string) => {
    setFilter(key, v);
    page.setPage(0);
  };

  useEffect(() => {
    listCertificates()
      .then(setCerts)
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function expiryLabel(c: Certificate): string {
    if (c.days_to_expiry == null) return "";
    if (c.status === "expired") {
      return t("certs.expiredAgo", { days: Math.abs(c.days_to_expiry) });
    }
    return t("certs.expiresIn", { days: c.days_to_expiry });
  }

  return (
    <div className="space-y-6">
      <PageHeader title={t("certs.title")} subtitle={t("certs.subtitle")} />

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="flex flex-wrap items-center gap-3">
        <SearchInput value={search} onChange={setSearch} />
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <TableHead
            columns={columns}
            sort={sort}
            toggleSort={toggleSort}
            filters={filters}
            setFilter={onColFilter}
          />
          <tbody className="divide-y divide-slate-800">
            {loading ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={5}>
                  {t("common.loading")}
                </td>
              </tr>
            ) : certs.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-center text-slate-500" colSpan={5}>
                  {t("certs.empty")}
                </td>
              </tr>
            ) : processed.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-center text-slate-500" colSpan={5}>
                  {t("common.noData")}
                </td>
              </tr>
            ) : (
              page.slice.map((c) => (
                <tr key={`${c.ip}:${c.port}/${c.protocol}`} className="bg-slate-950">
                  <td className="px-4 py-2 font-mono text-xs">
                    <Link
                      to={`/ports/${c.port}`}
                      className="text-emerald-400 hover:text-emerald-300"
                    >
                      {c.ip}:{c.port}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-slate-200">
                    {c.subject_cn ?? c.hostname ?? "-"}
                    {c.self_signed && (
                      <span className="ml-2 rounded-full bg-slate-700 px-2 py-0.5 text-xs text-slate-300">
                        {t("certs.selfSigned")}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-slate-400">{c.issuer ?? "-"}</td>
                  <td className="px-4 py-2 text-slate-300">
                    <span className="text-slate-200">{fmtDate(c.not_after)}</span>
                    <span className="ml-2 text-xs text-slate-500">{expiryLabel(c)}</span>
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        STATUS_CLASS[c.status] ?? STATUS_CLASS.valid
                      }`}
                    >
                      {t(`certs.status.${c.status}` as TKey)}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
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
    </div>
  );
}
