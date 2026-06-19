import { useI18n } from "../i18n/I18nContext";

export default function SearchInput({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  const { t } = useI18n();
  return (
    <div className="relative w-full sm:w-64">
      <svg
        viewBox="0 0 20 20"
        className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        aria-hidden="true"
      >
        <circle cx="9" cy="9" r="6" />
        <path d="M14 14l4 4" strokeLinecap="round" />
      </svg>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder ?? t("common.search")}
        className="w-full rounded-lg border border-slate-700 bg-slate-800 py-2 pl-8 pr-3 text-sm text-slate-100 outline-none focus:border-emerald-500"
      />
    </div>
  );
}
