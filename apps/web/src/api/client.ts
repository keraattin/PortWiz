const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API_V1 = `${BASE_URL}/api/v1`;

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export interface CurrentUser {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
}

function authHeaders(token: string | null): HeadersInit {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

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

export async function fetchMe(token: string): Promise<CurrentUser> {
  const res = await fetch(`${API_V1}/auth/me`, { headers: authHeaders(token) });
  if (!res.ok) {
    throw new ApiError(res.status, "Failed to load profile");
  }
  return (await res.json()) as CurrentUser;
}

export async function fetchHealth(): Promise<{ status: string }> {
  const res = await fetch(`${BASE_URL}/health`);
  return (await res.json()) as { status: string };
}
