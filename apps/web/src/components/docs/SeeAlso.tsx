import { Link } from "react-router-dom";
import { type TKey } from "../../i18n/locales/en";
import { useI18n } from "../../i18n/I18nContext";

// Cross-links to related guides. Items are passed in (guide id + title key) to
// avoid a dependency cycle with the guide registry.
export default function SeeAlso({ items }: { items: { id: string; title: TKey }[] }) {
  const { t } = useI18n();
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2">
      <p className="mb-1.5 text-xs font-medium text-slate-400">{t("docs.seeAlso")}</p>
      <div className="flex flex-wrap gap-2">
        {items.map((it) => (
          <Link
            key={it.id}
            to={`/docs/${it.id}`}
            className="rounded-md border border-slate-700 px-2 py-0.5 text-xs text-sky-400 hover:border-slate-600 hover:text-sky-300"
          >
            {t(it.title)}
          </Link>
        ))}
      </div>
    </div>
  );
}
