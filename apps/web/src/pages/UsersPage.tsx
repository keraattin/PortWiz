import { type FormEvent, useEffect, useState } from "react";
import {
  ApiError,
  type CurrentUser,
  type Role,
  createUser,
  listUsers,
  updateUser,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import Modal from "../components/Modal";
import Pagination, { usePagination } from "../components/Pagination";

function errorMessage(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong";
}

const ROLES: Role[] = ["admin", "operator", "auditor"];

const ROLE_BADGE: Record<string, string> = {
  admin: "bg-red-900 text-red-300",
  operator: "bg-sky-900 text-sky-300",
  auditor: "bg-slate-700 text-slate-300",
};

const ROLE_HINT: Record<Role, string> = {
  admin: "Full access, including users, agents, and settings.",
  operator: "Manage inventory, scans, changes, and tasks.",
  auditor: "Read-only: review changes, audit log, and evidence.",
};

const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500";
const labelClass = "block text-sm text-slate-300";
const primaryBtn =
  "rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50";

export default function UsersPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [users, setUsers] = useState<CurrentUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const usersPage = usePagination(users, 15);

  const [addOpen, setAddOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<Role>("operator");

  const [editUser, setEditUser] = useState<CurrentUser | null>(null);
  const [editName, setEditName] = useState("");
  const [editRole, setEditRole] = useState<Role>("operator");
  const [editActive, setEditActive] = useState(true);

  const editingSelf = editUser?.id === user?.id;

  async function reload() {
    setLoading(true);
    try {
      setUsers(await listUsers());
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
  }, []);

  function openAdd() {
    setError(null);
    setEmail("");
    setPassword("");
    setFullName("");
    setRole("operator");
    setAddOpen(true);
  }

  function openEdit(u: CurrentUser) {
    if (!isAdmin) return;
    setError(null);
    setEditUser(u);
    setEditName(u.full_name ?? "");
    setEditRole(u.role as Role);
    setEditActive(u.is_active);
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createUser({ email, password, full_name: fullName || null, role });
      setAddOpen(false);
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function onSave(e: FormEvent) {
    e.preventDefault();
    if (!editUser) return;
    setError(null);
    try {
      await updateUser(editUser.id, {
        full_name: editName || null,
        role: editRole,
        is_active: editActive,
      });
      setEditUser(null);
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-200">Users</h2>
          <p className="text-sm text-slate-500">
            Local accounts with role-based access.
            {isAdmin && " Click a user to edit their role or status."}
          </p>
        </div>
        {isAdmin && (
          <button onClick={openAdd} className={`${primaryBtn} whitespace-nowrap`}>
            Add user
          </button>
        )}
      </div>

      {error && !addOpen && editUser === null && (
        <p className="text-sm text-red-400">{error}</p>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900 text-slate-400">
            <tr>
              <th className="px-4 py-2 font-medium">Email</th>
              <th className="px-4 py-2 font-medium">Name</th>
              <th className="px-4 py-2 font-medium">Role</th>
              <th className="px-4 py-2 font-medium">Active</th>
              <th className="px-4 py-2 font-medium">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {loading ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={5}>
                  Loading…
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={5}>
                  No users.
                </td>
              </tr>
            ) : (
              usersPage.slice.map((u) => (
                <tr
                  key={u.id}
                  onClick={() => openEdit(u)}
                  className={`bg-slate-950 ${isAdmin ? "cursor-pointer hover:bg-slate-900" : ""}`}
                >
                  <td className="px-4 py-2 text-slate-100">
                    {u.email}
                    {u.id === user?.id && (
                      <span className="ml-2 text-xs text-slate-500">(you)</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-slate-300">{u.full_name ?? "-"}</td>
                  <td className="px-4 py-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${ROLE_BADGE[u.role] ?? ROLE_BADGE.auditor}`}>
                      {u.role}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`inline-block h-2.5 w-2.5 rounded-full ${u.is_active ? "bg-emerald-500" : "bg-slate-600"}`}
                    />
                  </td>
                  <td className="px-4 py-2 text-xs text-slate-400">
                    {new Date(u.created_at).toLocaleString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <Pagination
        page={usersPage.page}
        pageCount={usersPage.pageCount}
        total={usersPage.total}
        onPage={usersPage.setPage}
      />

      <Modal open={addOpen} onClose={() => setAddOpen(false)} title="Add user">
        <form onSubmit={onCreate} className="space-y-3">
          <div>
            <label className={labelClass}>Email</label>
            <input
              className={inputClass}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div>
            <label className={labelClass}>Password (min 8)</label>
            <input
              className={inputClass}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
            />
          </div>
          <div>
            <label className={labelClass}>Full name (optional)</label>
            <input
              className={inputClass}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>
          <div>
            <label className={labelClass}>Role</label>
            <select
              className={inputClass}
              value={role}
              onChange={(e) => setRole(e.target.value as Role)}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-slate-500">{ROLE_HINT[role]}</p>
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <div className="flex justify-end">
            <button type="submit" className={primaryBtn}>
              Create user
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        open={editUser !== null}
        onClose={() => setEditUser(null)}
        title={`Edit ${editUser?.email ?? ""}`}
      >
        <form onSubmit={onSave} className="space-y-3">
          <div>
            <label className={labelClass}>Full name</label>
            <input
              className={inputClass}
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
            />
          </div>
          <div>
            <label className={labelClass}>Role</label>
            <select
              className={inputClass}
              value={editRole}
              onChange={(e) => setEditRole(e.target.value as Role)}
              disabled={editingSelf}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-slate-500">{ROLE_HINT[editRole]}</p>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={editActive}
              onChange={(e) => setEditActive(e.target.checked)}
              disabled={editingSelf}
            />
            Active
          </label>
          {editingSelf && (
            <p className="text-xs text-amber-400">
              You cannot change your own role or active status.
            </p>
          )}
          {error && <p className="text-sm text-red-400">{error}</p>}
          <div className="flex justify-end">
            <button type="submit" className={primaryBtn}>
              Save changes
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
