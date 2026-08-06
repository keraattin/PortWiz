import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  type AiProviderInfo,
  type JiraProject,
  type JiraUser,
  type ScanProfile,
  type SettingsConfig,
  type SettingsConfigUpdate,
  type SettingsStatus,
  type CVEImportReport,
  type TestResult,
  type UpdateStatus,
  applyUpdate,
  checkForUpdate,
  listScanProfiles,
  fetchAiProviders,
  importCveFeed,
  fetchJiraIssueTypes,
  fetchJiraPriorities,
  fetchJiraProjects,
  fetchSettings,
  fetchSettingsConfig,
  fetchUpdateStatus,
  searchJiraUsers,
  testAi,
  testEmail,
  testSlack,
  testTeams,
  testJira,
  testCve,
  testNetbox,
  updateSettingsConfig,
} from "../api/client";
import CveHowToModal from "../components/CveHowToModal";
import { inputClass } from "../components/formStyles";
import { useErrorMessage } from "../i18n/useErrorMessage";
import { useAuth } from "../auth/AuthContext";
import FormField from "../components/FormField";
import InfoCallout from "../components/InfoCallout";
import DocsLink from "../components/DocsLink";
import PageHeader from "../components/PageHeader";
import { useToast } from "../components/Toast";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

type Translate = (key: TKey, vars?: Record<string, string | number>) => string;

// Guided "connect" helper for key-based AI providers: names the provider,
// deep-links to its key page and states the get-key → paste → save → test flow.
function ProviderConnectHelp({ provider, t }: { provider: AiProviderInfo; t: Translate }) {
  if (!provider.needs_api_key || !provider.console_url) return null;
  return (
    <InfoCallout>
      <p className="font-medium text-slate-200">{t("settings.ai.connectTitle")}</p>
      <p className="mt-1 text-slate-400">{t("settings.ai.connectSteps")}</p>
      <a
        href={provider.console_url}
        target="_blank"
        rel="noreferrer"
        className="mt-2 inline-block text-sm font-medium text-emerald-400 hover:text-emerald-300"
      >
        {t("settings.ai.getKeyFrom", { provider: provider.label })} →
      </a>
    </InfoCallout>
  );
}

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
  smtp_tls_verify: boolean;
  notification_recipients: string;
  email_min_severity: string;
  email_scan_profiles: string[];
  notify_mode: string;
  notify_quiet_hours_enabled: boolean;
  notify_quiet_start: string;
  notify_quiet_end: string;
  slack_enabled: boolean;
  slack_transport: string;
  slack_webhook_url: string;
  slack_bot_token: string;
  slack_channel: string;
  slack_min_severity: string;
  slack_scan_profiles: string[];
  teams_enabled: boolean;
  teams_transport: string;
  teams_webhook_url: string;
  teams_tenant_id: string;
  teams_client_id: string;
  teams_client_secret: string;
  teams_team_id: string;
  teams_channel_id: string;
  teams_min_severity: string;
  teams_scan_profiles: string[];
  jira_enabled: boolean;
  jira_deployment: string;
  jira_url: string;
  jira_email: string;
  jira_api_token: string;
  jira_project_key: string;
  jira_issue_type: string;
  jira_default_assignee: string;
  jira_labels: string;
  jira_priority_high: string;
  jira_priority_medium: string;
  jira_priority_low: string;
  jira_extra_fields: string;
  netbox_enabled: boolean;
  netbox_url: string;
  netbox_token: string;
  netbox_writeback_enabled: boolean;
  netbox_import_assets: boolean;
  netbox_import_vlans: boolean;
  netbox_import_hostnames: boolean;
  netbox_import_descriptions: boolean;
  cve_enabled: boolean;
  cve_source: string;
  cve_api_url: string;
  cve_api_key: string;
  cve_min_cvss: string;
  cve_recheck_hours: string;
  cert_expiry_warn_days: string;
  cert_expiry_recheck_hours: string;
  change_confirmations: string;
  agent_online_seconds: string;
  agent_poll_seconds: string;
  scan_stale_minutes: string;
  scan_max_attempts: string;
  default_scan_ports: string;
  default_scan_type: string;
  default_service_detection: boolean;
  default_scan_rate_limit_pps: string;
  retention_observation_days: string;
  update_check_enabled: boolean;
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
    smtp_tls_verify: c.smtp_tls_verify,
    notification_recipients: c.notification_recipients.join(", "),
    email_min_severity: c.email_min_severity,
    email_scan_profiles: c.email_scan_profiles,
    notify_mode: c.notify_mode,
    notify_quiet_hours_enabled: c.notify_quiet_hours_enabled,
    notify_quiet_start: c.notify_quiet_start,
    notify_quiet_end: c.notify_quiet_end,
    slack_enabled: c.slack_enabled,
    slack_transport: c.slack_transport,
    slack_webhook_url: "",
    slack_bot_token: "",
    slack_channel: c.slack_channel ?? "",
    slack_min_severity: c.slack_min_severity,
    slack_scan_profiles: c.slack_scan_profiles,
    teams_enabled: c.teams_enabled,
    teams_transport: c.teams_transport,
    teams_webhook_url: "",
    teams_tenant_id: c.teams_tenant_id ?? "",
    teams_client_id: c.teams_client_id ?? "",
    teams_client_secret: "",
    teams_team_id: c.teams_team_id ?? "",
    teams_channel_id: c.teams_channel_id ?? "",
    teams_min_severity: c.teams_min_severity,
    teams_scan_profiles: c.teams_scan_profiles,
    jira_enabled: c.jira_enabled,
    jira_deployment: c.jira_deployment || "cloud",
    jira_url: c.jira_url ?? "",
    jira_email: c.jira_email ?? "",
    jira_api_token: "",
    jira_project_key: c.jira_project_key,
    jira_issue_type: c.jira_issue_type || "Task",
    jira_default_assignee: c.jira_default_assignee ?? "",
    jira_labels: c.jira_labels ?? "",
    jira_priority_high: c.jira_priority_high ?? "",
    jira_priority_medium: c.jira_priority_medium ?? "",
    jira_priority_low: c.jira_priority_low ?? "",
    jira_extra_fields: c.jira_extra_fields ?? "",
    netbox_enabled: c.netbox_enabled,
    netbox_url: c.netbox_url ?? "",
    netbox_token: "",
    netbox_writeback_enabled: c.netbox_writeback_enabled,
    netbox_import_assets: c.netbox_import_assets,
    netbox_import_vlans: c.netbox_import_vlans,
    netbox_import_hostnames: c.netbox_import_hostnames,
    netbox_import_descriptions: c.netbox_import_descriptions,
    cve_enabled: c.cve_enabled,
    cve_source: c.cve_source || "nvd",
    cve_api_url: c.cve_api_url ?? "",
    cve_api_key: "",
    cve_min_cvss: String(c.cve_min_cvss ?? 0),
    cve_recheck_hours: String(c.cve_recheck_hours ?? 0),
    cert_expiry_warn_days: String(c.cert_expiry_warn_days ?? 30),
    cert_expiry_recheck_hours: String(c.cert_expiry_recheck_hours ?? 24),
    change_confirmations: String(c.change_confirmations),
    agent_online_seconds: String(c.agent_online_seconds),
    agent_poll_seconds: String(c.agent_poll_seconds),
    scan_stale_minutes: String(c.scan_stale_minutes),
    scan_max_attempts: String(c.scan_max_attempts),
    default_scan_ports: c.default_scan_ports,
    default_scan_type: c.default_scan_type,
    default_service_detection: c.default_service_detection,
    default_scan_rate_limit_pps: String(c.default_scan_rate_limit_pps),
    retention_observation_days: String(c.retention_observation_days),
    update_check_enabled: c.update_check_enabled,
  };
}

function secretHint(isSet: boolean, t: Translate): string {
  return isSet ? t("settings.secretSet") : t("settings.secretNotSet");
}

// Per-channel delivery rules: a minimum severity and a scan-profile scope.
// Shared by the email, Slack, and Teams sections.
function ChannelRules({
  t,
  profiles,
  severity,
  onSeverity,
  selected,
  onToggle,
}: {
  t: Translate;
  profiles: ScanProfile[];
  severity: string;
  onSeverity: (v: string) => void;
  selected: string[];
  onToggle: (id: string) => void;
}) {
  return (
    <>
      <FormField label={t("settings.rules.minSeverity")} hint={t("settings.rules.minSeverityHint")}>
        <select
          className={inputClass}
          value={severity}
          onChange={(e) => onSeverity(e.target.value)}
        >
          <option value="low">{t("severity.low")}</option>
          <option value="medium">{t("severity.medium")}</option>
          <option value="high">{t("severity.high")}</option>
        </select>
      </FormField>
      <FormField label={t("settings.rules.profiles")} hint={t("settings.rules.profilesHint")}>
        {profiles.length === 0 ? (
          <p className="text-sm text-slate-500">{t("settings.rules.noProfiles")}</p>
        ) : (
          <div className="max-h-40 space-y-1 overflow-y-auto rounded-lg border border-slate-800 bg-slate-950 p-2">
            {profiles.map((p) => (
              <label key={p.id} className="flex items-center gap-2 text-sm text-slate-300">
                <input
                  type="checkbox"
                  checked={selected.includes(p.id)}
                  onChange={() => onToggle(p.id)}
                />
                {p.name}
              </label>
            ))}
          </div>
        )}
      </FormField>
    </>
  );
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

// At-a-glance "connected / not configured" status for an integration tab.
function ConnectionBanner({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-sm">
      <span
        className={`inline-block h-2.5 w-2.5 shrink-0 rounded-full ${
          ok ? "bg-emerald-500" : "bg-slate-600"
        }`}
      />
      <span className={ok ? "text-slate-300" : "text-slate-400"}>{label}</span>
    </div>
  );
}

export default function SettingsPage() {
  const { user } = useAuth();
  const toast = useToast();
  const { t } = useI18n();
  const errorMessage = useErrorMessage();
  const isAdmin = user?.role === "admin";

  const [config, setConfig] = useState<SettingsConfig | null>(null);
  const [status, setStatus] = useState<SettingsStatus | null>(null);
  const [scanProfiles, setScanProfiles] = useState<ScanProfile[]>([]);
  const [form, setForm] = useState<FormState | null>(null);
  const [providers, setProviders] = useState<AiProviderInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  // Allow deep-linking to a tab, e.g. /settings?tab=system from the update banner.
  const [searchParams] = useSearchParams();
  const TABS = ["ai", "email", "chat", "jira", "netbox", "cve", "system"] as const;
  const requestedTab = searchParams.get("tab");
  const [activeTab, setActiveTab] = useState<(typeof TABS)[number]>(
    (TABS as readonly string[]).includes(requestedTab ?? "")
      ? (requestedTab as (typeof TABS)[number])
      : "ai",
  );
  // Reveal the updates section once when arriving via ?tab=system.
  const updatesRef = useRef<HTMLDivElement | null>(null);
  const revealedUpdates = useRef(false);

  const [aiResult, setAiResult] = useState<TestResult | null>(null);
  const [emailResult, setEmailResult] = useState<TestResult | null>(null);
  const [slackResult, setSlackResult] = useState<TestResult | null>(null);
  const [teamsResult, setTeamsResult] = useState<TestResult | null>(null);
  const [jiraResult, setJiraResult] = useState<TestResult | null>(null);
  const [netboxResult, setNetboxResult] = useState<TestResult | null>(null);
  const [cveResult, setCveResult] = useState<TestResult | null>(null);
  const [cveFeedFile, setCveFeedFile] = useState<File | null>(null);
  const [cveImporting, setCveImporting] = useState(false);
  const [cveImportReport, setCveImportReport] = useState<CVEImportReport | null>(null);
  const [cveHowToOpen, setCveHowToOpen] = useState(false);
  const [emailTo, setEmailTo] = useState("");
  const [updateStatus, setUpdateStatus] = useState<UpdateStatus | null>(null);
  const [checkingUpdate, setCheckingUpdate] = useState(false);
  const [applyingUpdate, setApplyingUpdate] = useState(false);
  const [updateApplied, setUpdateApplied] = useState(false);

  // Jira discovery: loaded on demand from the saved connection.
  const [jiraProjects, setJiraProjects] = useState<JiraProject[]>([]);
  const [jiraTypes, setJiraTypes] = useState<string[]>([]);
  const [jiraPriorities, setJiraPriorities] = useState<string[]>([]);
  const [userQuery, setUserQuery] = useState("");
  const [userResults, setUserResults] = useState<JiraUser[]>([]);
  const [jiraLoading, setJiraLoading] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      if (isAdmin) {
        const [c, p, s, profs] = await Promise.all([
          fetchSettingsConfig(),
          fetchAiProviders(),
          fetchSettings(),
          listScanProfiles(),
        ]);
        setConfig(c);
        setForm(fromConfig(c));
        setProviders(p);
        setStatus(s);
        setScanProfiles(profs);
        fetchUpdateStatus()
          .then(setUpdateStatus)
          .catch(() => {
            /* update check is best-effort */
          });
      } else {
        setStatus(await fetchSettings());
      }
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function checkUpdateNow() {
    setCheckingUpdate(true);
    try {
      setUpdateStatus(await checkForUpdate());
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setCheckingUpdate(false);
    }
  }

  async function applyUpdateNow() {
    setApplyingUpdate(true);
    try {
      await applyUpdate();
      setUpdateApplied(true);
      toast.success(t("update.inProgress"));
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setApplyingUpdate(false);
    }
  }

  async function onImportCveFeed() {
    if (!cveFeedFile) return;
    setCveImporting(true);
    setCveImportReport(null);
    try {
      const report = await importCveFeed(cveFeedFile);
      setCveImportReport(report);
      toast.success(t("settings.cve.imported", { count: report.imported }));
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setCveImporting(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin]);

  // Once the system tab has rendered (config loaded), scroll the updates section
  // into view when the user arrived from the "How to update" link.
  useEffect(() => {
    if (
      !revealedUpdates.current &&
      requestedTab === "system" &&
      activeTab === "system" &&
      config &&
      updatesRef.current
    ) {
      revealedUpdates.current = true;
      updatesRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [requestedTab, activeTab, config]);

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => (f ? { ...f, [key]: value } : f));
  }

  // Toggle a scan-profile id in one of the channel scope arrays.
  function toggleProfile(
    key: "email_scan_profiles" | "slack_scan_profiles" | "teams_scan_profiles",
    id: string,
  ) {
    setForm((f) =>
      f
        ? {
            ...f,
            [key]: f[key].includes(id) ? f[key].filter((x) => x !== id) : [...f[key], id],
          }
        : f,
    );
  }

  // Jira pickers fetch from the live instance; they need the connection saved
  // first, so a 400 here surfaces as a toast telling the admin to save + test.
  async function loadJiraProjects() {
    setJiraLoading("projects");
    try {
      setJiraProjects(await fetchJiraProjects());
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setJiraLoading(null);
    }
  }

  async function loadJiraTypes() {
    setJiraLoading("types");
    try {
      setJiraTypes(await fetchJiraIssueTypes());
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setJiraLoading(null);
    }
  }

  async function loadJiraPriorities() {
    setJiraLoading("priorities");
    try {
      setJiraPriorities(await fetchJiraPriorities());
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setJiraLoading(null);
    }
  }

  async function searchUsers() {
    if (!form) return;
    setJiraLoading("users");
    try {
      setUserResults(await searchJiraUsers(userQuery, form.jira_project_key));
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setJiraLoading(null);
    }
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
      setStatus(await fetchSettings()); // refresh the connection banners
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

  if (error) {
    // Keep the page shell and offer a retry instead of wiping everything to a
    // single red line on a transient fetch failure.
    return (
      <div className="space-y-4">
        <PageHeader title={t("settings.title")} />
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
          <span>{error}</span>
          <button
            onClick={() => void load()}
            className="rounded-lg border border-red-800 px-3 py-1 text-red-200 hover:bg-red-900/40"
          >
            {t("common.retry")}
          </button>
        </div>
      </div>
    );
  }

  // Read-only view for non-admins (auditors).
  if (!isAdmin) {
    if (!status) return <p className="text-sm text-slate-400">{t("common.loading")}</p>;
    return (
      <div className="space-y-4">
        <PageHeader title={t("settings.title")} subtitle={t("settings.readonlySubtitle")} />
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
      <PageHeader title={t("settings.title")} subtitle={t("settings.adminSubtitle")} />

      <div data-tour="settings-tabs" className="flex flex-wrap gap-1 border-b border-slate-800">
        {(["ai", "email", "chat", "jira", "netbox", "cve", "system"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`-mb-px rounded-t-lg border-b-2 px-4 py-2 text-sm ${
              activeTab === tab
                ? "border-emerald-500 text-emerald-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            {t(`settings.section.${tab}` as TKey)}
          </button>
        ))}
      </div>

      <div className="max-w-2xl">
        {activeTab === "ai" && (
        <section className={cardClass}>
          <h3 className="font-medium text-slate-100">{t("settings.ai.title")}</h3>
          {status && (
            <ConnectionBanner
              ok={status.ai_configured}
              label={
                status.ai_configured
                  ? t("settings.ai.connected", {
                      provider: currentProvider?.label ?? status.ai_provider,
                      model: status.ai_model,
                    })
                  : t("settings.ai.notConnected")
              }
            />
          )}
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
              <ProviderConnectHelp provider={currentProvider} t={t} />
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
              <ProviderConnectHelp provider={currentProvider} t={t} />
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
        )}

        {activeTab === "email" && (
        <div className="space-y-6">
          <div className="flex justify-end">
            <DocsLink guide="notifications" />
          </div>
          <section className={cardClass}>
            <h3 className="font-medium text-slate-100">{t("settings.timing.title")}</h3>
            <p className="text-sm text-slate-400">{t("settings.timing.intro")}</p>
            <FormField label={t("settings.timing.mode")} hint={t("settings.timing.modeHint")}>
              <select
                className={inputClass}
                value={form.notify_mode}
                onChange={(e) => set("notify_mode", e.target.value)}
              >
                <option value="immediate">{t("settings.timing.modeImmediate")}</option>
                <option value="hourly">{t("settings.timing.modeHourly")}</option>
                <option value="daily">{t("settings.timing.modeDaily")}</option>
              </select>
            </FormField>
            <Toggle
              label={t("settings.timing.quietHours")}
              checked={form.notify_quiet_hours_enabled}
              onChange={(v) => set("notify_quiet_hours_enabled", v)}
            />
            {form.notify_quiet_hours_enabled && (
              <div className="grid grid-cols-2 gap-3">
                <FormField label={t("settings.timing.start")}>
                  <input
                    className={inputClass}
                    type="time"
                    value={form.notify_quiet_start}
                    onChange={(e) => set("notify_quiet_start", e.target.value)}
                  />
                </FormField>
                <FormField label={t("settings.timing.end")}>
                  <input
                    className={inputClass}
                    type="time"
                    value={form.notify_quiet_end}
                    onChange={(e) => set("notify_quiet_end", e.target.value)}
                  />
                </FormField>
              </div>
            )}
            <p className="text-xs text-slate-500">{t("settings.timing.quietHint")}</p>
            <div>
              <button
                className={primaryBtn}
                disabled={saving === "timing"}
                onClick={() =>
                  save("timing", {
                    notify_mode: form.notify_mode,
                    notify_quiet_hours_enabled: form.notify_quiet_hours_enabled,
                    notify_quiet_start: form.notify_quiet_start,
                    notify_quiet_end: form.notify_quiet_end,
                  })
                }
              >
                {saving === "timing" ? t("common.saving") : t("common.save")}
              </button>
            </div>
          </section>

          <section className={cardClass}>
          <h3 className="font-medium text-slate-100">{t("settings.email.title")}</h3>
          {status && (
            <ConnectionBanner
              ok={status.email_enabled}
              label={t(status.email_enabled ? "settings.conn.connected" : "settings.conn.notConfigured")}
            />
          )}
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
          <Toggle
            label={t("settings.email.verifyTls")}
            checked={form.smtp_tls_verify}
            onChange={(v) => set("smtp_tls_verify", v)}
          />
          <p className="text-xs text-slate-500">{t("settings.email.verifyTlsHint")}</p>
          <FormField label={t("settings.email.recipients")} hint={t("settings.email.recipientsHint")}>
            <input
              className={inputClass}
              placeholder="security@example.com, ops@example.com"
              value={form.notification_recipients}
              onChange={(e) => set("notification_recipients", e.target.value)}
            />
          </FormField>
          <ChannelRules
            t={t}
            profiles={scanProfiles}
            severity={form.email_min_severity}
            onSeverity={(v) => set("email_min_severity", v)}
            selected={form.email_scan_profiles}
            onToggle={(id) => toggleProfile("email_scan_profiles", id)}
          />
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
                  smtp_tls_verify: form.smtp_tls_verify,
                  email_min_severity: form.email_min_severity,
                  email_scan_profiles: form.email_scan_profiles,
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
        </div>
        )}

        {activeTab === "chat" && (
        <div className="space-y-6">
          <div className="flex justify-end">
            <DocsLink guide="notifications" />
          </div>
          <InfoCallout>
            <p className="text-slate-400">{t("settings.chat.intro")}</p>
          </InfoCallout>

          <section className={cardClass}>
            <h3 className="font-medium text-slate-100">{t("settings.slack.title")}</h3>
            {status && (
              <ConnectionBanner
                ok={status.slack_configured}
                label={t(status.slack_configured ? "settings.conn.connected" : "settings.conn.notConfigured")}
              />
            )}
            <Toggle
              label={t("settings.slack.enabled")}
              checked={form.slack_enabled}
              onChange={(v) => set("slack_enabled", v)}
            />
            <FormField label={t("settings.slack.transport")} hint={t("settings.slack.transportHint")}>
              <select
                className={inputClass}
                value={form.slack_transport}
                onChange={(e) => set("slack_transport", e.target.value)}
              >
                <option value="webhook">{t("settings.slack.transport.webhook")}</option>
                <option value="bot">{t("settings.slack.transport.bot")}</option>
              </select>
            </FormField>
            {form.slack_transport === "bot" ? (
              <>
                <FormField
                  label={t("settings.slack.botToken")}
                  hint={config.slack_bot_token_set ? secretHint(true, t) : t("settings.slack.botTokenHint")}
                >
                  <input
                    className={inputClass}
                    type="password"
                    placeholder={config.slack_bot_token_set ? "••••••••" : "xoxb-…"}
                    value={form.slack_bot_token}
                    onChange={(e) => set("slack_bot_token", e.target.value)}
                  />
                </FormField>
                <FormField label={t("settings.slack.channel")} hint={t("settings.slack.channelHint")}>
                  <input
                    className={inputClass}
                    placeholder="#alerts"
                    value={form.slack_channel}
                    onChange={(e) => set("slack_channel", e.target.value)}
                  />
                </FormField>
              </>
            ) : (
              <FormField
                label={t("settings.slack.webhook")}
                hint={config.slack_webhook_set ? secretHint(true, t) : t("settings.slack.webhookHint")}
              >
                <input
                  className={inputClass}
                  type="password"
                  placeholder={config.slack_webhook_set ? "••••••••" : "https://hooks.slack.com/services/…"}
                  value={form.slack_webhook_url}
                  onChange={(e) => set("slack_webhook_url", e.target.value)}
                />
              </FormField>
            )}
            <ChannelRules
              t={t}
              profiles={scanProfiles}
              severity={form.slack_min_severity}
              onSeverity={(v) => set("slack_min_severity", v)}
              selected={form.slack_scan_profiles}
              onToggle={(id) => toggleProfile("slack_scan_profiles", id)}
            />
            <div className="flex flex-wrap items-center gap-3">
              <button
                className={primaryBtn}
                disabled={saving === "slack"}
                onClick={() =>
                  save("slack", {
                    slack_enabled: form.slack_enabled,
                    slack_transport: form.slack_transport,
                    slack_webhook_url: form.slack_webhook_url,
                    slack_bot_token: form.slack_bot_token,
                    slack_channel: form.slack_channel,
                    slack_min_severity: form.slack_min_severity,
                    slack_scan_profiles: form.slack_scan_profiles,
                  })
                }
              >
                {saving === "slack" ? t("common.saving") : t("common.save")}
              </button>
              <button
                className={testBtn}
                disabled={testing === "slack"}
                onClick={() => runTest("slack", testSlack, setSlackResult)}
              >
                {testing === "slack" ? t("settings.testing") : t("settings.testConnection")}
              </button>
            </div>
            <TestRow result={slackResult} />
          </section>

          <section className={cardClass}>
            <h3 className="font-medium text-slate-100">{t("settings.teams.title")}</h3>
            {status && (
              <ConnectionBanner
                ok={status.teams_configured}
                label={t(status.teams_configured ? "settings.conn.connected" : "settings.conn.notConfigured")}
              />
            )}
            <Toggle
              label={t("settings.teams.enabled")}
              checked={form.teams_enabled}
              onChange={(v) => set("teams_enabled", v)}
            />
            <FormField label={t("settings.teams.transport")} hint={t("settings.teams.transportHint")}>
              <select
                className={inputClass}
                value={form.teams_transport}
                onChange={(e) => set("teams_transport", e.target.value)}
              >
                <option value="webhook">{t("settings.teams.transport.webhook")}</option>
                <option value="graph">{t("settings.teams.transport.graph")}</option>
              </select>
            </FormField>
            {form.teams_transport === "graph" ? (
              <>
                <FormField label={t("settings.teams.tenantId")} hint={t("settings.teams.graphHint")}>
                  <input
                    className={inputClass}
                    value={form.teams_tenant_id}
                    onChange={(e) => set("teams_tenant_id", e.target.value)}
                  />
                </FormField>
                <FormField label={t("settings.teams.clientId")}>
                  <input
                    className={inputClass}
                    value={form.teams_client_id}
                    onChange={(e) => set("teams_client_id", e.target.value)}
                  />
                </FormField>
                <FormField
                  label={t("settings.teams.clientSecret")}
                  hint={config.teams_client_secret_set ? secretHint(true, t) : undefined}
                >
                  <input
                    className={inputClass}
                    type="password"
                    placeholder={config.teams_client_secret_set ? "••••••••" : ""}
                    value={form.teams_client_secret}
                    onChange={(e) => set("teams_client_secret", e.target.value)}
                  />
                </FormField>
                <FormField label={t("settings.teams.teamId")}>
                  <input
                    className={inputClass}
                    value={form.teams_team_id}
                    onChange={(e) => set("teams_team_id", e.target.value)}
                  />
                </FormField>
                <FormField label={t("settings.teams.channelId")}>
                  <input
                    className={inputClass}
                    value={form.teams_channel_id}
                    onChange={(e) => set("teams_channel_id", e.target.value)}
                  />
                </FormField>
              </>
            ) : (
              <FormField
                label={t("settings.teams.webhook")}
                hint={config.teams_webhook_set ? secretHint(true, t) : t("settings.teams.webhookHint")}
              >
                <input
                  className={inputClass}
                  type="password"
                  placeholder={config.teams_webhook_set ? "••••••••" : "https://outlook.office.com/webhook/…"}
                  value={form.teams_webhook_url}
                  onChange={(e) => set("teams_webhook_url", e.target.value)}
                />
              </FormField>
            )}
            <ChannelRules
              t={t}
              profiles={scanProfiles}
              severity={form.teams_min_severity}
              onSeverity={(v) => set("teams_min_severity", v)}
              selected={form.teams_scan_profiles}
              onToggle={(id) => toggleProfile("teams_scan_profiles", id)}
            />
            <div className="flex flex-wrap items-center gap-3">
              <button
                className={primaryBtn}
                disabled={saving === "teams"}
                onClick={() =>
                  save("teams", {
                    teams_enabled: form.teams_enabled,
                    teams_transport: form.teams_transport,
                    teams_webhook_url: form.teams_webhook_url,
                    teams_tenant_id: form.teams_tenant_id,
                    teams_client_id: form.teams_client_id,
                    teams_client_secret: form.teams_client_secret,
                    teams_team_id: form.teams_team_id,
                    teams_channel_id: form.teams_channel_id,
                    teams_min_severity: form.teams_min_severity,
                    teams_scan_profiles: form.teams_scan_profiles,
                  })
                }
              >
                {saving === "teams" ? t("common.saving") : t("common.save")}
              </button>
              <button
                className={testBtn}
                disabled={testing === "teams"}
                onClick={() => runTest("teams", testTeams, setTeamsResult)}
              >
                {testing === "teams" ? t("settings.testing") : t("settings.testConnection")}
              </button>
            </div>
            <TestRow result={teamsResult} />
          </section>
        </div>
        )}

        {activeTab === "jira" && (
        <section className={cardClass}>
          <h3 className="font-medium text-slate-100">{t("settings.jira.title")}</h3>
          {status && (
            <ConnectionBanner
              ok={status.jira_configured}
              label={t(status.jira_configured ? "settings.conn.connected" : "settings.conn.notConfigured")}
            />
          )}
          <Toggle
            label={t("settings.jira.enabled")}
            checked={form.jira_enabled}
            onChange={(v) => set("jira_enabled", v)}
          />
          <FormField label={t("settings.jira.deployment")} hint={t("settings.jira.deploymentHint")}>
            <select
              className={inputClass}
              value={form.jira_deployment}
              onChange={(e) => set("jira_deployment", e.target.value)}
            >
              <option value="cloud">{t("settings.jira.deploymentCloud")}</option>
              <option value="server">{t("settings.jira.deploymentServer")}</option>
            </select>
          </FormField>
          <FormField label={t("settings.jira.url")} hint={t("settings.jira.urlHint")}>
            <input
              className={inputClass}
              placeholder={
                form.jira_deployment === "cloud"
                  ? "https://yourorg.atlassian.net"
                  : "https://jira.example.com"
              }
              value={form.jira_url}
              onChange={(e) => set("jira_url", e.target.value)}
            />
          </FormField>
          {form.jira_deployment === "cloud" && (
            <FormField label={t("settings.jira.email")} hint={t("settings.jira.emailHint")}>
              <input
                className={inputClass}
                value={form.jira_email}
                onChange={(e) => set("jira_email", e.target.value)}
              />
            </FormField>
          )}
          <FormField
            label={
              form.jira_deployment === "cloud"
                ? t("settings.jira.token")
                : t("settings.jira.pat")
            }
            hint={secretHint(config.jira_api_token_set, t)}
          >
            <input
              className={inputClass}
              type="password"
              placeholder={config.jira_api_token_set ? "••••••••" : t("settings.notSetPlaceholder")}
              value={form.jira_api_token}
              onChange={(e) => set("jira_api_token", e.target.value)}
            />
          </FormField>
          <FormField label={t("settings.jira.projectKey")} hint={t("settings.jira.projectKeyHint")}>
            <div className="space-y-2">
              {jiraProjects.length > 0 ? (
                <select
                  className={inputClass}
                  value={form.jira_project_key}
                  onChange={(e) => set("jira_project_key", e.target.value)}
                >
                  {form.jira_project_key &&
                    !jiraProjects.some((p) => p.key === form.jira_project_key) && (
                      <option value={form.jira_project_key}>{form.jira_project_key}</option>
                    )}
                  {jiraProjects.map((p) => (
                    <option key={p.key} value={p.key}>
                      {p.name} ({p.key})
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  className={inputClass}
                  value={form.jira_project_key}
                  onChange={(e) => set("jira_project_key", e.target.value)}
                />
              )}
              <button
                type="button"
                className={testBtn}
                disabled={jiraLoading === "projects"}
                onClick={loadJiraProjects}
              >
                {jiraLoading === "projects" ? t("common.loading") : t("settings.jira.loadProjects")}
              </button>
            </div>
          </FormField>
          <FormField label={t("settings.jira.issueType")} hint={t("settings.jira.issueTypeHint")}>
            <div className="space-y-2">
              {jiraTypes.length > 0 ? (
                <select
                  className={inputClass}
                  value={form.jira_issue_type}
                  onChange={(e) => set("jira_issue_type", e.target.value)}
                >
                  {form.jira_issue_type && !jiraTypes.includes(form.jira_issue_type) && (
                    <option value={form.jira_issue_type}>{form.jira_issue_type}</option>
                  )}
                  {jiraTypes.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  className={inputClass}
                  value={form.jira_issue_type}
                  onChange={(e) => set("jira_issue_type", e.target.value)}
                />
              )}
              <button
                type="button"
                className={testBtn}
                disabled={jiraLoading === "types"}
                onClick={loadJiraTypes}
              >
                {jiraLoading === "types" ? t("common.loading") : t("settings.jira.loadTypes")}
              </button>
            </div>
          </FormField>
          <FormField label={t("settings.jira.assignee")} hint={t("settings.jira.assigneeHint")}>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <input
                  className={inputClass}
                  placeholder={t("settings.jira.assigneeNone")}
                  value={form.jira_default_assignee}
                  onChange={(e) => set("jira_default_assignee", e.target.value)}
                />
                {form.jira_default_assignee && (
                  <button
                    type="button"
                    className={testBtn}
                    onClick={() => set("jira_default_assignee", "")}
                  >
                    {t("common.delete")}
                  </button>
                )}
              </div>
              <div className="flex items-center gap-2">
                <input
                  className={inputClass}
                  placeholder={t("settings.jira.userSearchPlaceholder")}
                  value={userQuery}
                  onChange={(e) => setUserQuery(e.target.value)}
                />
                <button
                  type="button"
                  className={testBtn}
                  disabled={jiraLoading === "users"}
                  onClick={searchUsers}
                >
                  {jiraLoading === "users" ? t("common.loading") : t("settings.jira.searchUsers")}
                </button>
              </div>
              {userResults.length > 0 && (
                <ul className="divide-y divide-slate-800 rounded-lg border border-slate-800">
                  {userResults.map((u) => (
                    <li key={u.id}>
                      <button
                        type="button"
                        className="w-full px-3 py-2 text-left text-sm text-slate-300 hover:bg-slate-800"
                        onClick={() => {
                          set("jira_default_assignee", u.id);
                          setUserResults([]);
                          setUserQuery("");
                        }}
                      >
                        {u.label}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </FormField>
          <FormField label={t("settings.jira.labels")} hint={t("settings.jira.labelsHint")}>
            <input
              className={inputClass}
              placeholder="portwiz, security"
              value={form.jira_labels}
              onChange={(e) => set("jira_labels", e.target.value)}
            />
          </FormField>

          <div className="space-y-2 border-t border-slate-800 pt-3">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-medium text-slate-300">
                {t("settings.jira.priorityTitle")}
              </p>
              <button
                type="button"
                className={testBtn}
                disabled={jiraLoading === "priorities"}
                onClick={loadJiraPriorities}
              >
                {jiraLoading === "priorities"
                  ? t("common.loading")
                  : t("settings.jira.loadPriorities")}
              </button>
            </div>
            <p className="text-xs text-slate-500">{t("settings.jira.priorityHint")}</p>
            {(
              [
                ["settings.jira.sev.high", "jira_priority_high"],
                ["settings.jira.sev.medium", "jira_priority_medium"],
                ["settings.jira.sev.low", "jira_priority_low"],
              ] as [TKey, "jira_priority_high" | "jira_priority_medium" | "jira_priority_low"][]
            ).map(([label, field]) => (
              <div key={field} className="flex items-center gap-3">
                <span className="w-28 shrink-0 text-xs text-slate-400">{t(label)}</span>
                {jiraPriorities.length > 0 ? (
                  <select
                    className={inputClass}
                    value={form[field]}
                    onChange={(e) => set(field, e.target.value)}
                  >
                    <option value="">{t("settings.jira.priorityNone")}</option>
                    {form[field] && !jiraPriorities.includes(form[field]) && (
                      <option value={form[field]}>{form[field]}</option>
                    )}
                    {jiraPriorities.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    className={inputClass}
                    value={form[field]}
                    onChange={(e) => set(field, e.target.value)}
                  />
                )}
              </div>
            ))}
          </div>

          <FormField
            label={t("settings.jira.extraFields")}
            hint={t("settings.jira.extraFieldsHint")}
          >
            <textarea
              className={`${inputClass} font-mono`}
              rows={3}
              placeholder='{"customfield_10050": {"value": "Security"}}'
              value={form.jira_extra_fields}
              onChange={(e) => set("jira_extra_fields", e.target.value)}
            />
          </FormField>

          <div className="flex flex-wrap items-center gap-3">
            <button
              className={primaryBtn}
              disabled={saving === "jira"}
              onClick={() =>
                save("jira", {
                  jira_enabled: form.jira_enabled,
                  jira_deployment: form.jira_deployment,
                  jira_url: form.jira_url,
                  jira_email: form.jira_email,
                  jira_api_token: form.jira_api_token,
                  jira_project_key: form.jira_project_key,
                  jira_issue_type: form.jira_issue_type,
                  jira_default_assignee: form.jira_default_assignee,
                  jira_labels: form.jira_labels,
                  jira_priority_high: form.jira_priority_high,
                  jira_priority_medium: form.jira_priority_medium,
                  jira_priority_low: form.jira_priority_low,
                  jira_extra_fields: form.jira_extra_fields,
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
        )}

        {activeTab === "netbox" && (
        <section className={cardClass}>
          <h3 className="font-medium text-slate-100">{t("settings.netbox.title")}</h3>
          {status && (
            <ConnectionBanner
              ok={status.netbox_configured}
              label={t(status.netbox_configured ? "settings.conn.connected" : "settings.conn.notConfigured")}
            />
          )}
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
          <div className="space-y-1">
            <Toggle
              label={t("settings.netbox.writeback")}
              checked={form.netbox_writeback_enabled}
              onChange={(v) => set("netbox_writeback_enabled", v)}
            />
            <p className="text-xs text-slate-500">{t("settings.netbox.writebackHint")}</p>
          </div>
          <div className="space-y-2 rounded-lg border border-slate-800 p-3">
            <p className="text-sm font-medium text-slate-200">{t("settings.netbox.importScope")}</p>
            <p className="text-xs text-slate-500">{t("settings.netbox.importScopeHint")}</p>
            <Toggle
              label={t("settings.netbox.importAssets")}
              checked={form.netbox_import_assets}
              onChange={(v) => set("netbox_import_assets", v)}
            />
            <Toggle
              label={t("settings.netbox.importVlans")}
              checked={form.netbox_import_vlans}
              onChange={(v) => set("netbox_import_vlans", v)}
            />
            <Toggle
              label={t("settings.netbox.importHostnames")}
              checked={form.netbox_import_hostnames}
              onChange={(v) => set("netbox_import_hostnames", v)}
            />
            <Toggle
              label={t("settings.netbox.importDescriptions")}
              checked={form.netbox_import_descriptions}
              onChange={(v) => set("netbox_import_descriptions", v)}
            />
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              className={primaryBtn}
              disabled={saving === "netbox"}
              onClick={() =>
                save("netbox", {
                  netbox_enabled: form.netbox_enabled,
                  netbox_url: form.netbox_url,
                  netbox_token: form.netbox_token,
                  netbox_writeback_enabled: form.netbox_writeback_enabled,
                  netbox_import_assets: form.netbox_import_assets,
                  netbox_import_vlans: form.netbox_import_vlans,
                  netbox_import_hostnames: form.netbox_import_hostnames,
                  netbox_import_descriptions: form.netbox_import_descriptions,
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
        )}

        {activeTab === "cve" && (
        <section className={cardClass}>
          <h3 className="font-medium text-slate-100">{t("settings.cve.title")}</h3>
          {status && (
            <ConnectionBanner
              ok={status.cve_configured}
              label={t(status.cve_configured ? "settings.conn.connected" : "settings.conn.notConfigured")}
            />
          )}
          <p className="text-xs text-slate-500">{t("settings.cve.intro")}</p>
          <Toggle
            label={t("settings.cve.enabled")}
            checked={form.cve_enabled}
            onChange={(v) => set("cve_enabled", v)}
          />
          <FormField label={t("settings.cve.source")} hint={t("settings.cve.sourceHint")}>
            <select
              className={inputClass}
              value={form.cve_source}
              onChange={(e) => set("cve_source", e.target.value)}
            >
              <option value="nvd">{t("settings.cve.sourceNvd")}</option>
              <option value="offline">{t("settings.cve.sourceOffline")}</option>
            </select>
          </FormField>
          {form.cve_source === "offline" ? (
            <div className="space-y-2 rounded-lg border border-slate-800 bg-slate-950 p-3">
              <div className="flex items-start justify-between gap-3">
                <p className="text-xs text-slate-400">{t("settings.cve.offlineIntro")}</p>
                <button
                  type="button"
                  onClick={() => setCveHowToOpen(true)}
                  className="shrink-0 whitespace-nowrap rounded-md border border-sky-800 bg-sky-950/50 px-2.5 py-1 text-xs font-medium text-sky-300 hover:bg-sky-900/50"
                >
                  {t("cve.howto.open")}
                </button>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <input
                  type="file"
                  accept=".json,.gz,.json.gz"
                  className="text-xs text-slate-400 file:mr-2 file:rounded-md file:border-0 file:bg-slate-800 file:px-3 file:py-1 file:text-slate-200"
                  onChange={(e) => setCveFeedFile(e.target.files?.[0] ?? null)}
                />
                <button
                  type="button"
                  className={testBtn}
                  disabled={!cveFeedFile || cveImporting}
                  onClick={() => void onImportCveFeed()}
                >
                  {cveImporting ? t("settings.cve.importing") : t("settings.cve.importFeed")}
                </button>
              </div>
              {cveImportReport && (
                <p className="text-xs text-emerald-400">
                  {t("settings.cve.importResult", {
                    imported: cveImportReport.imported,
                    loaded: cveImportReport.loaded,
                  })}
                </p>
              )}
            </div>
          ) : (
            <>
              <FormField label={t("settings.cve.apiUrl")} hint={t("settings.cve.apiUrlHint")}>
                <input
                  className={inputClass}
                  placeholder="https://services.nvd.nist.gov/rest/json/cves/2.0"
                  value={form.cve_api_url}
                  onChange={(e) => set("cve_api_url", e.target.value)}
                />
              </FormField>
              <FormField
                label={t("settings.cve.apiKey")}
                hint={secretHint(config.cve_api_key_set, t)}
              >
                <input
                  className={inputClass}
                  type="password"
                  placeholder={config.cve_api_key_set ? "••••••••" : t("settings.notSetPlaceholder")}
                  value={form.cve_api_key}
                  onChange={(e) => set("cve_api_key", e.target.value)}
                />
              </FormField>
            </>
          )}
          <FormField label={t("settings.cve.minCvss")} hint={t("settings.cve.minCvssHint")}>
            <input
              className={inputClass}
              type="number"
              min={0}
              max={10}
              step={0.1}
              value={form.cve_min_cvss}
              onChange={(e) => set("cve_min_cvss", e.target.value)}
            />
          </FormField>
          <FormField
            label={t("settings.cve.recheckHours")}
            hint={t("settings.cve.recheckHoursHint")}
          >
            <input
              className={inputClass}
              type="number"
              min={0}
              step={1}
              value={form.cve_recheck_hours}
              onChange={(e) => set("cve_recheck_hours", e.target.value)}
            />
          </FormField>
          <div className="flex flex-wrap items-center gap-3">
            <button
              className={primaryBtn}
              disabled={saving === "cve"}
              onClick={() =>
                save("cve", {
                  cve_enabled: form.cve_enabled,
                  cve_source: form.cve_source,
                  cve_api_url: form.cve_api_url,
                  cve_api_key: form.cve_api_key,
                  cve_min_cvss: Math.min(10, Math.max(0, parseFloat(form.cve_min_cvss) || 0)),
                  cve_recheck_hours: Math.max(0, parseInt(form.cve_recheck_hours, 10) || 0),
                })
              }
            >
              {saving === "cve" ? t("common.saving") : t("common.save")}
            </button>
            <button
              className={testBtn}
              disabled={testing === "cve"}
              onClick={() => runTest("cve", testCve, setCveResult)}
            >
              {testing === "cve" ? t("settings.testing") : t("settings.testConnection")}
            </button>
          </div>
          <TestRow result={cveResult} />
        </section>
        )}

        {activeTab === "system" && (
        <section className={cardClass}>
          <h3 className="font-medium text-slate-100">{t("settings.system.title")}</h3>
          <p className="text-sm text-slate-500">{t("settings.system.subtitle")}</p>
          <FormField
            label={t("settings.system.confirmations")}
            hint={t("settings.system.confirmationsHint")}
          >
            <input
              className={inputClass}
              type="number"
              min={1}
              value={form.change_confirmations}
              onChange={(e) => set("change_confirmations", e.target.value)}
            />
          </FormField>
          <FormField
            label={t("settings.system.onlineSeconds")}
            hint={t("settings.system.onlineSecondsHint")}
          >
            <input
              className={inputClass}
              type="number"
              min={10}
              value={form.agent_online_seconds}
              onChange={(e) => set("agent_online_seconds", e.target.value)}
            />
          </FormField>
          <FormField
            label={t("settings.system.pollSeconds")}
            hint={t("settings.system.pollSecondsHint")}
          >
            <input
              className={inputClass}
              type="number"
              min={5}
              value={form.agent_poll_seconds}
              onChange={(e) => set("agent_poll_seconds", e.target.value)}
            />
          </FormField>
          <FormField
            label={t("settings.system.staleMinutes")}
            hint={t("settings.system.staleMinutesHint")}
          >
            <input
              className={inputClass}
              type="number"
              min={1}
              value={form.scan_stale_minutes}
              onChange={(e) => set("scan_stale_minutes", e.target.value)}
            />
          </FormField>
          <FormField
            label={t("settings.system.maxAttempts")}
            hint={t("settings.system.maxAttemptsHint")}
          >
            <input
              className={inputClass}
              type="number"
              min={1}
              value={form.scan_max_attempts}
              onChange={(e) => set("scan_max_attempts", e.target.value)}
            />
          </FormField>

          <p className="pt-2 text-sm font-medium text-slate-300">
            {t("settings.system.scanDefaults")}
          </p>
          <FormField label={t("settings.system.defaultPorts")} hint={t("settings.system.defaultPortsHint")}>
            <input
              className={inputClass}
              placeholder="top-1000"
              value={form.default_scan_ports}
              onChange={(e) => set("default_scan_ports", e.target.value)}
            />
          </FormField>
          <FormField label={t("settings.system.defaultScanType")}>
            <select
              className={inputClass}
              value={form.default_scan_type}
              onChange={(e) => set("default_scan_type", e.target.value)}
            >
              <option value="connect">{t("scans.scanType.connect")}</option>
              <option value="syn">{t("scans.scanType.syn")}</option>
              <option value="udp">{t("scans.scanType.udp")}</option>
            </select>
          </FormField>
          <FormField label={t("settings.system.defaultRateLimit")} hint={t("settings.system.defaultRateLimitHint")}>
            <input
              className={inputClass}
              type="number"
              min={1}
              value={form.default_scan_rate_limit_pps}
              onChange={(e) => set("default_scan_rate_limit_pps", e.target.value)}
            />
          </FormField>
          <Toggle
            label={t("settings.system.defaultServiceDetection")}
            checked={form.default_service_detection}
            onChange={(v) => set("default_service_detection", v)}
          />

          <p className="pt-2 text-sm font-medium text-slate-300">
            {t("settings.system.retention")}
          </p>
          <FormField
            label={t("settings.system.retentionObservationDays")}
            hint={t("settings.system.retentionObservationDaysHint")}
          >
            <input
              className={inputClass}
              type="number"
              min={0}
              value={form.retention_observation_days}
              onChange={(e) => set("retention_observation_days", e.target.value)}
            />
          </FormField>

          <p className="pt-2 text-sm font-medium text-slate-300">
            {t("settings.system.certExpiry")}
          </p>
          <FormField
            label={t("settings.system.certWarnDays")}
            hint={t("settings.system.certWarnDaysHint")}
          >
            <input
              className={inputClass}
              type="number"
              min={1}
              value={form.cert_expiry_warn_days}
              onChange={(e) => set("cert_expiry_warn_days", e.target.value)}
            />
          </FormField>
          <FormField
            label={t("settings.system.certRecheckHours")}
            hint={t("settings.system.certRecheckHoursHint")}
          >
            <input
              className={inputClass}
              type="number"
              min={0}
              value={form.cert_expiry_recheck_hours}
              onChange={(e) => set("cert_expiry_recheck_hours", e.target.value)}
            />
          </FormField>

          <div ref={updatesRef} className="pt-2 scroll-mt-4">
            <p className="text-sm font-medium text-slate-300">
              {t("settings.system.updates")}
            </p>
          </div>
          <Toggle
            label={t("settings.system.updateCheck")}
            checked={form.update_check_enabled}
            onChange={(v) => set("update_check_enabled", v)}
          />
          <p className="text-xs text-slate-500">{t("settings.system.updateCheckHint")}</p>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="text-slate-400">
              {t("update.current", { version: updateStatus?.current ?? "-" })}
            </span>
            {updateStatus?.update_available ? (
              <span className="text-emerald-400">
                {t("update.available", {
                  latest: updateStatus.latest ?? "",
                  current: updateStatus.current,
                })}
                {updateStatus.url && (
                  <a
                    href={updateStatus.url}
                    target="_blank"
                    rel="noreferrer"
                    className="ml-2 underline"
                  >
                    {t("update.whatsNew")}
                  </a>
                )}
              </span>
            ) : updateStatus?.enabled && updateStatus.latest ? (
              <span className="text-slate-500">{t("update.upToDate")}</span>
            ) : null}
            <button
              type="button"
              className={testBtn}
              disabled={checkingUpdate}
              onClick={() => void checkUpdateNow()}
            >
              {checkingUpdate ? t("update.checking") : t("update.checkNow")}
            </button>
          </div>
          {updateStatus?.update_available &&
            (updateApplied ? (
              <p className="rounded-lg border border-emerald-800 bg-emerald-950/40 px-3 py-2 text-xs text-emerald-300">
                {t("update.inProgress")}
              </p>
            ) : updateStatus.apply_available ? (
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  className={primaryBtn}
                  disabled={applyingUpdate}
                  onClick={() => void applyUpdateNow()}
                >
                  {applyingUpdate ? t("update.applying") : t("update.applyNow")}
                </button>
                <span className="text-xs text-slate-500">{t("update.applyHint")}</span>
              </div>
            ) : (
              <p className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 font-mono text-xs text-slate-400">
                {t("update.instructions")}
              </p>
            ))}

          <div className="flex flex-wrap items-center gap-3">
            <button
              className={primaryBtn}
              disabled={saving === "system"}
              onClick={() =>
                save("system", {
                  change_confirmations: Math.max(1, parseInt(form.change_confirmations, 10) || 2),
                  agent_online_seconds: Math.max(
                    10,
                    parseInt(form.agent_online_seconds, 10) || 120,
                  ),
                  agent_poll_seconds: Math.max(5, parseInt(form.agent_poll_seconds, 10) || 15),
                  scan_stale_minutes: Math.max(1, parseInt(form.scan_stale_minutes, 10) || 30),
                  scan_max_attempts: Math.max(1, parseInt(form.scan_max_attempts, 10) || 3),
                  default_scan_ports: form.default_scan_ports.trim() || "top-1000",
                  default_scan_type: form.default_scan_type,
                  default_service_detection: form.default_service_detection,
                  default_scan_rate_limit_pps: Math.max(
                    1,
                    parseInt(form.default_scan_rate_limit_pps, 10) || 1000,
                  ),
                  retention_observation_days: Math.max(
                    0,
                    parseInt(form.retention_observation_days, 10) || 0,
                  ),
                  cert_expiry_warn_days: Math.max(
                    1,
                    parseInt(form.cert_expiry_warn_days, 10) || 30,
                  ),
                  cert_expiry_recheck_hours: Math.max(
                    0,
                    parseInt(form.cert_expiry_recheck_hours, 10) || 0,
                  ),
                  update_check_enabled: form.update_check_enabled,
                })
              }
            >
              {saving === "system" ? t("common.saving") : t("common.save")}
            </button>
          </div>
        </section>
        )}
      </div>

      <CveHowToModal open={cveHowToOpen} onClose={() => setCveHowToOpen(false)} />
    </div>
  );
}
