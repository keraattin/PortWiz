import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

// Navigation is grouped into a few top-level sections; each section reveals its
// pages as contextual sub-tabs. `roles`, when present, limits visibility.
interface Tab {
  to: string;
  label: string;
  roles?: string[];
}

interface Section {
  label: string;
  tabs: Tab[];
  roles?: string[];
}

const SECTIONS: Section[] = [
  { label: "Dashboard", tabs: [{ to: "/", label: "Dashboard" }] },
  {
    label: "Inventory",
    tabs: [
      { to: "/assets", label: "Assets" },
      { to: "/vlans", label: "VLANs" },
    ],
  },
  {
    label: "Scanning",
    tabs: [
      { to: "/scans", label: "Scans" },
      { to: "/agents", label: "Agents", roles: ["admin", "auditor"] },
    ],
  },
  {
    label: "Changes",
    tabs: [
      { to: "/changes", label: "Changes" },
      { to: "/tasks", label: "Tasks" },
    ],
  },
  { label: "Compliance", tabs: [{ to: "/compliance", label: "Compliance" }] },
  { label: "Assistant", tabs: [{ to: "/assistant", label: "Assistant" }] },
  {
    label: "Admin",
    roles: ["admin", "auditor"],
    tabs: [
      { to: "/users", label: "Users", roles: ["admin", "auditor"] },
      { to: "/settings", label: "Settings" },
    ],
  },
];

function pathInTab(pathname: string, to: string): boolean {
  return to === "/" ? pathname === "/" : pathname === to || pathname.startsWith(`${to}/`);
}

export default function Layout() {
  const { user, logout } = useAuth();
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
                    key={s.label}
                    to={s.tabs[0].to}
                    className={`rounded-lg px-3 py-1.5 text-sm ${
                      active
                        ? "bg-slate-800 text-emerald-400"
                        : "text-slate-300 hover:bg-slate-900"
                    }`}
                  >
                    {s.label}
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
            <button
              onClick={logout}
              className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
            >
              Sign out
            </button>
          </div>
        </div>

        {activeSection && activeSection.tabs.length > 1 && (
          <nav className="flex gap-1 px-8 pb-2">
            {activeSection.tabs.map((t) => (
              <NavLink
                key={t.to}
                to={t.to}
                end={t.to === "/"}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1 text-sm ${
                    isActive
                      ? "bg-slate-800 text-emerald-300"
                      : "text-slate-400 hover:bg-slate-900"
                  }`
                }
              >
                {t.label}
              </NavLink>
            ))}
          </nav>
        )}
      </header>
      <main className="px-8 py-8">
        <Outlet />
      </main>
    </div>
  );
}
