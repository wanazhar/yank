import type { AppConfig, DownloadOptionsIn } from "@/lib/types";

const TOKEN_KEY = "yank-connect-token";

export function getToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(TOKEN_KEY) ?? "";
}

export function setToken(token: string) {
  if (token.trim()) localStorage.setItem(TOKEN_KEY, token.trim());
  else localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(): HeadersInit {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  for (const [k, v] of Object.entries(authHeaders())) headers.set(k, v);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(path, { ...init, headers, credentials: "include" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = (body as { detail?: string }).detail ?? res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export function bootstrapPairFromUrl(): void {
  if (typeof window === "undefined") return;
  const params = new URLSearchParams(window.location.search);
  const pair = params.get("pair");
  if (!pair) return;
  window.location.replace(`/api/pair?${new URLSearchParams({ code: pair })}`);
}

export type SessionInfo = {
  authenticated: boolean;
  cookies?: { set?: boolean };
};

export async function fetchSession() {
  return apiFetch<SessionInfo>("/api/session");
}

export async function ensureSession(): Promise<boolean> {
  try {
    await fetchSession();
    return true;
  } catch {
    return false;
  }
}

export async function uploadSessionCookies(netscape: string) {
  return apiFetch<{ ok: boolean }>("/api/session/cookies", {
    method: "PUT",
    body: JSON.stringify({ netscape }),
  });
}

export async function clearSessionCookies() {
  return apiFetch<{ ok: string }>("/api/session/cookies", { method: "DELETE" });
}

export async function fetchConfig() {
  return apiFetch<AppConfig>("/api/config");
}

export async function patchConfig(patch: Partial<AppConfig>) {
  return apiFetch<AppConfig>("/api/config", {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export type FormatRow = {
  format_id: string;
  ext: string;
  resolution: string;
  filesize_display: string;
  kind: string;
  note: string;
};

export type VideoMeta = {
  url: string;
  title: string;
  duration?: number;
  uploader?: string;
  platform: string;
  thumbnail: string;
  formats: FormatRow[];
  suggested_format_id?: string;
  subtitle_langs?: string[];
};

export type PlaylistExtract = {
  playlist: true;
  entries: { url: string; title: string }[];
};

export async function extractFormats(url: string, playlist = false) {
  return apiFetch<VideoMeta | PlaylistExtract>("/api/formats/extract", {
    method: "POST",
    body: JSON.stringify({ url, playlist }),
  });
}

export type EnqueuePayload = {
  url: string;
  format_id: string;
  extract_audio?: boolean;
  audio_format?: string;
  auto_start?: boolean;
  schedule_minutes?: number;
  note?: string;
  options?: DownloadOptionsIn;
};

export async function enqueueDownload(payload: EnqueuePayload) {
  return apiFetch<{ id: string }>("/api/queue", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function enqueueBatch(
  urls: string[],
  payload: Omit<EnqueuePayload, "url">,
) {
  return apiFetch<{ items: unknown[]; errors: { url: string; error: string }[] }>("/api/queue/batch", {
    method: "POST",
    body: JSON.stringify({ urls, ...payload }),
  });
}

export type QueueItem = {
  id: string;
  title: string;
  url: string;
  status: string;
  error?: string;
  filename?: string;
  progress?: {
    percent: number;
    speed_display: string;
    eta_display: string;
    filename?: string;
  };
  downloadable?: boolean;
  streamable?: boolean;
  media_kind?: string;
  delivery?: string;
  staging_only?: boolean;
};

export type QueueResponse = {
  items: QueueItem[];
  summary?: { size: number; active: number; average_percent: number };
};

export async function fetchQueue(q = "") {
  const qs = q ? `?q=${encodeURIComponent(q)}` : "";
  return apiFetch<QueueResponse>(`/api/queue${qs}`);
}

export async function queueStartAll() {
  return apiFetch("/api/queue/start-all", { method: "POST" });
}

export async function queuePauseAll() {
  return apiFetch("/api/queue/pause-all", { method: "POST" });
}

export async function queueClearFinished() {
  return apiFetch("/api/queue/clear-finished", { method: "POST" });
}

export async function queueRetryFailed() {
  return apiFetch("/api/queue/retry-failed", { method: "POST" });
}

export async function queueItemStart(id: string) {
  return apiFetch(`/api/queue/${id}/start`, { method: "POST" });
}

export async function queueItemPause(id: string) {
  return apiFetch(`/api/queue/${id}/pause`, { method: "POST" });
}

export async function queueItemCancel(id: string) {
  return apiFetch(`/api/queue/${id}/cancel`, { method: "POST" });
}

export type HistoryEntry = {
  date: string;
  title: string;
  url: string;
  format_id: string;
  status: string;
  error?: string;
  filesize?: number;
  note?: string;
  favorite?: boolean;
};

export async function fetchHistory(q = "", status = "") {
  const p = new URLSearchParams();
  if (q) p.set("q", q);
  if (status) p.set("status", status);
  const qs = p.toString() ? `?${p}` : "";
  return apiFetch<{ entries: HistoryEntry[] }>(`/api/history${qs}`);
}

export async function historyToggleFavorite(index: number) {
  return apiFetch<{ favorite: boolean }>(`/api/history/${index}/favorite`, { method: "POST" });
}

export async function historyClear() {
  return apiFetch("/api/history", { method: "DELETE" });
}

export function withAuthQuery(path: string): string {
  if (typeof window === "undefined") return path;
  const token = getToken();
  if (!token) return path;
  const join = path.includes("?") ? "&" : "?";
  return `${path}${join}token=${encodeURIComponent(token)}`;
}

export function streamUrl(itemId: string) {
  return withAuthQuery(`/api/downloads/${itemId}/stream`);
}

export function downloadUrl(itemId: string, removeFromServer = true) {
  return withAuthQuery(
    `/api/downloads/${itemId}/file?remove_from_server=${removeFromServer ? "true" : "false"}`,
  );
}

/** Save to this device via fetch (cookies / token); optional server staging cleanup. */
export async function saveDownloadToDevice(itemId: string, filename: string) {
  const res = await fetch(downloadUrl(itemId), { credentials: "include" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = (body as { detail?: string }).detail ?? res.statusText;
    throw new Error(typeof detail === "string" ? detail : "Download failed");
  }
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  try {
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = filename || "download";
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}
