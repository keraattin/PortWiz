import { useEffect, useState } from "react";
import {
  type CurrentUser,
  type Task,
  type TaskStatus,
  linkTaskToJira,
  listTasks,
  listUsers,
  syncTaskFromJira,
  updateTask,
} from "../api/client";
import { useErrorMessage } from "../i18n/useErrorMessage";
import { useAuth } from "../auth/AuthContext";
import PageHeader from "../components/PageHeader";
import Pagination, { usePagination } from "../components/Pagination";
import SearchInput from "../components/SearchInput";
import { type Column, TableHead, processRows, useColumnFilters } from "../components/tableView";
import { useSort } from "../components/useSort";
import { useToast } from "../components/Toast";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

const STATUSES: TaskStatus[] = ["open", "in_progress", "done", "cancelled"];
const FILTERS = ["all", "open", "in_progress", "done", "cancelled"] as const;
// Rank so status sorts by lifecycle order, not alphabetically.
const STATUS_RANK: Record<string, number> = {
  open: 0,
  in_progress: 1,
  done: 2,
  cancelled: 3,
};

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
  const errorMessage = useErrorMessage();
  const canWrite = user?.role === "admin" || user?.role === "operator";
  const [tasks, setTasks] = useState<Task[]>([]);
  const [users, setUsers] = useState<CurrentUser[]>([]);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");
  const { sort, toggleSort } = useSort();
  const { filters, setFilter: setColFilter } = useColumnFilters();
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function reload(f = filter) {
    setError(null);
    setLoading(true);
    try {
      setTasks(await listTasks(f === "all" ? undefined : { status: f }));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
    try {
      setUsers(await listUsers());
    } catch {
      // Best-effort: if the user list can't be read, assignee names just show blank.
    }
  }

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ownerEmail = (id: string | null) =>
    id ? (users.find((u) => u.id === id)?.email ?? "unknown") : "";

  const columns: Column<Task>[] = [
    { key: "title", label: t("tasks.col.title"), filter: "text", get: (task) => task.title },
    {
      key: "status",
      label: t("tasks.col.status"),
      filter: STATUSES.map((s) => ({ value: s, label: t(`taskStatus.${s}` as TKey) })),
      get: (task) => task.status,
      rank: STATUS_RANK,
    },
    {
      key: "assignee",
      label: t("tasks.col.assignee"),
      filter: "text",
      get: (task) => ownerEmail(task.assignee_id),
    },
    {
      key: "source",
      label: t("tasks.col.source"),
      filter: [
        { value: "change", label: t("tasks.source.change") },
        { value: "manual", label: t("tasks.source.manual") },
      ],
      get: (task) => (task.change_event_id ? "change" : "manual"),
    },
    { key: "jira", label: t("tasks.col.jira"), filter: "text", get: (task) => task.jira_key ?? "" },
  ];
  const processed = processRows(tasks, columns, sort, filters, search);
  const tasksPage = usePagination(processed, 15);
  const onColFilter = (key: string, v: string) => {
    setColFilter(key, v);
    tasksPage.setPage(0);
  };

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
        docsGuide="evidence"
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
            setFilter={onColFilter}
          />
          <tbody className="divide-y divide-slate-800">
            {loading ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={5}>
                  {t("common.loading")}
                </td>
              </tr>
            ) : tasks.length === 0 ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={5}>
                  {t("tasks.empty")}
                </td>
              </tr>
            ) : processed.length === 0 ? (
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
        pageSize={tasksPage.pageSize}
        onPageSize={tasksPage.setPageSize}
      />
    </div>
  );
}
