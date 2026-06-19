const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API_V1 = `${BASE_URL}/api/v1`;
const TOKEN_KEY = "portwiz_token";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// Global 401 handler: AuthContext registers this so an expired or invalid token
// logs the user out and bounces to /login, instead of stranding them behind
// repeated "could not validate credentials" errors. 403 (insufficient role) is
// deliberately not handled here.
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null): void {
  onUnauthorized = fn;
}

function handleUnauthorized(): void {
  clearToken();
  onUnauthorized?.();
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${API_V1}${path}`, { ...init, headers });
  if (res.status === 204) {
    return undefined as T;
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401) handleUnauthorized();
    const detail =
      data && typeof data.detail === "string" ? data.detail : res.statusText;
    throw new ApiError(res.status, detail);
  }
  return data as T;
}

// Types
export type Criticality = "low" | "medium" | "high" | "critical";
export type DataSensitivity = "none" | "pii" | "cde" | "ephi";

export interface CurrentUser {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface Vlan {
  id: string;
  name: string;
  vlan_tag: number | null;
  description: string | null;
  created_at: string;
}

export interface Asset {
  id: string;
  ip: string;
  hostname: string | null;
  vlan_id: string | null;
  owner_id: string | null;
  criticality: Criticality;
  data_sensitivity: DataSensitivity;
  description: string | null;
  created_at: string;
  updated_at: string;
}

// Auth
export async function login(email: string, password: string): Promise<string> {
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${API_V1}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) {
    throw new ApiError(res.status, "Incorrect email or password");
  }
  const data = (await res.json()) as { access_token: string };
  return data.access_token;
}

export function fetchMe(): Promise<CurrentUser> {
  return request<CurrentUser>("/auth/me");
}

export async function fetchHealth(): Promise<{ status: string }> {
  const res = await fetch(`${BASE_URL}/health`);
  return (await res.json()) as { status: string };
}

// Dashboard overview
export interface DashboardStats {
  assets: number;
  vlans: number;
  agents_total: number;
  agents_online: number;
  open_changes: number;
  open_tasks: number;
  pending_runs: number;
  last_scan_at: string | null;
}

export function fetchStats(): Promise<DashboardStats> {
  return request<DashboardStats>("/stats");
}

export interface TimePoint {
  date: string;
  count: number;
}

export interface ChartSlice {
  name: string;
  value: number;
}

export interface DashboardCharts {
  changes_by_day: TimePoint[];
  changes_by_type: ChartSlice[];
  assets_by_criticality: ChartSlice[];
  runs_by_status: ChartSlice[];
  compliance_by_status: ChartSlice[];
}

export function fetchCharts(): Promise<DashboardCharts> {
  return request<DashboardCharts>("/stats/charts");
}

// Users
export type Role = "admin" | "operator" | "auditor";

export interface UserCreateInput {
  email: string;
  password: string;
  full_name?: string | null;
  role: Role;
}

export function listUsers(): Promise<CurrentUser[]> {
  return request<CurrentUser[]>("/users");
}

export function createUser(payload: UserCreateInput): Promise<CurrentUser> {
  return request<CurrentUser>("/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export interface UserUpdateInput {
  full_name?: string | null;
  role?: Role;
  is_active?: boolean;
}

export function updateUser(id: string, payload: UserUpdateInput): Promise<CurrentUser> {
  return request<CurrentUser>(`/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

// VLANs
export function listVlans(): Promise<Vlan[]> {
  return request<Vlan[]>("/vlans");
}

export function createVlan(payload: {
  name: string;
  vlan_tag?: number | null;
  description?: string | null;
}): Promise<Vlan> {
  return request<Vlan>("/vlans", { method: "POST", body: JSON.stringify(payload) });
}

export function deleteVlan(id: string): Promise<void> {
  return request<void>(`/vlans/${id}`, { method: "DELETE" });
}

// IP ranges
export interface IpRange {
  id: string;
  cidr: string;
  vlan_id: string | null;
  description: string | null;
  created_at: string;
}

export function listIpRanges(): Promise<IpRange[]> {
  return request<IpRange[]>("/ip-ranges");
}

export function createIpRange(payload: {
  cidr: string;
  vlan_id?: string | null;
  description?: string | null;
}): Promise<IpRange> {
  return request<IpRange>("/ip-ranges", { method: "POST", body: JSON.stringify(payload) });
}

export function deleteIpRange(id: string): Promise<void> {
  return request<void>(`/ip-ranges/${id}`, { method: "DELETE" });
}

// Assets
export interface AssetInput {
  ip: string;
  hostname?: string | null;
  vlan_id?: string | null;
  owner_id?: string | null;
  criticality?: Criticality;
  data_sensitivity?: DataSensitivity;
  description?: string | null;
}

export function listAssets(params?: { vlan_id?: string }): Promise<Asset[]> {
  const query = params?.vlan_id ? `?vlan_id=${params.vlan_id}` : "";
  return request<Asset[]>(`/assets${query}`);
}

export function createAsset(payload: AssetInput): Promise<Asset> {
  return request<Asset>("/assets", { method: "POST", body: JSON.stringify(payload) });
}

export function updateAsset(id: string, payload: Partial<AssetInput>): Promise<Asset> {
  return request<Asset>(`/assets/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteAsset(id: string): Promise<void> {
  return request<void>(`/assets/${id}`, { method: "DELETE" });
}

// Bulk import (CSV / Excel)
export interface AssetImportRowResult {
  row: number;
  ip: string | null;
  status: string; // created | updated | skipped | error
  error: string | null;
}

export interface AssetImportReport {
  total: number;
  created: number;
  updated: number;
  skipped: number;
  errors: number;
  results: AssetImportRowResult[];
}

export async function importAssets(
  file: File,
  onConflict: "update" | "skip" = "update",
): Promise<AssetImportReport> {
  // Multipart upload: let the browser set the Content-Type boundary, so we
  // don't go through the JSON request() helper.
  const token = getToken();
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_V1}/assets/import?on_conflict=${onConflict}`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401) handleUnauthorized();
    const detail =
      data && typeof data.detail === "string" ? data.detail : res.statusText;
    throw new ApiError(res.status, detail);
  }
  return data as AssetImportReport;
}

export interface VlanImportRowResult {
  row: number;
  name: string | null;
  status: string; // created | updated | skipped | error
  error: string | null;
}
export interface VlanImportReport {
  total: number;
  created: number;
  updated: number;
  skipped: number;
  errors: number;
  results: VlanImportRowResult[];
}

export async function importVlans(
  file: File,
  onConflict: "update" | "skip" = "update",
): Promise<VlanImportReport> {
  const token = getToken();
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_V1}/vlans/import?on_conflict=${onConflict}`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401) handleUnauthorized();
    const detail = data && typeof data.detail === "string" ? data.detail : res.statusText;
    throw new ApiError(res.status, detail);
  }
  return data as VlanImportReport;
}

export async function downloadVlanImportTemplate(): Promise<void> {
  const res = await authedFetch("/vlans/import-template");
  triggerDownload(await res.blob(), "portwiz-vlans-template.csv");
}

// Sync from an external inventory source (NetBox)
export interface AssetSyncReport {
  source: string;
  total: number;
  created: number;
  updated: number;
  skipped: number;
  errors: number;
  errors_detail: string[];
}

export function syncAssets(onConflict: "update" | "skip" = "update"): Promise<AssetSyncReport> {
  return request<AssetSyncReport>(`/assets/sync?on_conflict=${onConflict}`, {
    method: "POST",
  });
}

// Scans
export type ScanType = "syn" | "connect" | "udp";
export type ComplianceFramework = "pci" | "hipaa" | "soc2" | "iso27001" | "nist";
export type ScanSource =
  | "internal-authenticated"
  | "internal-unauthenticated"
  | "external-asv";
export type ScanRunStatus =
  | "pending"
  | "running"
  | "completed"
  | "partial"
  | "failed";

export interface ScanProfile {
  id: string;
  name: string;
  targets: string[];
  ports: string;
  scan_type: ScanType;
  service_detection: boolean;
  rate_limit_pps: number;
  scan_source: ScanSource;
  segment: string | null;
  compliance_framework: ComplianceFramework | null;
  cron: string | null;
  enabled: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScanRun {
  id: string;
  scan_profile_id: string | null;
  agent_id: string | null;
  status: ScanRunStatus;
  scan_source: ScanSource;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  created_at: string;
}

export interface Observation {
  id: string;
  ts: string;
  scan_run_id: string;
  asset_id: string | null;
  ip: string;
  port: number;
  protocol: string;
  state: string;
  service: string | null;
  version: string | null;
  product: string | null;
  banner_sha256: string | null;
  fingerprint_confidence: number | null;
}

export interface ScanProfileInput {
  name: string;
  targets: string[];
  ports?: string;
  scan_type?: ScanType;
  service_detection?: boolean;
  segment?: string | null;
  compliance_framework?: ComplianceFramework | null;
  cron?: string | null;
}

export function listScanProfiles(): Promise<ScanProfile[]> {
  return request<ScanProfile[]>("/scan-profiles");
}

export function createScanProfile(payload: ScanProfileInput): Promise<ScanProfile> {
  return request<ScanProfile>("/scan-profiles", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteScanProfile(id: string): Promise<void> {
  return request<void>(`/scan-profiles/${id}`, { method: "DELETE" });
}

export function runScanProfile(id: string): Promise<ScanRun> {
  return request<ScanRun>(`/scan-profiles/${id}/run`, { method: "POST" });
}

export function listScanRuns(): Promise<ScanRun[]> {
  return request<ScanRun[]>("/scan-runs");
}

export function listRunObservations(runId: string): Promise<Observation[]> {
  return request<Observation[]>(`/scan-runs/${runId}/observations`);
}

// Scan agents
export interface Agent {
  id: string;
  name: string;
  segment: string | null;
  enabled: boolean;
  last_seen_at: string | null;
  created_at: string;
}

export interface EnrolledAgent {
  id: string;
  name: string;
  segment: string | null;
  token: string; // shown only once, at enrollment
  created_at: string;
}

export function listAgents(): Promise<Agent[]> {
  return request<Agent[]>("/agents");
}

export function enrollAgent(name: string, segment?: string | null): Promise<EnrolledAgent> {
  return request<EnrolledAgent>("/agents", {
    method: "POST",
    body: JSON.stringify({ name, segment: segment || null }),
  });
}

export interface AgentUpdateInput {
  segment?: string | null;
  enabled?: boolean;
}

export function updateAgent(id: string, payload: AgentUpdateInput): Promise<Agent> {
  return request<Agent>(`/agents/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteAgent(id: string): Promise<void> {
  return request<void>(`/agents/${id}`, { method: "DELETE" });
}

// Changes
export type ChangeType = "opened" | "closed" | "service_changed" | "version_changed";
export type ChangeStatus = "open" | "acknowledged" | "resolved";

export interface PortSnapshot {
  state?: string;
  service?: string | null;
  version?: string | null;
}

export interface ChangeEvent {
  id: string;
  scan_profile_id: string;
  scan_run_id: string | null;
  asset_id: string | null;
  ip: string;
  port: number;
  protocol: string;
  change_type: ChangeType;
  before: PortSnapshot;
  after: PortSnapshot;
  severity: string;
  status: ChangeStatus;
  detected_at: string;
}

export function listChanges(params?: { status?: string }): Promise<ChangeEvent[]> {
  const query = params?.status ? `?status=${params.status}` : "";
  return request<ChangeEvent[]>(`/changes${query}`);
}

export function updateChangeStatus(
  id: string,
  status: ChangeStatus,
): Promise<ChangeEvent> {
  return request<ChangeEvent>(`/changes/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

// Audit log
export interface AuditEvent {
  seq: number;
  actor_id: string | null;
  actor_email: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  payload: Record<string, unknown>;
  prev_hash: string;
  hash: string;
  created_at: string;
}

export interface AuditPage {
  total: number;
  events: AuditEvent[];
}

export interface ChainVerification {
  ok: boolean;
  broken_seq: number | null;
  total: number;
}

export function listAudit(params?: {
  action?: string;
  actor_email?: string;
  limit?: number;
  offset?: number;
}): Promise<AuditPage> {
  const qs = new URLSearchParams();
  if (params?.action) qs.set("action", params.action);
  if (params?.actor_email) qs.set("actor_email", params.actor_email);
  qs.set("limit", String(params?.limit ?? 50));
  qs.set("offset", String(params?.offset ?? 0));
  return request<AuditPage>(`/audit?${qs.toString()}`);
}

export function verifyAudit(): Promise<ChainVerification> {
  return request<ChainVerification>("/audit/verify");
}

// Evidence downloads (auth header is required, so we fetch and save a blob)
function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function authedFetch(path: string): Promise<Response> {
  const token = getToken();
  const res = await fetch(`${API_V1}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    if (res.status === 401) handleUnauthorized();
    throw new ApiError(res.status, "Download failed");
  }
  return res;
}

export async function downloadEvidenceJson(profileId: string, profileName: string): Promise<void> {
  const res = await authedFetch(`/evidence/scan-profiles/${profileId}`);
  const data = await res.json();
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  triggerDownload(blob, `portwiz-evidence-${profileName}.json`);
}

export async function downloadEvidencePdf(profileId: string, profileName: string): Promise<void> {
  const res = await authedFetch(`/evidence/scan-profiles/${profileId}/pdf`);
  triggerDownload(await res.blob(), `portwiz-evidence-${profileName}.pdf`);
}

export async function downloadAssetImportTemplate(): Promise<void> {
  const res = await authedFetch("/assets/import-template");
  triggerDownload(await res.blob(), "portwiz-assets-template.csv");
}

// Compliance cadence
export interface ComplianceStatusItem {
  profile_id: string;
  profile_name: string;
  framework: string;
  cadence_days: number;
  last_scan_at: string | null;
  days_since: number | null;
  status: string; // compliant | due_soon | overdue | never
  scan_source: string;
  asv_satisfied: boolean;
}

export function fetchComplianceStatus(): Promise<ComplianceStatusItem[]> {
  return request<ComplianceStatusItem[]>("/compliance/status");
}

// Tasks
export type TaskStatus = "open" | "in_progress" | "done" | "cancelled";

export interface Task {
  id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  change_event_id: string | null;
  assignee_id: string | null;
  created_by: string | null;
  jira_key: string | null;
  created_at: string;
  updated_at: string;
}

export function listTasks(params?: { status?: string }): Promise<Task[]> {
  const query = params?.status ? `?task_status=${params.status}` : "";
  return request<Task[]>(`/tasks${query}`);
}

export function updateTask(
  id: string,
  payload: { status?: TaskStatus; assignee_id?: string | null },
): Promise<Task> {
  return request<Task>(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function linkTaskToJira(id: string): Promise<Task> {
  return request<Task>(`/tasks/${id}/jira`, { method: "POST" });
}

export function syncTaskFromJira(id: string): Promise<Task> {
  return request<Task>(`/tasks/${id}/jira/sync`, { method: "POST" });
}

// Settings / integrations (non-secret status + admin test actions)
export interface SettingsStatus {
  app_name: string;
  environment: string;
  version: string;
  ai_provider: string;
  ai_model: string;
  ai_configured: boolean;
  email_enabled: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_from: string;
  email_recipients: string[];
  jira_enabled: boolean;
  jira_url: string | null;
  jira_project_key: string;
  jira_configured: boolean;
  netbox_enabled: boolean;
  netbox_url: string | null;
  netbox_configured: boolean;
}

export interface TestResult {
  ok: boolean;
  detail: string;
}

export function fetchSettings(): Promise<SettingsStatus> {
  return request<SettingsStatus>("/settings");
}

export function testAi(): Promise<TestResult> {
  return request<TestResult>("/settings/test/ai", { method: "POST" });
}

export function testEmail(recipient?: string): Promise<TestResult> {
  return request<TestResult>("/settings/test/email", {
    method: "POST",
    body: JSON.stringify({ recipient: recipient || null }),
  });
}

export function testJira(): Promise<TestResult> {
  return request<TestResult>("/settings/test/jira", { method: "POST" });
}

export function testNetbox(): Promise<TestResult> {
  return request<TestResult>("/settings/test/netbox", { method: "POST" });
}

// Editable settings (admin). Secrets are never returned; a `*_set` flag reports
// whether each is currently set.
export interface SettingsConfig {
  ai_provider: string;
  ollama_base_url: string;
  ollama_model: string;
  anthropic_model: string;
  anthropic_api_key_set: boolean;
  compat_base_url: string;
  compat_model: string;
  compat_api_key_set: boolean;
  notifications_enabled: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_from: string;
  smtp_username: string | null;
  smtp_use_tls: boolean;
  smtp_password_set: boolean;
  notification_recipients: string[];
  jira_enabled: boolean;
  jira_url: string | null;
  jira_email: string | null;
  jira_project_key: string;
  jira_api_token_set: boolean;
  netbox_enabled: boolean;
  netbox_url: string | null;
  netbox_token_set: boolean;
}

export type SettingsConfigUpdate = Partial<{
  ai_provider: string;
  ollama_base_url: string;
  ollama_model: string;
  anthropic_api_key: string;
  anthropic_model: string;
  compat_base_url: string;
  compat_model: string;
  compat_api_key: string;
  notifications_enabled: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_from: string;
  smtp_username: string;
  smtp_password: string;
  smtp_use_tls: boolean;
  notification_recipients: string[];
  jira_enabled: boolean;
  jira_url: string;
  jira_email: string;
  jira_api_token: string;
  jira_project_key: string;
  netbox_enabled: boolean;
  netbox_url: string;
  netbox_token: string;
}>;

export function fetchSettingsConfig(): Promise<SettingsConfig> {
  return request<SettingsConfig>("/settings/config");
}

export function updateSettingsConfig(payload: SettingsConfigUpdate): Promise<SettingsConfig> {
  return request<SettingsConfig>("/settings/config", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export interface AiProviderInfo {
  id: string;
  label: string;
  kind: string; // "none" | "ollama" | "anthropic" | "openai_compat"
  default_base_url: string;
  default_model: string;
  needs_api_key: boolean;
  needs_base_url: boolean;
  console_url: string;
}

export function fetchAiProviders(): Promise<AiProviderInfo[]> {
  return request<AiProviderInfo[]>("/settings/ai-providers");
}

// Agentic assistant: chat + proposed actions the user confirms.
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ActionRequest {
  method: string;
  path: string;
  body: Record<string, unknown> | null;
}

export interface ProposedAction {
  name: string;
  summary: Record<string, unknown>;
  request: ActionRequest;
}

export interface ChatResult {
  provider: string;
  reply: string;
  action: ProposedAction | null;
}

export function chatAssistant(messages: ChatMessage[]): Promise<ChatResult> {
  return request<ChatResult>("/ai/chat", {
    method: "POST",
    body: JSON.stringify({ messages }),
  });
}

// Execute a server-built action request (the path/body are constructed
// server-side from the catalog, then run here with the user's own token).
export function executeAction(req: ActionRequest): Promise<unknown> {
  return request(req.path, {
    method: req.method,
    body: req.body != null ? JSON.stringify(req.body) : undefined,
  });
}
