import { useEffect, useState } from "react";
import {
  ApiError,
  type CurrentUser,
  type Task,
  type TaskStatus,
  linkTaskToJira,
  listTasks,
  listUsers,
  syncTaskFromJira,
  updateTask,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import PageHeader from "../components/PageHeader";
import Pagination, { usePagination } from "../components/Pagination";
import SearchInput from "../components/SearchInput";
import { useToast } from "../components/Toast";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

function errorMessage(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong";
}

const STATUSES: TaskStatus[] = ["open", "in_progress", "done", "cancelled"];
const FILTERS = ["all", "open", "in_progress", "done", "cancelled"] as const;

const STATUS_BADGE: Record<TaskStatus, string> = {
  open: "bg-sky-900 text-sky-300",
  in_progress: "bg-amber-900 text-amber-300",
  done: "bg-emerald-900 text-emerald-300",
  cancelled: "bg-slate-700 text-slate-400",
};

const selectClass =
  "rounded-lg border border-slate-700 bg-slate-800 px-2 py-1 text-xs text-slate-100 outline-none focus:border-emerald-500";

export default function TasksPage() {
  const { user } = useAuth();
  const toast = useToast();
  const { t } = useI18n();
  const canWrite = user?.role === "admin" || user?.role === "operator";
  const [tasks, setTasks] = useState<Task[]>([]);
  const [users, setUsers] = useState<CurrentUser[]>([]);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function reload(f = filter) {
    setError(null);
    try {
      setTasks(await listTasks(f === "all" ? undefined : { status: f }));
    } catch (e) {
      setError(errorMessage(e));
    }
    try {
      setUsers(await listUsers());
    } catch {
      // Listing users requires admin/auditor; operators just see no names.
    }
  }

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ownerEmail = (id: string | null) =>
    id ? (users.find((u) => u.id === id)?.email ?? "unknown") : "";

  const q = query.trim().toLowerCase();
  const filteredTasks = q
    ? tasks.filter((task) =>
        [task.title, ownerEmail(task.assignee_id), task.jira_key ?? ""].some((v) =>
          v.toLowerCase().includes(q),
        ),
      )
    : tasks;
  const tasksPage = usePagination(filteredTasks, 15);

  async function act(fn: () => Promise<unknown>) {
    setError(null);
    try {
      await fn();
      toast.success(t("tasks.updated"));
      await reload();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  function onFilter(f: (typeof FILTERS)[number]) {
    setFilter(f);
    tasksPage.setPage(0);
    void reload(f);
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("tasks.title")}
        actions={FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => onFilter(f)}
            className={`rounded-lg px-3 py-1.5 text-sm ${
              filter === f
                ? "bg-slate-800 text-emerald-400"
                : "text-slate-400 hover:bg-slate-900"
            }`}
          >
            {f === "all" ? t("filters.all") : t(`taskStatus.${f}` as TKey)}
          </button>
        ))}
      />

      <p className="text-sm text-slate-500">{t("tasks.subtitle")}</p>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {tasks.length > 0 && (
        <div className="flex justify-end">
          <SearchInput
            value={query}
            onChange={(v) => {
              setQuery(v);
              tasksPage.setPage(0);
            }}
          />
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900 text-slate-400">
            <tr>
              <th className="px-4 py-2 font-medium">{t("tasks.col.title")}</th>
              <th className="px-4 py-2 font-medium">{t("tasks.col.status")}</th>
              <th className="px-4 py-2 font-medium">{t("tasks.col.assignee")}</th>
              <th className="px-4 py-2 font-medium">{t("tasks.col.source")}</th>
              <th className="px-4 py-2 font-medium">{t("tasks.col.jira")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {tasks.length === 0 ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={5}>
                  {t("tasks.empty")}
                </td>
              </tr>
            ) : filteredTasks.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-center text-slate-500" colSpan={5}>
                  {t("common.noData")}
                </td>
              </tr>
            ) : (
              tasksPage.slice.map((task) => (
                <tr key={task.id} className="bg-slate-950">
                  <td className="px-4 py-2 text-slate-100">{task.title}</td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-2">
                      <span className={`rounded-full px-2 py-0.5 text-xs ${STATUS_BADGE[task.status]}`}>
                        {t(`taskStatus.${task.status}` as TKey)}
                      </span>
                      {canWrite && (
                        <select
                          className={selectClass}
                          value={task.status}
                          onChange={(e) =>
                            act(() => updateTask(task.id, { status: e.target.value as TaskStatus }))
                          }
                        >
                          {STATUSES.map((s) => (
                            <option key={s} value={s}>
                              {t(`taskStatus.${s}` as TKey)}
                            </option>
                          ))}
                        </select>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-2">
                    {canWrite ? (
                      <select
                        className={selectClass}
                        value={task.assignee_id ?? ""}
                        onChange={(e) =>
                          act(() => updateTask(task.id, { assignee_id: e.target.value || null }))
                        }
                      >
                        <option value="">{t("tasks.unassigned")}</option>
                        {users.map((u) => (
                          <option key={u.id} value={u.id}>
                            {u.email}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className="text-xs text-slate-300">
                        {task.assignee_id ? ownerEmail(task.assignee_id) : t("tasks.unassigned")}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-xs text-slate-400">
                    {task.change_event_id ? t("tasks.source.change") : t("tasks.source.manual")}
                  </td>
                  <td className="px-4 py-2">
                    {task.jira_key ? (
                      <span className="flex items-center gap-2 text-xs">
                        <span className="font-mono text-slate-300">{task.jira_key}</span>
                        {canWrite && (
                          <button
                            onClick={() => act(() => syncTaskFromJira(task.id))}
                            className="text-sky-400 hover:text-sky-300"
                          >
                            {t("tasks.sync")}
                          </button>
                        )}
                      </span>
                    ) : canWrite ? (
                      <button
                        onClick={() => act(() => linkTaskToJira(task.id))}
                        className="text-xs text-emerald-400 hover:text-emerald-300"
                      >
                        {t("tasks.linkJira")}
                      </button>
                    ) : (
                      <span className="text-xs text-slate-600">-</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <Pagination
        page={tasksPage.page}
        pageCount={tasksPage.pageCount}
        total={tasksPage.total}
        onPage={tasksPage.setPage}
      />
    </div>
  );
}
