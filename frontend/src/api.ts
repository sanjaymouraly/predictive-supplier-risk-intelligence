/**
 * Typed API client for Predictive Supplier Risk Intelligence.
 *
 * Authentication: a JWT issued by ``POST /api/auth/login`` is kept in
 * localStorage and attached to every request. In local demo mode the backend
 * additionally accepts an ``X-Demo-Role`` header so CLI/API exploration still
 * works without a token.
 */

const TOKEN_KEY = 'sri_access_token';
const USER_KEY = 'sri_current_user';

export interface AuthUser {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): AuthUser | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function storeSession(token: string, user: AuthUser): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

function authHeaders(): Headers {
  const headers = new Headers();
  const token = getToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  return headers;
}

export async function apiFetch<T = any>(
  path: string,
  options: RequestInit = {},
  role: string = 'procurement_lead'
): Promise<T> {
  const headers = new Headers(options.headers || {});
  const token = getToken();

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  } else if (!headers.has('X-Demo-Role')) {
    // Local demo convenience only. Ignored by the backend when ALLOW_DEMO_MODE=false.
    headers.set('X-Demo-Role', role);
  }

  if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const res = await fetch(path, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    clearSession();
    window.dispatchEvent(new Event('sri:unauthorized'));
  }

  if (!res.ok) {
    let errDetail = `HTTP ${res.status}`;
    try {
      const errJson = await res.json();
      errDetail = errJson.detail || errJson.message || errDetail;
    } catch {
      // ignore non-JSON error bodies
    }
    throw new Error(errDetail);
  }

  return res.json() as Promise<T>;
}

/** Download a file through the authenticated API rather than a bare anchor tag. */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const res = await fetch(path, { headers: authHeaders() });
  if (!res.ok) {
    throw new Error(`Download failed (HTTP ${res.status})`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
