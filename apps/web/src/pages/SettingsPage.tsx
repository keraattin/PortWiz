import { useEffect, useState } from "react";
import {
  type AiProviderInfo,
  ApiError,
  type SettingsConfig,
  type SettingsConfigUpdate,
  type SettingsStatus,
  type TestResult,
  fetchAiProviders,
  fetchSettings,
  fetchSettingsConfig,
  testAi,
  testEmail,
  testJira,
  testNetbox,
  updateSettingsConfig,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import FormField from "../components/FormField";
import { useToast } from "../components/Toast";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

type Translate = (key: TKey, vars?: Record<string, string | number>) => string;

function errorMessage(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong";
}

const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500";
const cardClass = "space-y-3 rounded-xl border border-slate-800 bg-slate-900 p-5";
const primaryBtn =
  "rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50";
const testBtn =
  "rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800 disabled:opacity-50";

interface FormState {
  ai_provider: string;
  ollama_base_url: string;
  ollama_model: string;
  anthropic_model: string;
  anthropic_api_key: string;
  compat_base_url: string;
  compat_model: string;
  compat_api_key: string;
  notifications_enabled: boolean;
  smtp_host: string;
  smtp_port: string;
  smtp_from: string;
  smtp_username: string;
  smtp_password: string;
  smtp_use_tls: boolean;
  notification_recipients: string;
  jira_enabled: boolean;
  jira_url: string;
  jira_email: string;
  jira_api_token: string;
  jira_project_key: string;
  netbox_enabled: boolean;
  netbox_url: string;
  netbox_token: string;
}

function fromConfig(c: SettingsConfig): FormState {
  return {
    ai_provider: c.ai_provider,
    ollama_base_url: c.ollama_base_url,
    ollama_model: c.ollama_model,
    anthropic_model: c.anthropic_model,
    anthropic_api_key: "",
    compat_base_url: c.compat_base_url,
    compat_model: c.compat_model,
    compat_api_key: "",
    notifications_enabled: c.notifications_enabled,
    smtp_host: c.smtp_host,
    smtp_port: String(c.smtp_port),
    smtp_from: c.smtp_from,
    smtp_username: c.smtp_username ?? "",
    smtp_password: "",
    smtp_use_tls: c.smtp_use_tls,
    notification_recipients: c.notification_recipients.join(", "),
    jira_enabled: c.jira_enabled,
    jira_url: c.jira_url ?? "",
    jira_email: c.jira_email ?? "",
    jira_api_token: "",
    jira_project_key: c.jira_project_key,
    netbox_enabled: c.netbox_enabled,
    netbox_url: c.netbox_url ?? "",
    netbox_token: "",
  };
}

function secretHint(isSet: boolean, t: Translate): string {
  return isSet ? t("settings.secretSet") : t("settings.secretNotSet");
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-slate-300">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
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

export default function SettingsPage() {
  const { user } = useAuth();
  const toast = useToast();
  const { t } = useI18n();
  const isAdmin = user?.role === "admin";

  const [config, setConfig] = useState<SettingsConfig | null>(null);
  const [status, setStatus] = useState<SettingsStatus | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [providers, setProviders] = useState<AiProviderInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [testing, setTesting] = useState<string | null>(null);

  const [aiResult, setAiResult] = useState<TestResult | null>(null);
  const [emailResult, setEmailResult] = useState<TestResult | null>(null);
  const [jiraResult, setJiraResult] = useState<TestResult | null>(null);
  const [netboxResult, setNetboxResult] = useState<TestResult | null>(null);
  const [emailTo, setEmailTo] = useState("");

  useEffect(() => {
    async function load() {
      try {
        if (isAdmin) {
          const [c, p] = await Promise.all([fetchSettingsConfig(), fetchAiProviders()]);
          setConfig(c);
          setForm(fromConfig(c));
          setProviders(p);
        } else {
          setStatus(await fetchSettings());
        }
      } catch (e) {
        setError(errorMessage(e));
      }
    }
    void load();
  }, [isAdmin]);

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => (f ? { ...f, [key]: value } : f));
  }

  // Switching provider resets the OpenAI-compatible fields to the chosen
  // provider's defaults (each has its own base URL and model).
  function onProviderChange(id: string) {
    const info = providers.find((p) => p.id === id);
    setForm((f) =>
      f
        ? {
            ...f,
            ai_provider: id,
            ...(info?.kind === "openai_compat"
              ? {
                  compat_base_url: info.default_base_url,
                  compat_model: info.default_model,
                  compat_api_key: "",
                }
              : {}),
          }
        : f,
    );
  }

  async function save(group: string, payload: SettingsConfigUpdate) {
    setSaving(group);
    try {
      const c = await updateSettingsConfig(payload);
      setConfig(c);
      setForm(fromConfig(c)); // clears the secret inputs
      toast.success(t("settings.saved"));
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setSaving(null);
    }
  }

  async function runTest(
    name: string,
    fn: () => Promise<TestResult>,
    setResult: (r: TestResult) => void,
  ) {
    setTesting(name);
    try {
      setResult(await fn());
    } catch (e) {
      setResult({ ok: false, detail: errorMessage(e) });
    } finally {
      setTesting(null);
    }
  }

  if (error) return <p className="text-sm text-red-400">{error}</p>;

  // Read-only view for non-admins (auditors).
  if (!isAdmin) {
    if (!status) return <p className="text-sm text-slate-400">{t("common.loading")}</p>;
    return (
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-slate-200">{t("settings.title")}</h2>
        <p className="text-sm text-slate-500">{t("settings.readonlySubtitle")}</p>
        <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
          <div className={cardClass}>
            <h3 className="font-medium text-slate-100">{t("settings.section.ai")}</h3>
            <p className="text-slate-300">
              {status.ai_provider} (
              {status.ai_configured ? t("settings.configured") : t("settings.off")})
            </p>
          </div>
          <div className={cardClass}>
            <h3 className="font-medium text-slate-100">{t("settings.section.email")}</h3>
            <p className="text-slate-300">
              {status.smtp_host}:{status.smtp_port} (
              {status.email_enabled ? t("settings.enabled") : t("settings.disabled")})
            </p>
          </div>
          <div className={cardClass}>
            <h3 className="font-medium text-slate-100">{t("settings.section.jira")}</h3>
            <p className="text-slate-300">
              {status.jira_configured ? t("settings.configured") : t("settings.off")}
            </p>
          </div>
          <div className={cardClass}>
            <h3 className="font-medium text-slate-100">{t("settings.section.netbox")}</h3>
            <p className="text-slate-300">
              {status.netbox_configured ? t("settings.configured") : t("settings.off")}
            </p>
          </div>
        </dl>
      </div>
    );
  }

  if (!config || !form) return <p className="text-sm text-slate-400">{t("common.loading")}</p>;

  const currentProvider = providers.find((p) => p.id === form.ai_provider);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-200">{t("settings.title")}</h2>
        <p className="text-sm text-slate-500">{t("settings.adminSubtitle")}</p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* AI */}
        <section className={cardClass}>
          <h3 className="font-medium text-slate-100">{t("settings.ai.title")}</h3>
          <FormField label={t("settings.ai.provider")} hint={t("settings.ai.providerHint")}>
            <select
              className={inputClass}
              value={form.ai_provider}
              onChange={(e) => onProviderChange(e.target.value)}
            >
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </FormField>

          {/* Only the fields relevant to the selected provider are shown. */}
          {currentProvider?.kind === "ollama" && (
            <>
              <FormField label={t("settings.ai.ollamaUrl")}>
                <input
                  className={inputClass}
                  value={form.ollama_base_url}
                  onChange={(e) => set("ollama_base_url", e.target.value)}
                />
              </FormField>
              <FormField label={t("settings.ai.ollamaModel")}>
                <input
                  className={inputClass}
                  value={form.ollama_model}
                  onChange={(e) => set("ollama_model", e.target.value)}
                />
              </FormField>
            </>
          )}

          {currentProvider?.kind === "anthropic" && (
            <>
              <FormField label={t("settings.ai.claudeModel")}>
                <input
                  className={inputClass}
                  value={form.anthropic_model}
                  onChange={(e) => set("anthropic_model", e.target.value)}
                />
              </FormField>
              <FormField label={t("settings.ai.anthropicKey")} hint={secretHint(config.anthropic_api_key_set, t)}>
                <input
                  className={inputClass}
                  type="password"
                  placeholder={config.anthropic_api_key_set ? "••••••••" : t("settings.notSetPlaceholder")}
                  value={form.anthropic_api_key}
                  onChange={(e) => set("anthropic_api_key", e.target.value)}
                />
              </FormField>
            </>
          )}

          {currentProvider?.kind === "openai_compat" && (
            <>
              {currentProvider.needs_base_url && (
                <FormField label={t("settings.compat.baseUrl")} hint={t("settings.compat.baseUrlHint")}>
                  <input
                    className={inputClass}
                    placeholder="http://localhost:1234/v1"
                    value={form.compat_base_url}
                    onChange={(e) => set("compat_base_url", e.target.value)}
                  />
                </FormField>
              )}
              <FormField label={t("settings.compat.model")}>
                <input
                  className={inputClass}
                  placeholder={currentProvider.default_model}
                  value={form.compat_model}
                  onChange={(e) => set("compat_model", e.target.value)}
                />
              </FormField>
              {currentProvider.needs_api_key && (
                <FormField label={t("settings.compat.apiKey")} hint={secretHint(config.compat_api_key_set, t)}>
                  <input
                    className={inputClass}
                    type="password"
                    placeholder={config.compat_api_key_set ? "••••••••" : t("settings.notSetPlaceholder")}
                    value={form.compat_api_key}
                    onChange={(e) => set("compat_api_key", e.target.value)}
                  />
                </FormField>
              )}
            </>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <button
              className={primaryBtn}
              disabled={saving === "ai"}
              onClick={() =>
                save("ai", {
                  ai_provider: form.ai_provider,
                  ollama_base_url: form.ollama_base_url,
                  ollama_model: form.ollama_model,
                  anthropic_model: form.anthropic_model,
                  anthropic_api_key: form.anthropic_api_key,
                  compat_base_url: form.compat_base_url,
                  compat_model: form.compat_model,
                  compat_api_key: form.compat_api_key,
                })
              }
            >
              {saving === "ai" ? t("common.saving") : t("common.save")}
            </button>
            <button
              className={testBtn}
              disabled={testing === "ai"}
              onClick={() => runTest("ai", testAi, setAiResult)}
            >
              {testing === "ai" ? t("settings.testing") : t("settings.ai.test")}
            </button>
          </div>
          <TestRow result={aiResult} />
        </section>

        {/* Email */}
        <section className={cardClass}>
          <h3 className="font-medium text-slate-100">{t("settings.email.title")}</h3>
          <Toggle
            label={t("settings.email.notificationsEnabled")}
            checked={form.notifications_enabled}
            onChange={(v) => set("notifications_enabled", v)}
          />
          <FormField label={t("settings.email.host")}>
            <input
              className={inputClass}
              value={form.smtp_host}
              onChange={(e) => set("smtp_host", e.target.value)}
            />
          </FormField>
          <FormField label={t("settings.email.port")}>
            <input
              className={inputClass}
              inputMode="numeric"
              value={form.smtp_port}
              onChange={(e) => set("smtp_port", e.target.value)}
            />
          </FormField>
          <FormField label={t("settings.email.from")}>
            <input
              className={inputClass}
              value={form.smtp_from}
              onChange={(e) => set("smtp_from", e.target.value)}
            />
          </FormField>
          <FormField label={t("settings.email.username")} hint={t("settings.email.usernameHint")}>
            <input
              className={inputClass}
              value={form.smtp_username}
              onChange={(e) => set("smtp_username", e.target.value)}
            />
          </FormField>
          <FormField label={t("settings.email.password")} hint={secretHint(config.smtp_password_set, t)}>
            <input
              className={inputClass}
              type="password"
              placeholder={config.smtp_password_set ? "••••••••" : t("settings.notSetPlaceholder")}
              value={form.smtp_password}
              onChange={(e) => set("smtp_password", e.target.value)}
            />
          </FormField>
          <Toggle
            label={t("settings.email.useTls")}
            checked={form.smtp_use_tls}
            onChange={(v) => set("smtp_use_tls", v)}
          />
          <FormField label={t("settings.email.recipients")} hint={t("settings.email.recipientsHint")}>
            <input
              className={inputClass}
              placeholder="security@example.com, ops@example.com"
              value={form.notification_recipients}
              onChange={(e) => set("notification_recipients", e.target.value)}
            />
          </FormField>
          <div className="flex flex-wrap items-center gap-3">
            <button
              className={primaryBtn}
              disabled={saving === "email"}
              onClick={() =>
                save("email", {
                  notifications_enabled: form.notifications_enabled,
                  smtp_host: form.smtp_host,
                  smtp_port: Number(form.smtp_port) || 0,
                  smtp_from: form.smtp_from,
                  smtp_username: form.smtp_username,
                  smtp_password: form.smtp_password,
                  smtp_use_tls: form.smtp_use_tls,
                  notification_recipients: form.notification_recipients
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean),
                })
              }
            >
              {saving === "email" ? t("common.saving") : t("common.save")}
            </button>
            <input
              className={`${inputClass} sm:w-56`}
              placeholder={t("settings.email.testRecipient")}
              value={emailTo}
              onChange={(e) => setEmailTo(e.target.value)}
            />
            <button
              className={testBtn}
              disabled={testing === "email"}
              onClick={() => runTest("email", () => testEmail(emailTo || undefined), setEmailResult)}
            >
              {testing === "email" ? t("settings.email.sending") : t("settings.email.sendTest")}
            </button>
          </div>
          <TestRow result={emailResult} />
        </section>

        {/* Jira */}
        <section className={cardClass}>
          <h3 className="font-medium text-slate-100">{t("settings.jira.title")}</h3>
          <Toggle
            label={t("settings.jira.enabled")}
            checked={form.jira_enabled}
            onChange={(v) => set("jira_enabled", v)}
          />
          <FormField label={t("settings.jira.url")} hint={t("settings.jira.urlHint")}>
            <input
              className={inputClass}
              value={form.jira_url}
              onChange={(e) => set("jira_url", e.target.value)}
            />
          </FormField>
          <FormField label={t("settings.jira.email")}>
            <input
              className={inputClass}
              value={form.jira_email}
              onChange={(e) => set("jira_email", e.target.value)}
            />
          </FormField>
          <FormField label={t("settings.jira.token")} hint={secretHint(config.jira_api_token_set, t)}>
            <input
              className={inputClass}
              type="password"
              placeholder={config.jira_api_token_set ? "••••••••" : t("settings.notSetPlaceholder")}
              value={form.jira_api_token}
              onChange={(e) => set("jira_api_token", e.target.value)}
            />
          </FormField>
          <FormField label={t("settings.jira.projectKey")} hint={t("settings.jira.projectKeyHint")}>
            <input
              className={inputClass}
              value={form.jira_project_key}
              onChange={(e) => set("jira_project_key", e.target.value)}
            />
          </FormField>
          <div className="flex flex-wrap items-center gap-3">
            <button
              className={primaryBtn}
              disabled={saving === "jira"}
              onClick={() =>
                save("jira", {
                  jira_enabled: form.jira_enabled,
                  jira_url: form.jira_url,
                  jira_email: form.jira_email,
                  jira_api_token: form.jira_api_token,
                  jira_project_key: form.jira_project_key,
                })
              }
            >
              {saving === "jira" ? t("common.saving") : t("common.save")}
            </button>
            <button
              className={testBtn}
              disabled={testing === "jira"}
              onClick={() => runTest("jira", testJira, setJiraResult)}
            >
              {testing === "jira" ? t("settings.testing") : t("settings.testConnection")}
            </button>
          </div>
          <TestRow result={jiraResult} />
        </section>

        {/* NetBox */}
        <section className={cardClass}>
          <h3 className="font-medium text-slate-100">{t("settings.netbox.title")}</h3>
          <Toggle
            label={t("settings.netbox.enabled")}
            checked={form.netbox_enabled}
            onChange={(v) => set("netbox_enabled", v)}
          />
          <FormField label={t("settings.netbox.url")} hint={t("settings.netbox.urlHint")}>
            <input
              className={inputClass}
              value={form.netbox_url}
              onChange={(e) => set("netbox_url", e.target.value)}
            />
          </FormField>
          <FormField label={t("settings.netbox.token")} hint={secretHint(config.netbox_token_set, t)}>
            <input
              className={inputClass}
              type="password"
              placeholder={config.netbox_token_set ? "••••••••" : t("settings.notSetPlaceholder")}
              value={form.netbox_token}
              onChange={(e) => set("netbox_token", e.target.value)}
            />
          </FormField>
          <div className="flex flex-wrap items-center gap-3">
            <button
              className={primaryBtn}
              disabled={saving === "netbox"}
              onClick={() =>
                save("netbox", {
                  netbox_enabled: form.netbox_enabled,
                  netbox_url: form.netbox_url,
                  netbox_token: form.netbox_token,
                })
              }
            >
              {saving === "netbox" ? t("common.saving") : t("common.save")}
            </button>
            <button
              className={testBtn}
              disabled={testing === "netbox"}
              onClick={() => runTest("netbox", testNetbox, setNetboxResult)}
            >
              {testing === "netbox" ? t("settings.testing") : t("settings.testConnection")}
            </button>
          </div>
          <TestRow result={netboxResult} />
        </section>
      </div>
    </div>
  );
}
