import type {
  ApprovalAction,
  AuditOut,
  ForwardAction,
  MeResponse,
  RequestOut,
  RequestWrite,
} from "@/lib/api-types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const CSRF_COOKIE = "soteops_csrf";
const CSRF_HEADER = "X-CSRF-Token";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") {
    return null;
  }
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

async function ensureCsrfToken(): Promise<string> {
  const existing = readCookie(CSRF_COOKIE);
  if (existing) {
    return existing;
  }
  const response = await fetch(`${API_BASE}/auth/csrf`, { credentials: "include" });
  if (!response.ok) {
    throw new ApiError("CSRF-tokenin haku epäonnistui", response.status);
  }
  const body = (await response.json()) as { csrf_token: string };
  return body.csrf_token;
}

function parseErrorMessage(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") {
    return fallback;
  }
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    if (first && typeof first === "object" && "msg" in first) {
      return String((first as { msg: string }).msg);
    }
  }
  return fallback;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  { csrf = false }: { csrf?: boolean } = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (csrf) {
    headers.set(CSRF_HEADER, await ensureCsrfToken());
  }
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers,
      credentials: "include",
    });
  } catch {
    throw new ApiError(
      `Selain ei saanut yhteyttä API-palvelimeen (${API_BASE}). Käynnistä paikallinen pino ja varmista, että CORS_ORIGINS sisältää tämän sivun osoitteen.`,
      0,
    );
  }
  if (response.status === 204) {
    return undefined as T;
  }
  const text = await response.text();
  const body = text ? (JSON.parse(text) as unknown) : null;
  if (!response.ok) {
    throw new ApiError(parseErrorMessage(body, response.statusText), response.status);
  }
  return body as T;
}

export const api = {
  me: () => request<MeResponse>("/auth/me"),
  login: (email: string, password: string) =>
    request<MeResponse>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) },
      { csrf: true },
    ),
  logout: () => request<{ status: string }>("/auth/logout", { method: "POST" }, { csrf: true }),
  listRequests: () => request<RequestOut[]>("/requests"),
  reviewQueue: () => request<RequestOut[]>("/review/queue"),
  getRequest: (id: string) => request<RequestOut>(`/requests/${id}`),
  createRequest: (payload: RequestWrite) =>
    request<RequestOut>("/requests", { method: "POST", body: JSON.stringify(payload) }, { csrf: true }),
  updateRequest: (id: string, payload: RequestWrite) =>
    request<RequestOut>(
      `/requests/${id}`,
      { method: "PATCH", body: JSON.stringify(payload) },
      { csrf: true },
    ),
  resubmitRequest: (id: string) =>
    request<RequestOut>(`/requests/${id}/resubmit`, { method: "POST" }, { csrf: true }),
  startReview: (id: string) =>
    request<RequestOut>(`/requests/${id}/review`, { method: "POST" }, { csrf: true }),
  approveRequest: (id: string, action: ApprovalAction) =>
    request<RequestOut>(
      `/requests/${id}/approve`,
      { method: "POST", body: JSON.stringify(action) },
      { csrf: true },
    ),
  rejectRequest: (id: string, action: ApprovalAction) =>
    request<RequestOut>(
      `/requests/${id}/reject`,
      { method: "POST", body: JSON.stringify(action) },
      { csrf: true },
    ),
  forwardRequest: (id: string, action?: ForwardAction) =>
    request<RequestOut>(
      `/requests/${id}/forward`,
      {
        method: "POST",
        body: action ? JSON.stringify(action) : undefined,
      },
      { csrf: true },
    ),
  auditTrail: (id: string) => request<AuditOut[]>(`/requests/${id}/audit`),
};

export { API_BASE };
