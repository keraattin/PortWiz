import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import PageHeader from "../components/PageHeader";
import SearchInput from "../components/SearchInput";
import { GUIDES, sectionAnchor } from "../docs/guides";
import { useI18n } from "../i18n/I18nContext";

export default function DocsPage() {
  const { t } = useI18n();
  const { guideId } = useParams();
  const { hash } = useLocation();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");

  // Scroll to the anchored section on a table-of-contents click or a deep link.
  useEffect(() => {
    if (!hash) return;
    document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [hash, guideId]);

  // A specific guide when the URL names one; otherwise the overview grid.
  const active = guideId ? GUIDES.find((g) => g.id === guideId) : null;
  const Body = active?.Body;

  const q = query.trim().toLowerCase();
  const filtered = q
    ? GUIDES.filter((g) => `${t(g.titleKey)} ${t(g.summaryKey)}`.toLowerCase().includes(q))
    : GUIDES;

  return (
    <div className="space-y-6">
      <PageHeader title={t("docs.title")} subtitle={t("docs.subtitle")} />
      <div className="grid gap-6 md:grid-cols-[17rem_1fr]">
        <aside className="space-y-2">
          <SearchInput value={query} onChange={setQuery} />
          <div className="space-y-1">
            {filtered.map((g) => (
              <button
                key={g.id}
                onClick={() => navigate(`/docs/${g.id}`)}
                className={`flex w-full items-start gap-2 rounded-lg border px-3 py-2 text-left transition ${
                  g.id === active?.id
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
            {filtered.length === 0 && (
              <p className="px-3 py-2 text-xs text-slate-500">{t("common.noData")}</p>
            )}
          </div>
        </aside>

        <article className="min-w-0 rounded-xl border border-slate-800 bg-slate-900 p-6">
          {active && Body ? (
            <>
              <h2 className="mb-5 text-xl font-semibold text-slate-100">{t(active.titleKey)}</h2>
              {active.toc && active.toc.length > 1 && (
                <nav className="mb-5 rounded-lg border border-slate-800 bg-slate-950 p-3">
                  <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-500">
                    {t("docs.contents")}
                  </p>
                  <div className="flex flex-wrap gap-x-4 gap-y-1">
                    {active.toc.map((h) => (
                      <a
                        key={h}
                        href={`#${sectionAnchor(h)}`}
                        className="text-xs text-sky-400 hover:text-sky-300"
                      >
                        {t(h)}
                      </a>
                    ))}
                  </div>
                </nav>
              )}
              <Body />
            </>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {GUIDES.map((g) => (
                <button
                  key={g.id}
                  onClick={() => navigate(`/docs/${g.id}`)}
                  className="rounded-xl border border-slate-800 bg-slate-950 p-4 text-left transition hover:border-slate-700"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-xl" aria-hidden="true">
                      {g.icon}
                    </span>
                    <span className="font-medium text-slate-100">{t(g.titleKey)}</span>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{t(g.summaryKey)}</p>
                </button>
              ))}
            </div>
          )}
        </article>
      </div>
    </div>
  );
}
