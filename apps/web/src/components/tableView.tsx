import { useCallback, useState } from "react";
import { useI18n } from "../i18n/I18nContext";
import InfoDot from "./InfoDot";
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
  info?: string; // optional hover-help explaining a jargon column
}

/** Per-column filter values, keyed by column key. */
export function useColumnFilters() {
  const [filters, setFilters] = useState<Record<string, string>>({});
  const setFilter = useCallback((key: string, value: string) => {
    setFilters((f) => ({ ...f, [key]: value }));
  }, []);
  return { filters, setFilter };
}

/** Row-selection state for bulk actions: a set of selected row ids plus toggles.
 * Ids are the caller's stable keys (usually the row id). */
export function useTableSelection() {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const toggle = useCallback((id: string) => {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);
  // Add or remove a batch of ids at once (drives the header select-all).
  const setMany = useCallback((ids: string[], on: boolean) => {
    setSelected((s) => {
      const next = new Set(s);
      for (const id of ids) {
        if (on) next.add(id);
        else next.delete(id);
      }
      return next;
    });
  }, []);
  const clear = useCallback(() => setSelected(new Set()), []);
  return { selected, toggle, setMany, clear };
}

export interface HeadSelection {
  allChecked: boolean;
  onToggleAll: (on: boolean) => void;
}

export const CHECKBOX_CLS = "h-4 w-4 rounded border-slate-600 bg-slate-800 accent-emerald-500";

/** Apply an optional free-text search (across every column) and per-column
 * filters, then sort. Enum columns match by equality, text columns by
 * case-insensitive substring. Pure; returns a new array. */
export function processRows<T>(
  rows: T[],
  columns: Column<T>[],
  sort: SortState,
  filters: Record<string, string>,
  search = "",
): T[] {
  const q = search.trim().toLowerCase();
  const filtered = rows.filter((row) => {
    if (q) {
      const hit = columns.some((col) => {
        const raw = col.get(row);
        return raw != null && String(raw).toLowerCase().includes(q);
      });
      if (!hit) return false;
    }
    return columns.every((col) => {
      const fv = filters[col.key];
      if (!fv || !col.filter) return true;
      const raw = col.get(row);
      const s = raw == null ? "" : String(raw);
      return Array.isArray(col.filter) ? s === fv : s.toLowerCase().includes(fv.toLowerCase());
    });
  });
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
  selection,
}: {
  columns: Column<T>[];
  sort: SortState;
  toggleSort: (key: string) => void;
  filters: Record<string, string>;
  setFilter: (key: string, value: string) => void;
  trailing?: boolean;
  // When set, a leading checkbox column drives bulk row selection.
  selection?: HeadSelection;
}) {
  const hasFilters = columns.some((c) => c.filter);
  return (
    <thead className="bg-slate-900 text-slate-400">
      <tr>
        {selection && (
          <th className="px-4 py-2">
            <input
              type="checkbox"
              className={CHECKBOX_CLS}
              checked={selection.allChecked}
              onChange={(e) => selection.onToggleAll(e.target.checked)}
            />
          </th>
        )}
        {columns.map((c) =>
          c.sortable === false ? (
            <th key={c.key} className="px-4 py-2 font-medium">
              <span className="inline-flex items-center gap-1">
                {c.label}
                {c.info && <InfoDot text={c.info} />}
              </span>
            </th>
          ) : (
            <SortHeader
              key={c.key}
              label={c.label}
              sortKey={c.key}
              sort={sort}
              onSort={toggleSort}
              info={c.info}
            />
          ),
        )}
        {trailing && <th className="px-4 py-2"></th>}
      </tr>
      {hasFilters && (
        <tr>
          {selection && <th className="px-2 pb-2"></th>}
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
