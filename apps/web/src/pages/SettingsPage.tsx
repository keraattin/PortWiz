import { useEffect, useState } from "react";
import {
  ApiError,
  type SettingsStatus,
  type TestResult,
  fetchSettings,
  testAi,
  testEmail,
  testJira,
  testNetbox,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";

function errorMessage(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong";
}

const cardClass = "space-y-3 rounded-xl border border-slate-800 bg-slate-900 p-5";
const labelClass = "text-slate-500";
const valueClass = "font-mono text-slate-200";
const testBtn =
  "rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800 disabled:opacity-50";

function StatusDot({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className="flex items-center gap-2 text-sm">
      <span
        className={`inline-block h-2.5 w-2.5 rounded-full ${ok ? "bg-emerald-500" : "bg-slate-600"}`}
      />
      <span className={ok ? "text-emerald-400" : "text-slate-400"}>{label}</span>
    </span>
  );
}

function TestRow({ result }: { result: TestResult | null }) {
  if (!result) return null;
  return (
    <p className={`text-sm ${result.ok ? "text-emerald-400" : "text-red-400"}`}>
      {result.detail}
    </p>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className={labelClass}>{label}</dt>
      <dd className={`${valueClass} truncate`}>{value}</dd>
    </div>
  );
}

export default function SettingsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [status, setStatus] = useState<SettingsStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [aiResult, setAiResult] = useState<TestResult | null>(null);
  const [emailResult, setEmailResult] = useState<TestResult | null>(null);
  const [jiraResult, setJiraResult] = useState<TestResult | null>(null);
  const [netboxResult, setNetboxResult] = useState<TestResult | null>(null);
  const [emailTo, setEmailTo] = useState("");
  const [testing, setTesting] = useState<string | null>(null);

  useEffect(() => {
    fetchSettings()
      .then(setStatus)
      .catch((e) => setError(errorMessage(e)));
  }, []);

  async function runTest(
    name: string,
    fn: () => Promise<TestResult>,
    set: (r: TestResult) => void,
  ) {
    setTesting(name);
    try {
      set(await fn());
    } catch (e) {
      set({ ok: false, detail: errorMessage(e) });
    } finally {
      setTesting(null);
    }
  }

  if (error) return <p className="text-sm text-red-400">{error}</p>;
  if (!status) return <p className="text-sm text-slate-400">Loading…</p>;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-200">Settings &amp; integrations</h2>
        <p className="text-sm text-slate-500">
          Configuration is set via environment variables. This page shows the effective,
          non-secret status; admins can test each integration. No secrets are exposed.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* AI */}
        <section className={cardClass}>
          <div className="flex items-center justify-between">
            <h3 className="font-medium text-slate-100">AI assistant</h3>
            <StatusDot ok={status.ai_configured} label={status.ai_configured ? "configured" : "off"} />
          </div>
          <dl className="space-y-1 text-sm">
            <Field label="Provider" value={status.ai_provider} />
            <Field label="Model" value={status.ai_model} />
          </dl>
          {isAdmin && (
            <button
              className={testBtn}
              disabled={testing === "ai"}
              onClick={() => runTest("ai", testAi, setAiResult)}
            >
              {testing === "ai" ? "Testing…" : "Test provider"}
            </button>
          )}
          <TestRow result={aiResult} />
        </section>

        {/* Email */}
        <section className={cardClass}>
          <div className="flex items-center justify-between">
            <h3 className="font-medium text-slate-100">Email (SMTP)</h3>
            <StatusDot
              ok={status.email_enabled}
              label={status.email_enabled ? "enabled" : "disabled"}
            />
          </div>
          <dl className="space-y-1 text-sm">
            <Field label="Host" value={`${status.smtp_host}:${status.smtp_port}`} />
            <Field label="From" value={status.smtp_from} />
            <Field label="Recipients" value={String(status.email_recipients.length)} />
          </dl>
          {isAdmin && (
            <div className="space-y-2">
              <input
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-sm text-slate-100 outline-none focus:border-emerald-500"
                placeholder="Recipient (optional)"
                value={emailTo}
                onChange={(e) => setEmailTo(e.target.value)}
              />
              <button
                className={testBtn}
                disabled={testing === "email"}
                onClick={() => runTest("email", () => testEmail(emailTo || undefined), setEmailResult)}
              >
                {testing === "email" ? "Sending…" : "Send test email"}
              </button>
            </div>
          )}
          <TestRow result={emailResult} />
        </section>

        {/* Jira */}
        <section className={cardClass}>
          <div className="flex items-center justify-between">
            <h3 className="font-medium text-slate-100">Jira</h3>
            <StatusDot
              ok={status.jira_configured}
              label={status.jira_configured ? "configured" : "off"}
            />
          </div>
          <dl className="space-y-1 text-sm">
            <Field label="URL" value={status.jira_url ?? "-"} />
            <Field label="Project" value={status.jira_project_key} />
          </dl>
          {isAdmin && (
            <button
              className={testBtn}
              disabled={testing === "jira"}
              onClick={() => runTest("jira", testJira, setJiraResult)}
            >
              {testing === "jira" ? "Testing…" : "Test connection"}
            </button>
          )}
          <TestRow result={jiraResult} />
        </section>

        {/* NetBox */}
        <section className={cardClass}>
          <div className="flex items-center justify-between">
            <h3 className="font-medium text-slate-100">NetBox (IPAM)</h3>
            <StatusDot
              ok={status.netbox_configured}
              label={status.netbox_configured ? "configured" : "off"}
            />
          </div>
          <dl className="space-y-1 text-sm">
            <Field label="URL" value={status.netbox_url ?? "-"} />
          </dl>
          {isAdmin && (
            <button
              className={testBtn}
              disabled={testing === "netbox"}
              onClick={() => runTest("netbox", testNetbox, setNetboxResult)}
            >
              {testing === "netbox" ? "Testing…" : "Test connection"}
            </button>
          )}
          <TestRow result={netboxResult} />
        </section>
      </div>

      {!isAdmin && (
        <p className="text-xs text-slate-600">
          Integration tests require an administrator.
        </p>
      )}
      <p className="text-xs text-slate-600">
        {status.app_name} v{status.version} · {status.environment}
      </p>
    </div>
  );
}
