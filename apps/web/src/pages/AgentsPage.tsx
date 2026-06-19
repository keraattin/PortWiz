import { type FormEvent, useEffect, useState } from "react";
import {
  ApiError,
  type Agent,
  type EnrolledAgent,
  deleteAgent,
  enrollAgent,
  listAgents,
  updateAgent,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import Modal from "../components/Modal";
import PageHeader from "../components/PageHeader";
import { useToast } from "../components/Toast";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

function errorMessage(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong";
}

// An agent heartbeats periodically; treat a recent heartbeat as "online".
const ONLINE_WINDOW_MS = 2 * 60 * 1000;

// Returns the i18n key for the status label plus its badge classes.
function agentStatus(lastSeen: string | null): { key: TKey; cls: string } {
  if (!lastSeen) return { key: "agents.status.neverSeen", cls: "bg-slate-700 text-slate-400" };
  const ageMs = Date.now() - new Date(lastSeen).getTime();
  if (ageMs < ONLINE_WINDOW_MS)
    return { key: "agents.status.online", cls: "bg-emerald-900 text-emerald-300" };
  return { key: "agents.status.offline", cls: "bg-red-900 text-red-300" };
}

const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500";

export default function AgentsPage() {
  const { user } = useAuth();
  const toast = useToast();
  const { t } = useI18n();
  const isAdmin = user?.role === "admin";

  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [segment, setSegment] = useState("");
  const [enrolled, setEnrolled] = useState<EnrolledAgent | null>(null);
  const [copied, setCopied] = useState(false);

  const [editAgent, setEditAgent] = useState<Agent | null>(null);
  const [editSegment, setEditSegment] = useState("");
  const [editEnabled, setEditEnabled] = useState(true);

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
      const result = await enrollAgent(name, segment || null);
      setEnrolled(result);
      setName("");
      setSegment("");
      toast.success(t("agents.enrolled"));
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function onDelete(id: string) {
    if (!window.confirm(t("agents.confirmDelete"))) return;
    try {
      await deleteAgent(id);
      toast.success(t("agents.deleted"));
      await reload();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  function openEdit(a: Agent) {
    if (!isAdmin) return;
    setError(null);
    setEditAgent(a);
    setEditSegment(a.segment ?? "");
    setEditEnabled(a.enabled);
  }

  async function onSaveEdit(e: FormEvent) {
    e.preventDefault();
    if (!editAgent) return;
    setError(null);
    try {
      await updateAgent(editAgent.id, {
        segment: editSegment || null,
        enabled: editEnabled,
      });
      setEditAgent(null);
      toast.success(t("agents.updated"));
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title={t("agents.title")} subtitle={t("agents.subtitle")} />

      {enrolled && (
        <div className="space-y-2 rounded-xl border border-emerald-800 bg-emerald-950/40 p-4">
          <p className="text-sm text-emerald-300">
            {t("agents.enrolledNotice", { name: enrolled.name })}
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
              {copied ? t("agents.copied") : t("agents.copy")}
            </button>
            <button
              onClick={() => setEnrolled(null)}
              className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 hover:bg-slate-800"
            >
              {t("agents.dismiss")}
            </button>
          </div>
        </div>
      )}

      {isAdmin && (
        <form onSubmit={onEnroll} className="flex flex-wrap gap-3">
          <input
            className={`${inputClass} flex-1`}
            placeholder={t("agents.namePlaceholder")}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <input
            className={`${inputClass} sm:w-48`}
            placeholder={t("agents.segmentPlaceholder")}
            value={segment}
            onChange={(e) => setSegment(e.target.value)}
          />
          <button
            type="submit"
            className="whitespace-nowrap rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
          >
            {t("agents.enroll")}
          </button>
        </form>
      )}

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="overflow-hidden rounded-xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900 text-slate-400">
            <tr>
              <th className="px-4 py-2 font-medium">{t("agents.col.name")}</th>
              <th className="px-4 py-2 font-medium">{t("agents.col.segment")}</th>
              <th className="px-4 py-2 font-medium">{t("agents.col.status")}</th>
              <th className="px-4 py-2 font-medium">{t("agents.col.lastSeen")}</th>
              <th className="px-4 py-2 font-medium">{t("agents.col.enrolledAt")}</th>
              {isAdmin && <th className="px-4 py-2"></th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {loading ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={6}>
                  {t("common.loading")}
                </td>
              </tr>
            ) : agents.length === 0 ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={6}>
                  {t("agents.empty")}
                </td>
              </tr>
            ) : (
              agents.map((a) => {
                const status = agentStatus(a.last_seen_at);
                return (
                  <tr
                    key={a.id}
                    onClick={() => openEdit(a)}
                    className={`bg-slate-950 ${isAdmin ? "cursor-pointer hover:bg-slate-900" : ""}`}
                  >
                    <td className="px-4 py-2 text-slate-100">{a.name}</td>
                    <td className="px-4 py-2 text-slate-300">
                      {a.segment ?? <span className="text-slate-600">{t("agents.any")}</span>}
                    </td>
                    <td className="px-4 py-2">
                      {a.enabled ? (
                        <span className={`rounded-full px-2 py-0.5 text-xs ${status.cls}`}>
                          {t(status.key)}
                        </span>
                      ) : (
                        <span className="rounded-full bg-slate-700 px-2 py-0.5 text-xs text-slate-400">
                          {t("agents.status.disabled")}
                        </span>
                      )}
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
                          onClick={(e) => {
                            e.stopPropagation();
                            void onDelete(a.id);
                          }}
                          className="text-xs text-red-400 hover:text-red-300"
                        >
                          {t("common.delete")}
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

      <Modal
        open={editAgent !== null}
        onClose={() => setEditAgent(null)}
        title={t("agents.editTitle", { name: editAgent?.name ?? "" })}
      >
        <form onSubmit={onSaveEdit} className="space-y-3">
          <div>
            <label className="block text-sm text-slate-300">{t("agents.f.segment")}</label>
            <input
              className={inputClass}
              placeholder={t("agents.f.segmentPlaceholder")}
              value={editSegment}
              onChange={(e) => setEditSegment(e.target.value)}
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={editEnabled}
              onChange={(e) => setEditEnabled(e.target.checked)}
            />
            {t("agents.f.enabled")}
          </label>
          <p className="text-xs text-slate-500">{t("agents.f.enabledHint")}</p>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <div className="flex justify-end">
            <button
              type="submit"
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
            >
              {t("agents.saveChanges")}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
