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

// Users
export function listUsers(): Promise<CurrentUser[]> {
  return request<CurrentUser[]>("/users");
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

// Scans
export type ScanType = "syn" | "connect" | "udp";
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
