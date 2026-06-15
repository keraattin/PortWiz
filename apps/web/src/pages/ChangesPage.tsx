import { useEffect, useState } from "react";
import {
  ApiError,
  type ChangeEvent,
  type ChangeStatus,
  type ChangeType,
  type PortSnapshot,
  listChanges,
  updateChangeStatus,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";

function errorMessage(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong";
}

const CHANGE_BADGE: Record<ChangeType, string> = {
  opened: "bg-emerald-900 text-emerald-300",
  closed: "bg-red-900 text-red-300",
  service_changed: "bg-amber-900 text-amber-300",
  version_changed: "bg-sky-900 text-sky-300",
};

const SEVERITY_BADGE: Record<string, string> = {
  high: "bg-red-900 text-red-300",
  medium: "bg-amber-900 text-amber-300",
  low: "bg-slate-700 text-slate-300",
};

const STATUS_BADGE: Record<ChangeStatus, string> = {
  open: "bg-sky-900 text-sky-300",
  acknowledged: "bg-amber-900 text-amber-300",
  resolved: "bg-emerald-900 text-emerald-300",
};

const STATUS_FILTERS = ["all", "open", "acknowledged", "resolved"] as const;

function describe(snapshot: PortSnapshot): string {
  if (snapshot.state !== "open") {
    return "closed";
  }
  const detail = [snapshot.service, snapshot.version].filter(Boolean).join(" ");
  return detail ? `open (${detail})` : "open";
}

export default function ChangesPage() {
  const { user } = useAuth();
  const canWrite = user?.role === "admin" || user?.role === "operator";
  const [changes, setChanges] = useState<ChangeEvent[]>([]);
  const [statusFilter, setStatusFilter] = useState<(typeof STATUS_FILTERS)[number]>("all");
  const [error, setError] = useState<string | null>(null);

  async function reload(filter = statusFilter) {
    try {
      setChanges(await listChanges(filter === "all" ? undefined : { status: filter }));
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onStatusChange(id: string, status: ChangeStatus) {
    setError(null);
    try {
      await updateChangeStatus(id, status);
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  function onFilter(filter: (typeof STATUS_FILTERS)[number]) {
    setStatusFilter(filter);
    void reload(filter);
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-200">Confirmed changes</h2>
        <div className="flex items-center gap-2">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => onFilter(f)}
              className={`rounded-lg px-3 py-1.5 text-sm capitalize ${
                statusFilter === f
                  ? "bg-slate-800 text-emerald-400"
                  : "text-slate-400 hover:bg-slate-900"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <p className="text-sm text-slate-500">
        Only changes confirmed across consecutive scans appear here, so network
        flapping does not raise noise.
      </p>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="overflow-hidden rounded-xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900 text-slate-400">
            <tr>
              <th className="px-4 py-2 font-medium">Detected</th>
              <th className="px-4 py-2 font-medium">Host</th>
              <th className="px-4 py-2 font-medium">Change</th>
              <th className="px-4 py-2 font-medium">Before / After</th>
              <th className="px-4 py-2 font-medium">Severity</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {changes.length === 0 ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={7}>
                  No changes recorded.
                </td>
              </tr>
            ) : (
              changes.map((c) => (
                <tr key={c.id} className="bg-slate-950">
                  <td className="px-4 py-2 text-xs text-slate-400">
                    {new Date(c.detected_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2 font-mono text-slate-100">
                    {c.ip}:{c.port}/{c.protocol}
                  </td>
                  <td className="px-4 py-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${CHANGE_BADGE[c.change_type]}`}>
                      {c.change_type.replace("_", " ")}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-xs text-slate-300">
                    <span className="text-slate-500">{describe(c.before)}</span>
                    <span className="px-1 text-slate-500">to</span>
                    <span className="text-slate-100">{describe(c.after)}</span>
                  </td>
                  <td className="px-4 py-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${SEVERITY_BADGE[c.severity] ?? SEVERITY_BADGE.low}`}>
                      {c.severity}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${STATUS_BADGE[c.status]}`}>
                      {c.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right">
                    {canWrite && c.status !== "acknowledged" && (
                      <button
                        onClick={() => onStatusChange(c.id, "acknowledged")}
                        className="mr-3 text-xs text-amber-400 hover:text-amber-300"
                      >
                        Acknowledge
                      </button>
                    )}
                    {canWrite && c.status !== "resolved" && (
                      <button
                        onClick={() => onStatusChange(c.id, "resolved")}
                        className="text-xs text-emerald-400 hover:text-emerald-300"
                      >
                        Resolve
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
