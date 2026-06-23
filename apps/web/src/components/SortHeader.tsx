import { type SortState } from "./useSort";

// A clickable table header that sorts its column. The indicator is an inline SVG
// (an up + down chevron, the active direction highlighted) rather than a Unicode
// arrow, so it renders consistently across platforms.
export default function SortHeader({
  label,
  sortKey,
  sort,
  onSort,
  className = "px-4 py-2 font-medium",
}: {
  label: string;
  sortKey: string;
  sort: SortState;
  onSort: (key: string) => void;
  className?: string;
}) {
  const active = sort.key === sortKey;
  return (
    <th className={className} aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}>
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className={`inline-flex items-center gap-1 ${active ? "text-emerald-400" : "hover:text-slate-200"}`}
      >
        {label}
        <svg
          viewBox="0 0 16 16"
          className="h-3.5 w-3.5 shrink-0"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M5 6.5l3-3 3 3" className={active && sort.dir === "asc" ? "" : "opacity-30"} />
          <path d="M5 9.5l3 3 3-3" className={active && sort.dir === "desc" ? "" : "opacity-30"} />
        </svg>
      </button>
    </th>
  );
}
