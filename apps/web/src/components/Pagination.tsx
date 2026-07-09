import { useMemo, useState } from "react";
import { useI18n } from "../i18n/I18nContext";

const PAGE_SIZES = [10, 15, 25, 50, 100];

/** Client-side pagination over an already-fetched array. Page size is user
 * adjustable (returned as `pageSize`/`setPageSize`); changing it resets to the
 * first page so the view never lands on an out-of-range page. */
export function usePagination<T>(items: T[], initialPageSize = 15) {
  const [page, setPage] = useState(0);
  const [pageSize, setPageSizeState] = useState(initialPageSize);
  const pageCount = Math.max(1, Math.ceil(items.length / pageSize));
  const current = Math.min(page, pageCount - 1);
  const slice = useMemo(
    () => items.slice(current * pageSize, current * pageSize + pageSize),
    [items, current, pageSize],
  );
  const setPageSize = (n: number) => {
    setPageSizeState(n);
    setPage(0);
  };
  return { page: current, setPage, pageCount, slice, total: items.length, pageSize, setPageSize };
}

interface PaginationProps {
  page: number;
  pageCount: number;
  total: number;
  onPage: (page: number) => void;
  // When both are supplied, a rows-per-page selector is shown.
  pageSize?: number;
  onPageSize?: (size: number) => void;
}

export default function Pagination({
  page,
  pageCount,
  total,
  onPage,
  pageSize,
  onPageSize,
}: PaginationProps) {
  const { t } = useI18n();
  if (total === 0) return null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 pt-3 text-sm text-slate-500">
      <div className="flex items-center gap-3">
        <span>{t("pagination.total", { total })}</span>
        {onPageSize && pageSize !== undefined && (
          <label className="flex items-center gap-1.5">
            <span>{t("pagination.pageSize")}</span>
            <select
              value={pageSize}
              onChange={(e) => onPageSize(Number(e.target.value))}
              className="rounded-lg border border-slate-700 bg-slate-800 px-2 py-1 text-slate-300 outline-none focus:border-emerald-500"
            >
              {PAGE_SIZES.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      {pageCount > 1 && (
        <div className="flex items-center gap-2">
          <button
            disabled={page <= 0}
            onClick={() => onPage(page - 1)}
            className="rounded-lg border border-slate-700 px-2 py-1 text-slate-300 hover:bg-slate-800 disabled:opacity-40"
          >
            {t("pagination.prev")}
          </button>
          <span>{t("pagination.pageOf", { page: page + 1, pageCount })}</span>
          <button
            disabled={page >= pageCount - 1}
            onClick={() => onPage(page + 1)}
            className="rounded-lg border border-slate-700 px-2 py-1 text-slate-300 hover:bg-slate-800 disabled:opacity-40"
          >
            {t("pagination.next")}
          </button>
        </div>
      )}
    </div>
  );
}
