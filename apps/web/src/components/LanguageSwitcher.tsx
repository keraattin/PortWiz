import { LANGUAGES, type Lang, useI18n } from "../i18n/I18nContext";

export default function LanguageSwitcher() {
  const { lang, setLang, t } = useI18n();
  return (
    <select
      value={lang}
      onChange={(e) => setLang(e.target.value as Lang)}
      title={t("chrome.language")}
      aria-label={t("chrome.language")}
      className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
    >
      {LANGUAGES.map((l) => (
        <option key={l.code} value={l.code}>
          {l.label}
        </option>
      ))}
    </select>
  );
}
