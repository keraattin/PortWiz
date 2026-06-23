import { useCallback, useState } from "react";

export type SortDir = "asc" | "desc";
export interface SortState {
  key: string | null;
  dir: SortDir;
}

/** Click-to-sort column state: first click sorts ascending, next toggles. */
export function useSort(initial: SortState = { key: null, dir: "asc" }) {
  const [sort, setSort] = useState<SortState>(initial);
  const toggleSort = useCallback((key: string) => {
    setSort((s) =>
      s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: "asc" },
    );
  }, []);
  return { sort, toggleSort, setSort };
}

type Value = string | number | null | undefined;

/** Pure, stable sort by a single column. Nulls/blanks sort last; strings use a
 * locale-aware, numeric-friendly compare. Returns a new array (input untouched). */
export function sortRows<T>(
  rows: T[],
  sort: SortState,
  getValue: (row: T, key: string) => Value,
): T[] {
  if (!sort.key) return rows;
  const key = sort.key;
  const dir = sort.dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const av = getValue(a, key);
    const bv = getValue(b, key);
    const aEmpty = av == null || av === "";
    const bEmpty = bv == null || bv === "";
    if (aEmpty && bEmpty) return 0;
    if (aEmpty) return 1; // empties last, regardless of direction
    if (bEmpty) return -1;
    if (typeof av === "number" && typeof bv === "number") return (av - bv) * dir;
    return String(av).localeCompare(String(bv), undefined, { numeric: true }) * dir;
  });
}
