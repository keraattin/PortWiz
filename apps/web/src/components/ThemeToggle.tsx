import { useI18n } from "../i18n/I18nContext";
import { useTheme } from "../theme/ThemeContext";

export default function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const { t } = useI18n();
  const isDark = theme === "dark";
  const label = isDark ? t("chrome.switchToLight") : t("chrome.switchToDark");
  return (
    <button
      onClick={toggle}
      title={label}
      aria-label={label}
      className="rounded-lg border border-slate-700 px-2.5 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
    >
      {isDark ? "☀️" : "🌙"}
    </button>
  );
}
