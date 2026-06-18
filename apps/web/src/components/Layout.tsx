import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";
import AssistantWidget from "./AssistantWidget";
import LanguageSwitcher from "./LanguageSwitcher";
import ThemeToggle from "./ThemeToggle";

// Navigation is grouped into a few top-level sections; each section reveals its
// pages as contextual sub-tabs. `roles`, when present, limits visibility.
interface Tab {
  to: string;
  labelKey: TKey;
  roles?: string[];
}

interface Section {
  labelKey: TKey;
  tabs: Tab[];
  roles?: string[];
}

const SECTIONS: Section[] = [
  { labelKey: "nav.dashboard", tabs: [{ to: "/", labelKey: "nav.dashboard" }] },
  {
    labelKey: "nav.inventory",
    tabs: [
      { to: "/assets", labelKey: "nav.assets" },
      { to: "/vlans", labelKey: "nav.vlans" },
    ],
  },
  {
    labelKey: "nav.scanning",
    tabs: [
      { to: "/scans", labelKey: "nav.scans" },
      { to: "/agents", labelKey: "nav.agents", roles: ["admin", "auditor"] },
    ],
  },
  {
    labelKey: "nav.changes",
    tabs: [
      { to: "/changes", labelKey: "nav.changes" },
      { to: "/tasks", labelKey: "nav.tasks" },
    ],
  },
  { labelKey: "nav.compliance", tabs: [{ to: "/compliance", labelKey: "nav.compliance" }] },
  {
    labelKey: "nav.admin",
    roles: ["admin", "auditor"],
    tabs: [
      { to: "/users", labelKey: "nav.users", roles: ["admin", "auditor"] },
      { to: "/settings", labelKey: "nav.settings" },
    ],
  },
];

function pathInTab(pathname: string, to: string): boolean {
  return to === "/" ? pathname === "/" : pathname === to || pathname.startsWith(`${to}/`);
}

export default function Layout() {
  const { user, logout } = useAuth();
  const { t } = useI18n();
  const { pathname } = useLocation();
  const role = user?.role;

  const sections = SECTIONS.filter((s) => !s.roles || (role != null && s.roles.includes(role)))
    .map((s) => ({
      ...s,
      tabs: s.tabs.filter((t) => !t.roles || (role != null && t.roles.includes(role))),
    }))
    .filter((s) => s.tabs.length > 0);

  const activeSection =
    sections.find((s) => s.tabs.some((t) => pathInTab(pathname, t.to))) ?? null;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800">
        <div className="flex items-center justify-between px-8 py-3">
          <div className="flex items-center gap-8">
            <span className="text-lg font-bold text-emerald-400">PortWiz</span>
            <nav className="flex gap-1">
              {sections.map((s) => {
                const active = s === activeSection;
                return (
                  <Link
                    key={s.labelKey}
                    to={s.tabs[0].to}
                    className={`rounded-lg px-3 py-1.5 text-sm ${
                      active
                        ? "bg-slate-800 text-emerald-400"
                        : "text-slate-300 hover:bg-slate-900"
                    }`}
                  >
                    {t(s.labelKey)}
                  </Link>
                );
              })}
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right text-sm">
              <p className="text-slate-200">{user?.email}</p>
              <p className="text-xs uppercase tracking-wide text-emerald-500">{user?.role}</p>
            </div>
            <LanguageSwitcher />
            <ThemeToggle />
            <button
              onClick={logout}
              className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
            >
              {t("chrome.signOut")}
            </button>
          </div>
        </div>

        {activeSection && activeSection.tabs.length > 1 && (
          <nav className="flex gap-1 px-8 pb-2">
            {activeSection.tabs.map((tab) => (
              <NavLink
                key={tab.to}
                to={tab.to}
                end={tab.to === "/"}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1 text-sm ${
                    isActive
                      ? "bg-slate-800 text-emerald-300"
                      : "text-slate-400 hover:bg-slate-900"
                  }`
                }
              >
                {t(tab.labelKey)}
              </NavLink>
            ))}
          </nav>
        )}
      </header>
      <main className="px-8 py-8">
        <Outlet />
      </main>
      <AssistantWidget />
    </div>
  );
}
