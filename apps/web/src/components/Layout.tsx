import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";
import AssistantWidget from "./AssistantWidget";
import LanguageSwitcher from "./LanguageSwitcher";
import NavIcon, { type IconKey } from "./NavIcon";
import ThemeToggle from "./ThemeToggle";
import Tour from "./Tour";

// Navigation lives in a left sidebar. Each top-level section carries an icon so
// the sidebar stays legible when collapsed to icons only; the active section
// reveals its pages as nested sub-tabs when expanded. `roles`, when present,
// limits visibility.
interface Tab {
  to: string;
  labelKey: TKey;
  roles?: string[];
}

interface Section {
  labelKey: TKey;
  icon: IconKey;
  tabs: Tab[];
  roles?: string[];
}

const SECTIONS: Section[] = [
  { labelKey: "nav.dashboard", icon: "dashboard", tabs: [{ to: "/", labelKey: "nav.dashboard" }] },
  {
    labelKey: "nav.inventory",
    icon: "inventory",
    tabs: [
      { to: "/assets", labelKey: "nav.assets" },
      { to: "/vlans", labelKey: "nav.vlans" },
    ],
  },
  {
    labelKey: "nav.scanning",
    icon: "scanning",
    tabs: [
      { to: "/scans", labelKey: "nav.scans" },
      { to: "/agents", labelKey: "nav.agents", roles: ["admin", "auditor"] },
    ],
  },
  {
    labelKey: "nav.changes",
    icon: "changes",
    tabs: [
      { to: "/changes", labelKey: "nav.changes" },
      { to: "/tasks", labelKey: "nav.tasks" },
      { to: "/cve", labelKey: "nav.cve" },
    ],
  },
  {
    labelKey: "nav.compliance",
    icon: "compliance",
    tabs: [{ to: "/compliance", labelKey: "nav.compliance" }],
  },
  {
    labelKey: "nav.admin",
    icon: "admin",
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

const STORAGE_KEY = "portwiz-sidebar";
const TOUR_KEY = "portwiz-tour-seen";

export default function Layout() {
  const { user, logout } = useAuth();
  const { t } = useI18n();
  const { pathname } = useLocation();
  const role = user?.role;

  const [collapsed, setCollapsed] = useState<boolean>(
    () => localStorage.getItem(STORAGE_KEY) === "collapsed",
  );

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, collapsed ? "collapsed" : "expanded");
  }, [collapsed]);

  // First-run welcome tour: shown once, then reopenable from the header.
  const [tourOpen, setTourOpen] = useState(false);
  useEffect(() => {
    if (localStorage.getItem(TOUR_KEY) !== "1") setTourOpen(true);
  }, []);
  function closeTour() {
    setTourOpen(false);
    localStorage.setItem(TOUR_KEY, "1");
  }

  const sections = SECTIONS.filter((s) => !s.roles || (role != null && s.roles.includes(role)))
    .map((s) => ({
      ...s,
      tabs: s.tabs.filter((tab) => !tab.roles || (role != null && tab.roles.includes(role))),
    }))
    .filter((s) => s.tabs.length > 0);

  const activeSection =
    sections.find((s) => s.tabs.some((tab) => pathInTab(pathname, tab.to))) ?? null;

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      <aside
        className={`flex shrink-0 flex-col border-r border-slate-800 bg-slate-900 transition-[width] duration-200 ${
          collapsed ? "w-16" : "w-60"
        }`}
      >
        <div className="flex h-14 items-center gap-2 border-b border-slate-800 px-3">
          {!collapsed && (
            <span className="flex-1 truncate text-lg font-bold text-emerald-400">PortWiz</span>
          )}
          <button
            onClick={() => setCollapsed((c) => !c)}
            title={t("chrome.toggleMenu")}
            aria-label={t("chrome.toggleMenu")}
            className={`rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-slate-100 ${
              collapsed ? "mx-auto" : ""
            }`}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-5 w-5"
              aria-hidden="true"
            >
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
        </div>

        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-2">
          {sections.map((s) => {
            const active = s === activeSection;
            return (
              <div key={s.labelKey}>
                <Link
                  to={s.tabs[0].to}
                  title={collapsed ? t(s.labelKey) : undefined}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${
                    collapsed ? "justify-center" : ""
                  } ${
                    active
                      ? "bg-slate-800 text-emerald-400"
                      : "text-slate-300 hover:bg-slate-800/60"
                  }`}
                >
                  <NavIcon name={s.icon} />
                  {!collapsed && <span className="truncate">{t(s.labelKey)}</span>}
                </Link>
                {!collapsed && active && s.tabs.length > 1 && (
                  <div className="mt-1 ml-4 flex flex-col gap-0.5 border-l border-slate-800 pl-3">
                    {s.tabs.map((tab) => (
                      <NavLink
                        key={tab.to}
                        to={tab.to}
                        end={tab.to === "/"}
                        className={({ isActive }) =>
                          `rounded-lg px-3 py-1.5 text-sm ${
                            isActive
                              ? "text-emerald-300"
                              : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
                          }`
                        }
                      >
                        {t(tab.labelKey)}
                      </NavLink>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-end gap-4 border-b border-slate-800 px-6">
          <div className="text-right text-sm">
            <p className="text-slate-200">{user?.email}</p>
            <p className="text-xs uppercase tracking-wide text-emerald-500">{user?.role}</p>
          </div>
          <button
            onClick={() => setTourOpen(true)}
            title={t("tour.launch")}
            aria-label={t("tour.launch")}
            className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-700 text-sm text-slate-300 hover:bg-slate-800 hover:text-slate-100"
          >
            ?
          </button>
          <LanguageSwitcher />
          <ThemeToggle />
          <button
            onClick={logout}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
          >
            {t("chrome.signOut")}
          </button>
        </header>
        <main className="flex-1 px-8 py-8">
          <Outlet />
        </main>
      </div>
      <AssistantWidget />
      <Tour open={tourOpen} onClose={closeTour} />
    </div>
  );
}
