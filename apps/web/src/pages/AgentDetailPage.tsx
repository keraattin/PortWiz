import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ApiError,
  type Agent,
  deleteAgent,
  fetchSettings,
  getAgent,
  rotateAgentToken,
  updateAgent,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import AgentDeployPanel from "../components/AgentDeployPanel";
import Button from "../components/Button";
import { useToast } from "../components/Toast";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";
import { absoluteTime, timeAgo } from "../i18n/relativeTime";

function errorMessage(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong";
}

const DEFAULT_ONLINE_MS = 2 * 60 * 1000;

function statusInfo(a: Agent, windowMs: number): { key: TKey; cls: string } {
  if (!a.enabled) return { key: "agents.status.disabled", cls: "bg-slate-700 text-slate-400" };
  if (!a.last_seen_at)
    return { key: "agents.status.neverSeen", cls: "bg-slate-700 text-slate-400" };
  return Date.now() - new Date(a.last_seen_at).getTime() < windowMs
    ? { key: "agents.status.online", cls: "bg-emerald-900 text-emerald-300" }
    : { key: "agents.status.offline", cls: "bg-red-900 text-red-300" };
}

const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500";

export default function AgentDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { t, lang } = useI18n();
  const toast = useToast();
  const isAdmin = user?.role === "admin";

  const [agent, setAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [onlineMs, setOnlineMs] = useState(DEFAULT_ONLINE_MS);
  const [pollSeconds, setPollSeconds] = useState(15);

  const [segment, setSegment] = useState("");
  const [enabled, setEnabled] = useState(true);
  // Set once after a rotation so the plaintext token can be shown and wired
  // into the deploy command; cleared on reload.
  const [freshToken, setFreshToken] = useState<string | undefined>(undefined);
  const [copiedToken, setCopiedToken] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const a = await getAgent(id);
      setAgent(a);
      setSegment(a.segment ?? "");
      setEnabled(a.enabled);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    fetchSettings()
      .then((s) => {
        setOnlineMs(s.agent_online_seconds * 1000);
        setPollSeconds(s.agent_poll_seconds);
      })
      .catch(() => {
        /* keep defaults */
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function onSave(e: FormEvent) {
    e.preventDefault();
    if (!agent) return;
    try {
      const updated = await updateAgent(agent.id, { segment: segment || null, enabled });
      setAgent(updated);
      toast.success(t("agents.updated"));
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  async function onRotate() {
    if (!agent) return;
    if (!window.confirm(t("agents.confirmRotate", { name: agent.name }))) return;
    try {
      const result = await rotateAgentToken(agent.id);
      setCopiedToken(false);
      setFreshToken(result.token);
      toast.success(t("agents.rotated"));
      await load();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  async function onDelete() {
    if (!agent) return;
    if (!window.confirm(t("agents.confirmDelete"))) return;
    try {
      await deleteAgent(agent.id);
      toast.success(t("agents.deleted"));
      navigate("/agents");
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  const back = (
    <Link to="/agents" className="text-sm text-slate-400 hover:text-slate-200">
      ← {t("agents.backToList")}
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

  if (!agent) {
    return (
      <div className="space-y-4">
        {back}
        <p className="text-sm text-red-400">{error ?? t("agents.notFound")}</p>
      </div>
    );
  }

  const status = statusInfo(agent, onlineMs);

  return (
    <div className="space-y-6">
      {back}

      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold text-slate-100">{agent.name}</h1>
        <span className={`rounded-full px-2 py-0.5 text-xs ${status.cls}`}>{t(status.key)}</span>
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
        <p className="mb-3 text-sm font-medium text-slate-300">{t("agents.details")}</p>
        <dl className="grid grid-cols-1 gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
          {(
            [
              ["agents.col.segment", agent.segment ?? t("agents.any")],
              ["agents.col.version", agent.version ?? t("agents.unknown")],
              ["agents.platform", agent.platform ?? t("agents.unknown")],
              ["agents.lastIp", agent.last_ip ?? t("agents.unknown")],
              [
                "agents.col.lastSeen",
                timeAgo(agent.last_seen_at, lang),
                absoluteTime(agent.last_seen_at),
              ],
              [
                "agents.col.enrolledAt",
                timeAgo(agent.created_at, lang),
                absoluteTime(agent.created_at),
              ],
            ] as [TKey, string, string?][]
          ).map(([label, value, title]) => (
            <div key={label} className="flex justify-between gap-4 border-b border-slate-800/60 py-1">
              <dt className="text-slate-500">{t(label)}</dt>
              <dd className="text-right text-slate-200" title={title}>
                {value}
              </dd>
            </div>
          ))}
        </dl>
      </div>

      {freshToken && (
        <div className="space-y-2 rounded-xl border border-emerald-800 bg-emerald-950/40 p-4">
          <p className="text-sm text-emerald-300">{t("agents.rotatedNotice", { name: agent.name })}</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 overflow-x-auto rounded bg-slate-900 px-3 py-2 font-mono text-xs text-slate-200">
              {freshToken}
            </code>
            <button
              onClick={() => {
                void navigator.clipboard?.writeText(freshToken);
                setCopiedToken(true);
              }}
              className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-500"
            >
              {copiedToken ? t("agents.copied") : t("agents.copy")}
            </button>
          </div>
        </div>
      )}

      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
        <AgentDeployPanel name={agent.name} token={freshToken} pollSeconds={pollSeconds} />
      </div>

      {isAdmin && (
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <form onSubmit={onSave} className="space-y-3">
            <p className="text-sm font-medium text-slate-300">{t("agents.editTitle", { name: agent.name })}</p>
            <div>
              <label className="block text-sm text-slate-300">{t("agents.f.segment")}</label>
              <input
                className={inputClass}
                placeholder={t("agents.f.segmentPlaceholder")}
                value={segment}
                onChange={(e) => setSegment(e.target.value)}
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
              {t("agents.f.enabled")}
            </label>
            <p className="text-xs text-slate-500">{t("agents.f.enabledHint")}</p>
            <div className="flex justify-end">
              <Button type="submit">{t("agents.saveChanges")}</Button>
            </div>
          </form>

          <div className="mt-4 space-y-2 border-t border-slate-800 pt-4">
            <p className="text-sm font-medium text-slate-300">{t("agents.rotateTitle")}</p>
            <p className="text-xs text-slate-500">{t("agents.rotateHint")}</p>
            <p className="text-xs text-slate-500">
              {agent.token_rotated_at
                ? t("agents.lastRotated", { when: new Date(agent.token_rotated_at).toLocaleString() })
                : t("agents.neverRotated")}
            </p>
            <button
              type="button"
              onClick={() => void onRotate()}
              className="rounded-lg border border-amber-700 px-3 py-2 text-sm font-medium text-amber-300 hover:bg-amber-950/40"
            >
              {t("agents.rotate")}
            </button>
          </div>

          <div className="mt-4 border-t border-slate-800 pt-4">
            <button
              type="button"
              onClick={() => void onDelete()}
              className="text-sm text-red-400 hover:text-red-300"
            >
              {t("agents.deleteAgent")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
