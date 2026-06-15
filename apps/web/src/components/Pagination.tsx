import { useMemo, useState } from "react";

/** Client-side pagination over an already-fetched array. */
export function usePagination<T>(items: T[], pageSize = 15) {
  const [page, setPage] = useState(0);
  const pageCount = Math.max(1, Math.ceil(items.length / pageSize));
  const current = Math.min(page, pageCount - 1);
  const slice = useMemo(
    () => items.slice(current * pageSize, current * pageSize + pageSize),
    [items, current, pageSize],
  );
  return { page: current, setPage, pageCount, slice, total: items.length };
}

interface PaginationProps {
  page: number;
  pageCount: number;
  total: number;
  onPage: (page: number) => void;
}

export default function Pagination({ page, pageCount, total, onPage }: PaginationProps) {
  if (pageCount <= 1) return null;
  return (
    <div className="flex items-center justify-between pt-3 text-sm text-slate-500">
      <span>{total} total</span>
      <div className="flex items-center gap-2">
        <button
          disabled={page <= 0}
          onClick={() => onPage(page - 1)}
          className="rounded-lg border border-slate-700 px-2 py-1 text-slate-300 hover:bg-slate-800 disabled:opacity-40"
        >
          Prev
        </button>
        <span>
          Page {page + 1} of {pageCount}
        </span>
        <button
          disabled={page >= pageCount - 1}
          onClick={() => onPage(page + 1)}
          className="rounded-lg border border-slate-700 px-2 py-1 text-slate-300 hover:bg-slate-800 disabled:opacity-40"
        >
          Next
        </button>
      </div>
    </div>
  );
}
