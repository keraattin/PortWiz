import { useI18n } from "../i18n/I18nContext";

export interface FilterOption {
  value: string;
  label: string;
}

// A compact dropdown for filtering a table by a categorical column. An empty
// value means "no filter"; the first option is an all-pass entry.
export default function FilterSelect({
  value,
  onChange,
  options,
  allLabel,
}: {
  value: string;
  onChange: (v: string) => void;
  options: FilterOption[];
  allLabel?: string;
}) {
  const { t } = useI18n();
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500"
    >
      <option value="">{allLabel ?? t("filters.all")}</option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}
