import { useState } from "react";
import { Link } from "react-router-dom";
import Modal from "./Modal";
import { GUIDES } from "../docs/guides";
import { useI18n } from "../i18n/I18nContext";

// A small "How to" button that opens the relevant in-app Docs guide in a popup,
// so the user gets help without leaving the page. The guide content is the same
// one rendered on the Docs page (single source), plus a link to open it there.
export default function DocsLink({ guide, className }: { guide: string; className?: string }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const g = GUIDES.find((x) => x.id === guide) ?? GUIDES[0];
  const Body = g.Body;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        title={t("common.howTo")}
        className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md border border-slate-700 px-2.5 py-1 text-xs text-slate-400 transition hover:border-slate-600 hover:text-slate-200 ${className ?? ""}`}
      >
        <span aria-hidden="true">?</span>
        {t("common.howTo")}
      </button>
      <Modal open={open} onClose={() => setOpen(false)} title={t(g.titleKey)} wide>
        <Body />
        <div className="mt-6 border-t border-slate-800 pt-3 text-right">
          <Link
            to={`/docs/${g.id}`}
            onClick={() => setOpen(false)}
            className="text-xs text-sky-400 underline hover:text-sky-300"
          >
            {t("docs.openFull")}
          </Link>
        </div>
      </Modal>
    </>
  );
}
