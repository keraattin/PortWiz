import { useEffect, useRef, useState } from "react";
import { LANGUAGES, useI18n } from "../i18n/I18nContext";
import Flag from "./Flag";

export default function LanguageSwitcher() {
  const { lang, setLang, t } = useI18n();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const current = LANGUAGES.find((l) => l.code === lang) ?? LANGUAGES[0];

  useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        title={t("chrome.language")}
        aria-label={t("chrome.language")}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-lg border border-slate-700 px-2.5 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
      >
        <Flag code={current.code} />
        <span className="hidden sm:inline">{current.label}</span>
        <span className="text-xs text-slate-500">▾</span>
      </button>

      {open && (
        <ul
          role="listbox"
          className="absolute right-0 z-20 mt-1 w-44 overflow-hidden rounded-lg border border-slate-700 bg-slate-900 py-1 shadow-lg"
        >
          {LANGUAGES.map((l) => (
            <li key={l.code}>
              <button
                type="button"
                role="option"
                aria-selected={l.code === lang}
                onClick={() => {
                  setLang(l.code);
                  setOpen(false);
                }}
                className={`flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-slate-800 ${
                  l.code === lang ? "text-emerald-400" : "text-slate-300"
                }`}
              >
                <Flag code={l.code} />
                <span className="flex-1">{l.label}</span>
                {l.code === lang && <span className="text-xs">✓</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
