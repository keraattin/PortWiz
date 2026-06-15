import { type FormEvent, useEffect, useState } from "react";
import {
  ApiError,
  type Agent,
  type EnrolledAgent,
  deleteAgent,
  enrollAgent,
  listAgents,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";

function errorMessage(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong";
}

// An agent heartbeats periodically; treat a recent heartbeat as "online".
const ONLINE_WINDOW_MS = 2 * 60 * 1000;

function agentStatus(lastSeen: string | null): { label: string; cls: string } {
  if (!lastSeen) return { label: "never seen", cls: "bg-slate-700 text-slate-400" };
  const ageMs = Date.now() - new Date(lastSeen).getTime();
  if (ageMs < ONLINE_WINDOW_MS) return { label: "online", cls: "bg-emerald-900 text-emerald-300" };
  return { label: "offline", cls: "bg-red-900 text-red-300" };
}

const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500";

export default function AgentsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [enrolled, setEnrolled] = useState<EnrolledAgent | null>(null);
  const [copied, setCopied] = useState(false);

  async function reload() {
    setLoading(true);
    try {
      setAgents(await listAgents());
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
  }, []);

  async function onEnroll(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setCopied(false);
    try {
      const result = await enrollAgent(name);
      setEnrolled(result);
      setName("");
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function onDelete(id: string) {
    if (!window.confirm("Delete this agent? Its token will stop working.")) return;
    setError(null);
    try {
      await deleteAgent(id);
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-200">Scan agents</h2>
        <p className="text-sm text-slate-500">
          Agents are the distributed scanners you deploy per VLAN. Enroll one here,
          then run it with its token (set <code className="text-slate-400">PORTWIZ_AGENT_TOKEN</code>).
          A scan run stays pending until an online agent picks it up.
        </p>
      </div>

      {enrolled && (
        <div className="space-y-2 rounded-xl border border-emerald-800 bg-emerald-950/40 p-4">
          <p className="text-sm text-emerald-300">
            Agent "{enrolled.name}" enrolled. Copy its token now — it will not be shown again.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 overflow-x-auto rounded bg-slate-900 px-3 py-2 font-mono text-xs text-slate-200">
              {enrolled.token}
            </code>
            <button
              onClick={() => {
                void navigator.clipboard?.writeText(enrolled.token);
                setCopied(true);
              }}
              className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-500"
            >
              {copied ? "Copied" : "Copy"}
            </button>
            <button
              onClick={() => setEnrolled(null)}
              className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 hover:bg-slate-800"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {isAdmin && (
        <form onSubmit={onEnroll} className="flex gap-3">
          <input
            className={inputClass}
            placeholder="Agent name (e.g. vlan10-scanner)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <button
            type="submit"
            className="whitespace-nowrap rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
          >
            Enroll agent
          </button>
        </form>
      )}

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="overflow-hidden rounded-xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900 text-slate-400">
            <tr>
              <th className="px-4 py-2 font-medium">Name</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Last seen</th>
              <th className="px-4 py-2 font-medium">Enrolled</th>
              {isAdmin && <th className="px-4 py-2"></th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {loading ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={5}>
                  Loading…
                </td>
              </tr>
            ) : agents.length === 0 ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={5}>
                  No agents enrolled yet. Enroll one to start scanning.
                </td>
              </tr>
            ) : (
              agents.map((a) => {
                const status = agentStatus(a.last_seen_at);
                return (
                  <tr key={a.id} className="bg-slate-950">
                    <td className="px-4 py-2 text-slate-100">{a.name}</td>
                    <td className="px-4 py-2">
                      <span className={`rounded-full px-2 py-0.5 text-xs ${status.cls}`}>
                        {status.label}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-400">
                      {a.last_seen_at ? new Date(a.last_seen_at).toLocaleString() : "-"}
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-400">
                      {new Date(a.created_at).toLocaleString()}
                    </td>
                    {isAdmin && (
                      <td className="px-4 py-2 text-right">
                        <button
                          onClick={() => onDelete(a.id)}
                          className="text-xs text-red-400 hover:text-red-300"
                        >
                          Delete
                        </button>
                      </td>
                    )}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
