import { useNavigate, useParams } from "react-router-dom";
import PageHeader from "../components/PageHeader";
import { GUIDES } from "../docs/guides";
import { useI18n } from "../i18n/I18nContext";

export default function DocsPage() {
  const { t } = useI18n();
  const { guideId } = useParams();
  const navigate = useNavigate();
  const active = GUIDES.find((g) => g.id === guideId) ?? GUIDES[0];
  const Body = active.Body;

  return (
    <div className="space-y-6">
      <PageHeader title={t("docs.title")} subtitle={t("docs.subtitle")} />
      <div className="grid gap-6 md:grid-cols-[17rem_1fr]">
        <aside className="space-y-1">
          {GUIDES.map((g) => (
            <button
              key={g.id}
              onClick={() => navigate(`/docs/${g.id}`)}
              className={`flex w-full items-start gap-2 rounded-lg border px-3 py-2 text-left transition ${
                g.id === active.id
                  ? "border-sky-800 bg-sky-950/40"
                  : "border-slate-800 bg-slate-900 hover:border-slate-700"
              }`}
            >
              <span className="text-lg leading-none" aria-hidden="true">
                {g.icon}
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-medium text-slate-100">{t(g.titleKey)}</span>
                <span className="block text-xs text-slate-500">{t(g.summaryKey)}</span>
              </span>
            </button>
          ))}
        </aside>
        <article className="min-w-0 rounded-xl border border-slate-800 bg-slate-900 p-6">
          <h2 className="mb-5 text-xl font-semibold text-slate-100">{t(active.titleKey)}</h2>
          <Body />
        </article>
      </div>
    </div>
  );
}
