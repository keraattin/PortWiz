import { useCallback, useState } from "react";
import { useI18n } from "../i18n/I18nContext";
import SortHeader from "./SortHeader";
import { type SortState, sortRows } from "./useSort";

export interface FilterOption {
  value: string;
  label: string;
}

// One column's worth of sort + filter behaviour. `get` returns the value used
// for sorting and filtering; the body cells are still rendered per-page, so this
// config only drives the header, the filter row and row processing.
export interface Column<T> {
  key: string;
  label: string;
  get: (row: T) => string | number | null | undefined;
  filter?: "text" | FilterOption[]; // text box, dropdown, or (omitted) not filterable
  sortable?: boolean; // default true
  rank?: Record<string, number>; // sort an enum column by rank, not alphabetically
}

/** Per-column filter values, keyed by column key. */
export function useColumnFilters() {
  const [filters, setFilters] = useState<Record<string, string>>({});
  const setFilter = useCallback((key: string, value: string) => {
    setFilters((f) => ({ ...f, [key]: value }));
  }, []);
  return { filters, setFilter };
}

/** Apply column filters then sort. Enum columns match by equality, text columns
 * by case-insensitive substring. Pure; returns a new array. */
export function processRows<T>(
  rows: T[],
  columns: Column<T>[],
  sort: SortState,
  filters: Record<string, string>,
): T[] {
  const filtered = rows.filter((row) =>
    columns.every((col) => {
      const fv = filters[col.key];
      if (!fv || !col.filter) return true;
      const raw = col.get(row);
      const s = raw == null ? "" : String(raw);
      return Array.isArray(col.filter) ? s === fv : s.toLowerCase().includes(fv.toLowerCase());
    }),
  );
  if (!sort.key) return filtered;
  const col = columns.find((c) => c.key === sort.key);
  if (!col) return filtered;
  return sortRows(filtered, sort, (row) => {
    const raw = col.get(row);
    if (col.rank && raw != null) return col.rank[String(raw)] ?? 0;
    return raw;
  });
}

function FilterCell<T>({
  column,
  value,
  onChange,
}: {
  column: Column<T>;
  value: string;
  onChange: (v: string) => void;
}) {
  const { t } = useI18n();
  const cls =
    "w-full rounded-md border border-slate-700 bg-slate-800 px-2 py-1 text-xs font-normal text-slate-100 outline-none focus:border-emerald-500";
  if (!column.filter) return <th className="px-2 pb-2"></th>;
  return (
    <th className="px-2 pb-2 font-normal">
      {Array.isArray(column.filter) ? (
        <select value={value} onChange={(e) => onChange(e.target.value)} className={cls}>
          <option value="">{t("filters.all")}</option>
          {column.filter.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      ) : (
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={t("common.filter")}
          className={cls}
        />
      )}
    </th>
  );
}

// A table header driven by the column config: a sortable label row and, beneath
// it, a per-column filter row (text box or dropdown). `trailing` adds an empty
// header cell for a row-actions column.
export function TableHead<T>({
  columns,
  sort,
  toggleSort,
  filters,
  setFilter,
  trailing = false,
}: {
  columns: Column<T>[];
  sort: SortState;
  toggleSort: (key: string) => void;
  filters: Record<string, string>;
  setFilter: (key: string, value: string) => void;
  trailing?: boolean;
}) {
  const hasFilters = columns.some((c) => c.filter);
  return (
    <thead className="bg-slate-900 text-slate-400">
      <tr>
        {columns.map((c) =>
          c.sortable === false ? (
            <th key={c.key} className="px-4 py-2 font-medium">
              {c.label}
            </th>
          ) : (
            <SortHeader
              key={c.key}
              label={c.label}
              sortKey={c.key}
              sort={sort}
              onSort={toggleSort}
            />
          ),
        )}
        {trailing && <th className="px-4 py-2"></th>}
      </tr>
      {hasFilters && (
        <tr>
          {columns.map((c) => (
            <FilterCell
              key={c.key}
              column={c}
              value={filters[c.key] ?? ""}
              onChange={(v) => setFilter(c.key, v)}
            />
          ))}
          {trailing && <th className="px-2 pb-2"></th>}
        </tr>
      )}
    </thead>
  );
}
