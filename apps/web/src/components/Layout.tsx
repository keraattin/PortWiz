import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

// `roles`, when present, limits the nav item to those roles. Items without
// `roles` are visible to every authenticated user.
interface NavItem {
  to: string;
  label: string;
  end: boolean;
  roles?: string[];
}

const NAV: NavItem[] = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/assets", label: "Assets", end: false },
  { to: "/vlans", label: "VLANs", end: false },
  { to: "/scans", label: "Scans", end: false },
  { to: "/agents", label: "Agents", end: false, roles: ["admin", "auditor"] },
  { to: "/changes", label: "Changes", end: false },
  { to: "/tasks", label: "Tasks", end: false },
  { to: "/compliance", label: "Compliance", end: false },
  { to: "/assistant", label: "Assistant", end: false },
  { to: "/users", label: "Users", end: false, roles: ["admin", "auditor"] },
  { to: "/settings", label: "Settings", end: false },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navItems = NAV.filter(
    (item) => !item.roles || (user != null && item.roles.includes(user.role)),
  );

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="flex items-center justify-between border-b border-slate-800 px-8 py-3">
        <div className="flex items-center gap-8">
          <span className="text-lg font-bold text-emerald-400">PortWiz</span>
          <nav className="flex gap-1">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 text-sm ${
                    isActive
                      ? "bg-slate-800 text-emerald-400"
                      : "text-slate-300 hover:bg-slate-900"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right text-sm">
            <p className="text-slate-200">{user?.email}</p>
            <p className="text-xs uppercase tracking-wide text-emerald-500">
              {user?.role}
            </p>
          </div>
          <button
            onClick={logout}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
          >
            Sign out
          </button>
        </div>
      </header>
      <main className="px-8 py-8">
        <Outlet />
      </main>
    </div>
  );
}
