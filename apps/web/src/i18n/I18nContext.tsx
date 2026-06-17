import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { type TKey, en } from "./locales/en";
import { de } from "./locales/de";
import { es } from "./locales/es";
import { fr } from "./locales/fr";
import { pt } from "./locales/pt";
import { tr } from "./locales/tr";

export type Lang = "en" | "tr" | "de" | "fr" | "pt" | "es";

// Native language names shown in the switcher.
export const LANGUAGES: { code: Lang; label: string }[] = [
  { code: "en", label: "English" },
  { code: "tr", label: "Türkçe" },
  { code: "de", label: "Deutsch" },
  { code: "fr", label: "Français" },
  { code: "pt", label: "Português" },
  { code: "es", label: "Español" },
];

const DICTS: Record<Lang, Partial<Record<TKey, string>>> = {
  en,
  tr,
  de,
  fr,
  pt,
  es,
};

const STORAGE_KEY = "portwiz-lang";

type Vars = Record<string, string | number>;

interface I18nState {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: TKey, vars?: Vars) => string;
}

const I18nContext = createContext<I18nState | undefined>(undefined);

function isLang(value: string | null): value is Lang {
  return LANGUAGES.some((l) => l.code === value);
}

function initialLang(): Lang {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (isLang(stored)) return stored;
  const nav = navigator.language?.slice(0, 2).toLowerCase() ?? "";
  if (isLang(nav)) return nav;
  return "en";
}

function interpolate(template: string, vars?: Vars): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (match, name) =>
    name in vars ? String(vars[name]) : match,
  );
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => initialLang());

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, lang);
    document.documentElement.setAttribute("lang", lang);
  }, [lang]);

  function setLang(next: Lang) {
    setLangState(next);
  }

  function t(key: TKey, vars?: Vars): string {
    const template = DICTS[lang][key] ?? en[key] ?? key;
    return interpolate(template, vars);
  }

  return <I18nContext.Provider value={{ lang, setLang, t }}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nState {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error("useI18n must be used within an I18nProvider");
  }
  return ctx;
}
