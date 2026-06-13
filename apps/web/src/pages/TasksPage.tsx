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
  const [tasks, setTasks] = useState<Task[]>([]);
  const [users, setUsers] = useState<CurrentUser[]>([]);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");
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

  async function act(fn: () => Promise<unknown>) {
    setError(null);
    try {
      await fn();
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  function onFilter(f: (typeof FILTERS)[number]) {
    setFilter(f);
    void reload(f);
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-200">Tasks</h2>
        <div className="flex items-center gap-1">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => onFilter(f)}
              className={`rounded-lg px-3 py-1.5 text-sm ${
                filter === f
                  ? "bg-slate-800 text-emerald-400"
                  : "text-slate-400 hover:bg-slate-900"
              }`}
            >
              {f.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>

      <p className="text-sm text-slate-500">
        A task is opened automatically for every confirmed change, and can also
        be created manually. Link a task to Jira to track it externally.
      </p>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="overflow-hidden rounded-xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900 text-slate-400">
            <tr>
              <th className="px-4 py-2 font-medium">Title</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Assignee</th>
              <th className="px-4 py-2 font-medium">Source</th>
              <th className="px-4 py-2 font-medium">Jira</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {tasks.length === 0 ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={5}>
                  No tasks.
                </td>
              </tr>
            ) : (
              tasks.map((t) => (
                <tr key={t.id} className="bg-slate-950">
                  <td className="px-4 py-2 text-slate-100">{t.title}</td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-2">
                      <span className={`rounded-full px-2 py-0.5 text-xs ${STATUS_BADGE[t.status]}`}>
                        {t.status.replace("_", " ")}
                      </span>
                      <select
                        className={selectClass}
                        value={t.status}
                        onChange={(e) =>
                          act(() => updateTask(t.id, { status: e.target.value as TaskStatus }))
                        }
                      >
                        {STATUSES.map((s) => (
                          <option key={s} value={s}>
                            {s.replace("_", " ")}
                          </option>
                        ))}
                      </select>
                    </div>
                  </td>
                  <td className="px-4 py-2">
                    <select
                      className={selectClass}
                      value={t.assignee_id ?? ""}
                      onChange={(e) =>
                        act(() => updateTask(t.id, { assignee_id: e.target.value || null }))
                      }
                    >
                      <option value="">Unassigned</option>
                      {users.map((u) => (
                        <option key={u.id} value={u.id}>
                          {u.email}
                        </option>
                      ))}
                    </select>
                    {t.assignee_id && !users.length ? (
                      <span className="ml-2 text-xs text-slate-500">{ownerEmail(t.assignee_id)}</span>
                    ) : null}
                  </td>
                  <td className="px-4 py-2 text-xs text-slate-400">
                    {t.change_event_id ? "change" : "manual"}
                  </td>
                  <td className="px-4 py-2">
                    {t.jira_key ? (
                      <span className="flex items-center gap-2 text-xs">
                        <span className="font-mono text-slate-300">{t.jira_key}</span>
                        <button
                          onClick={() => act(() => syncTaskFromJira(t.id))}
                          className="text-sky-400 hover:text-sky-300"
                        >
                          Sync
                        </button>
                      </span>
                    ) : (
                      <button
                        onClick={() => act(() => linkTaskToJira(t.id))}
                        className="text-xs text-emerald-400 hover:text-emerald-300"
                      >
                        Link to Jira
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
