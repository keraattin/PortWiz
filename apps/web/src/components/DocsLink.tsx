import { Link } from "react-router-dom";
import { useI18n } from "../i18n/I18nContext";

// A small "How to" link that deep-links to an in-app Docs guide, so any page can
// point the user at the relevant guide without duplicating its content.
export default function DocsLink({ guide, className }: { guide: string; className?: string }) {
  const { t } = useI18n();
  return (
    <Link
      to={`/docs/${guide}`}
      title={t("common.howTo")}
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md border border-slate-700 px-2.5 py-1 text-xs text-slate-400 transition hover:border-slate-600 hover:text-slate-200 ${className ?? ""}`}
    >
      <span aria-hidden="true">?</span>
      {t("common.howTo")}
    </Link>
  );
}
