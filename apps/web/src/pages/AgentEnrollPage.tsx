import { type FormEvent, useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { type EnrolledAgent, enrollAgent, fetchSettings } from "../api/client";
import { inputClass } from "../components/formStyles";
import { useErrorMessage } from "../i18n/useErrorMessage";
import { useAuth } from "../auth/AuthContext";
import AgentDeployPanel from "../components/AgentDeployPanel";
import Button from "../components/Button";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

const WHAT_POINTS: TKey[] = ["agents.what1", "agents.what2", "agents.what3", "agents.what4"];

export default function AgentEnrollPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const errorMessage = useErrorMessage();
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [segment, setSegment] = useState("");
  const [enrolled, setEnrolled] = useState<EnrolledAgent | null>(null);
  const [copied, setCopied] = useState(false);
  const [pollSeconds, setPollSeconds] = useState(15);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchSettings()
      .then((s) => setPollSeconds(s.agent_poll_seconds))
      .catch(() => {
        /* keep default */
      });
  }, []);

  // Enrollment is an admin action; send everyone else back to the list.
  if (user && user.role !== "admin") {
    return <Navigate to="/agents" replace />;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await enrollAgent(name, segment || null);
      setEnrolled(result);
      setCopied(false);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSubmitting(false);
    }
  }

  function enrollAnother() {
    setEnrolled(null);
    setName("");
    setSegment("");
    setError(null);
  }

  const back = (
    <Link to="/agents" className="text-sm text-slate-400 hover:text-slate-200">
      ← {t("agents.backToList")}
    </Link>
  );

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {back}

      <div>
        <h1 className="text-2xl font-semibold text-slate-100">{t("agents.enrollTitle")}</h1>
        <p className="mt-1 text-sm text-slate-400">{t("agents.enrollSubtitle")}</p>
      </div>

      {!enrolled && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
          <p className="mb-3 text-sm font-medium text-slate-200">{t("agents.whatTitle")}</p>
          <ul className="space-y-2">
            {WHAT_POINTS.map((key) => (
              <li key={key} className="flex gap-2 text-sm text-slate-400">
                <span className="mt-0.5 text-emerald-400">✓</span>
                <span>{t(key)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {enrolled ? (
        <div className="space-y-4">
          <div className="space-y-2 rounded-xl border border-emerald-800 bg-emerald-950/40 p-4">
            <p className="text-sm text-emerald-300">
              {t("agents.enrolledNotice", { name: enrolled.name })}
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 overflow-x-auto rounded bg-slate-900 px-3 py-2 font-mono text-xs text-slate-200">
                {enrolled.token}
              </code>
              <Button
                onClick={() => {
                  void navigator.clipboard?.writeText(enrolled.token);
                  setCopied(true);
                }}
              >
                {copied ? t("agents.copied") : t("agents.copy")}
              </Button>
            </div>
            <AgentDeployPanel
              name={enrolled.name}
              token={enrolled.token}
              pollSeconds={pollSeconds}
            />
          </div>

          <div className="flex flex-wrap gap-3">
            <Button onClick={() => navigate(`/agents/${enrolled.id}`)}>
              {t("agents.viewAgent")}
            </Button>
            <button
              onClick={enrollAnother}
              className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800"
            >
              {t("agents.enrollAnother")}
            </button>
          </div>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4 rounded-xl border border-slate-800 bg-slate-900 p-5">
          <div>
            <label className="block text-sm text-slate-300">{t("agents.enrollNameLabel")}</label>
            <input
              className={inputClass}
              placeholder={t("agents.namePlaceholder")}
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              autoFocus
            />
          </div>
          <div>
            <label className="block text-sm text-slate-300">{t("agents.enrollSegmentLabel")}</label>
            <input
              className={inputClass}
              placeholder={t("agents.segmentPlaceholder")}
              value={segment}
              onChange={(e) => setSegment(e.target.value)}
            />
            <p className="mt-1 text-xs text-slate-500">{t("agents.f.segmentHint")}</p>
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <div className="flex justify-end">
            <Button type="submit" disabled={submitting}>
              {submitting ? t("common.saving") : t("agents.enroll")}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
