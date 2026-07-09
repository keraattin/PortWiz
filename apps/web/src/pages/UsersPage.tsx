import { type FormEvent, useEffect, useState } from "react";
import {
  type CurrentUser,
  type Role,
  createUser,
  listUsers,
  updateUser,
} from "../api/client";
import { inputClass } from "../components/formStyles";
import { useErrorMessage } from "../i18n/useErrorMessage";
import { useAuth } from "../auth/AuthContext";
import Button from "../components/Button";
import Modal from "../components/Modal";
import PageHeader from "../components/PageHeader";
import Pagination, { usePagination } from "../components/Pagination";
import RoleMatrix from "../components/RoleMatrix";
import SearchInput from "../components/SearchInput";
import { type Column, TableHead, processRows, useColumnFilters } from "../components/tableView";
import { useSort } from "../components/useSort";
import { useToast } from "../components/Toast";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

const ROLES: Role[] = ["admin", "operator", "auditor"];

const ROLE_BADGE: Record<string, string> = {
  admin: "bg-red-900 text-red-300",
  operator: "bg-sky-900 text-sky-300",
  auditor: "bg-slate-700 text-slate-300",
};

const labelClass = "block text-sm text-slate-300";

export default function UsersPage() {
  const { user } = useAuth();
  const toast = useToast();
  const { t } = useI18n();
  const errorMessage = useErrorMessage();
  const isAdmin = user?.role === "admin";

  const [users, setUsers] = useState<CurrentUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { sort, toggleSort } = useSort();
  const { filters, setFilter } = useColumnFilters();
  const [search, setSearch] = useState("");
  const columns: Column<CurrentUser>[] = [
    { key: "email", label: t("users.col.email"), filter: "text", get: (u) => u.email },
    { key: "name", label: t("users.col.name"), filter: "text", get: (u) => u.full_name ?? "" },
    {
      key: "role",
      label: t("users.col.role"),
      filter: ROLES.map((r) => ({ value: r, label: t(`role.${r}` as TKey) })),
      get: (u) => u.role,
    },
    {
      key: "active",
      label: t("users.col.active"),
      filter: [
        { value: "active", label: t("common.active") },
        { value: "inactive", label: t("common.inactive") },
      ],
      get: (u) => (u.is_active ? "active" : "inactive"),
    },
    { key: "created", label: t("users.col.created"), get: (u) => u.created_at },
  ];
  const processed = processRows(users, columns, sort, filters, search);
  const usersPage = usePagination(processed, 15);
  const onFilter = (key: string, v: string) => {
    setFilter(key, v);
    usersPage.setPage(0);
  };

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
      toast.success(t("users.created"));
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
      toast.success(t("users.updated"));
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("users.title")}
        subtitle={
          <>
            {t("users.subtitle")}
            {isAdmin && t("users.subtitleAdmin")}
          </>
        }
        actions={
          isAdmin && (
            <Button onClick={openAdd} className="whitespace-nowrap">
              {t("users.add")}
            </Button>
          )
        }
      />

      {error && !addOpen && editUser === null && (
        <p className="text-sm text-red-400">{error}</p>
      )}

      <div className="flex justify-end">
        <SearchInput value={search} onChange={setSearch} />
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <TableHead
            columns={columns}
            sort={sort}
            toggleSort={toggleSort}
            filters={filters}
            setFilter={onFilter}
          />
          <tbody className="divide-y divide-slate-800">
            {loading ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={5}>
                  {t("common.loading")}
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={5}>
                  {t("users.empty")}
                </td>
              </tr>
            ) : processed.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-center text-slate-500" colSpan={5}>
                  {t("common.noData")}
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
                      <span className="ml-2 text-xs text-slate-500">{t("users.you")}</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-slate-300">{u.full_name ?? "-"}</td>
                  <td className="px-4 py-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${ROLE_BADGE[u.role] ?? ROLE_BADGE.auditor}`}>
                      {t(`role.${u.role}` as TKey)}
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
        pageSize={usersPage.pageSize}
        onPageSize={usersPage.setPageSize}
      />

      <Modal open={addOpen} onClose={() => setAddOpen(false)} title={t("users.add")}>
        <form onSubmit={onCreate} className="space-y-3">
          <div>
            <label className={labelClass}>{t("users.f.email")}</label>
            <input
              className={inputClass}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div>
            <label className={labelClass}>{t("users.f.password")}</label>
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
            <label className={labelClass}>{t("users.f.fullName")}</label>
            <input
              className={inputClass}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>
          <div>
            <label className={labelClass}>{t("users.f.role")}</label>
            <select
              className={inputClass}
              value={role}
              onChange={(e) => setRole(e.target.value as Role)}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {t(`role.${r}` as TKey)}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-slate-500">{t(`roleHint.${role}` as TKey)}</p>
          </div>
          <RoleMatrix />
          {error && <p className="text-sm text-red-400">{error}</p>}
          <div className="flex justify-end">
            <Button type="submit">
              {t("users.create")}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={editUser !== null}
        onClose={() => setEditUser(null)}
        title={t("users.editTitle", { email: editUser?.email ?? "" })}
      >
        <form onSubmit={onSave} className="space-y-3">
          <div>
            <label className={labelClass}>{t("users.f.fullNameEdit")}</label>
            <input
              className={inputClass}
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
            />
          </div>
          <div>
            <label className={labelClass}>{t("users.f.role")}</label>
            <select
              className={inputClass}
              value={editRole}
              onChange={(e) => setEditRole(e.target.value as Role)}
              disabled={editingSelf}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {t(`role.${r}` as TKey)}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-slate-500">{t(`roleHint.${editRole}` as TKey)}</p>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={editActive}
              onChange={(e) => setEditActive(e.target.checked)}
              disabled={editingSelf}
            />
            {t("users.f.active")}
          </label>
          {editingSelf && <p className="text-xs text-amber-400">{t("users.cannotEditSelf")}</p>}
          <RoleMatrix />
          {error && <p className="text-sm text-red-400">{error}</p>}
          <div className="flex justify-end">
            <Button type="submit">
              {t("users.saveChanges")}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
