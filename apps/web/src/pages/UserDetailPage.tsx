import { type FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  type AuditEvent,
  type CurrentUser,
  type Role,
  getUser,
  listAudit,
  updateUser,
} from "../api/client";
import { inputClass } from "../components/formStyles";
import { useErrorMessage } from "../i18n/useErrorMessage";
import { useAuth } from "../auth/AuthContext";
import Button from "../components/Button";
import FormField from "../components/FormField";
import Pagination, { usePagination } from "../components/Pagination";
import { useToast } from "../components/Toast";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

const ROLES: Role[] = ["admin", "operator", "auditor"];
const ROLE_BADGE: Record<string, string> = {
  admin: "bg-red-900 text-red-300",
  operator: "bg-sky-900 text-sky-300",
  auditor: "bg-slate-700 text-slate-300",
};

type Translate = (key: TKey, vars?: Record<string, string | number>) => string;

// A localised label for an audit action, falling back to the raw code.
function auditLabel(action: string, t: Translate): string {
  const key = `audit.action.${action.replace(/\./g, "_")}` as TKey;
  const label = t(key);
  return label === key ? action : label;
}

export default function UserDetailPage() {
  const { id = "" } = useParams();
  const { t } = useI18n();
  const { user: me } = useAuth();
  const toast = useToast();
  const errorMessage = useErrorMessage();

  const [u, setU] = useState<CurrentUser | null>(null);
  const [activity, setActivity] = useState<AuditEvent[]>([]);
  const [actionFilter, setActionFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("operator");
  const [active, setActive] = useState(true);

  const editingSelf = u?.id === me?.id;

  async function load() {
    setLoading(true);
    try {
      const user = await getUser(id);
      setU(user);
      setName(user.full_name ?? "");
      setRole(user.role as Role);
      setActive(user.is_active);
      // The user's own actions and logins, newest first.
      const page = await listAudit({ actor_email: user.email, limit: 100 });
      setActivity(page.events);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function onSave(e: FormEvent) {
    e.preventDefault();
    if (!u) return;
    try {
      const updated = await updateUser(u.id, {
        full_name: name || null,
        role,
        is_active: active,
      });
      setU(updated);
      toast.success(t("users.updated"));
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  // A dropdown of the action labels present, plus client-side paging over the
  // loaded window, so a busy user's activity stays browsable.
  const actionOptions = [...new Set(activity.map((a) => a.action))]
    .map((a) => ({ value: a, label: auditLabel(a, t) }))
    .sort((x, y) => x.label.localeCompare(y.label));
  const filteredActivity = activity.filter((a) => !actionFilter || a.action === actionFilter);
  const actPage = usePagination(filteredActivity, 15);

  const back = (
    <Link to="/users" className="text-sm text-slate-400 hover:text-slate-200">
      ← {t("userDetail.back")}
    </Link>
  );

  if (loading) {
    return (
      <div className="space-y-4">
        {back}
        <p className="text-sm text-slate-500">{t("common.loading")}</p>
      </div>
    );
  }
  if (!u) {
    return (
      <div className="space-y-4">
        {back}
        <p className="text-sm text-red-400">{error ?? t("userDetail.notFound")}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {back}

      <div>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold text-slate-100">{u.email}</h1>
          <span className={`rounded-full px-2 py-0.5 text-xs ${ROLE_BADGE[u.role] ?? ROLE_BADGE.auditor}`}>
            {t(`role.${u.role}` as TKey)}
          </span>
          <span
            className={`inline-flex items-center gap-1.5 text-xs ${
              u.is_active ? "text-emerald-400" : "text-slate-500"
            }`}
          >
            <span
              className={`inline-block h-2 w-2 rounded-full ${u.is_active ? "bg-emerald-500" : "bg-slate-600"}`}
            />
            {u.is_active ? t("common.active") : t("common.inactive")}
          </span>
          {u.id === me?.id && <span className="text-xs text-slate-500">{t("users.you")}</span>}
        </div>
        <p className="mt-1 text-xs text-slate-500">
          {t("users.col.created")}: {new Date(u.created_at).toLocaleString()}
        </p>
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
        <form onSubmit={onSave} className="space-y-3">
          <p className="text-sm font-medium text-slate-300">{t("userDetail.edit")}</p>
          <FormField label={t("users.f.fullNameEdit")}>
            <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} />
          </FormField>
          <FormField label={t("users.f.role")} hint={t(`roleHint.${role}` as TKey)}>
            <select
              className={inputClass}
              value={role}
              onChange={(e) => setRole(e.target.value as Role)}
              disabled={editingSelf}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {t(`role.${r}` as TKey)}
                </option>
              ))}
            </select>
          </FormField>
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={active}
              onChange={(e) => setActive(e.target.checked)}
              disabled={editingSelf}
            />
            {t("users.f.active")}
          </label>
          {editingSelf && <p className="text-xs text-amber-400">{t("users.cannotEditSelf")}</p>}
          <div className="flex justify-end">
            <Button type="submit">{t("users.saveChanges")}</Button>
          </div>
        </form>
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-medium text-slate-300">{t("userDetail.activity")}</p>
          {activity.length > 0 && (
            <select
              value={actionFilter}
              onChange={(e) => {
                setActionFilter(e.target.value);
                actPage.setPage(0);
              }}
              className="rounded-md border border-slate-700 bg-slate-800 px-2 py-1 text-xs text-slate-100 outline-none focus:border-emerald-500"
            >
              <option value="">{t("filters.all")}</option>
              {actionOptions.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          )}
        </div>
        {activity.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-600">{t("userDetail.noActivity")}</p>
        ) : filteredActivity.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-600">{t("common.noData")}</p>
        ) : (
          <>
            <ol className="space-y-2 text-sm">
              {actPage.slice.map((a) => (
                <li
                  key={a.seq}
                  className="flex flex-wrap items-center gap-2 border-b border-slate-800/60 py-1"
                >
                  <span className="text-slate-200" title={a.action}>
                    {auditLabel(a.action, t)}
                  </span>
                  {a.target_type && (
                    <span className="font-mono text-xs text-slate-500">
                      {a.target_type}:{(a.target_id ?? "").slice(0, 8)}
                    </span>
                  )}
                  <span className="ml-auto text-xs text-slate-500">
                    {new Date(a.created_at).toLocaleString()}
                  </span>
                </li>
              ))}
            </ol>
            <Pagination
              page={actPage.page}
              pageCount={actPage.pageCount}
              total={actPage.total}
              onPage={actPage.setPage}
              pageSize={actPage.pageSize}
              onPageSize={actPage.setPageSize}
            />
          </>
        )}
      </div>
    </div>
  );
}
