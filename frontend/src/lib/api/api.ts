import type {
  CanvasDocument,
  CanvasElement,
  GuestLink,
  InterviewSession,
  Participant,
  Role,
  User,
} from "./types";

const DEFAULT_API_BASE_URL = import.meta.env.DEV ? "http://localhost:8091" : "";
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, "");
const DEV_EMAIL = import.meta.env.VITE_API_EMAIL ?? "avery@northwind.dev";
const DEV_PASSWORD = import.meta.env.VITE_API_PASSWORD ?? "demo-password";
const ACCESS_TOKEN_KEY = "sdip.access-token";

type ApiErrorBody = { code?: string; message?: string };

export type RoomMessage =
  | { type: "document_update"; sessionId: string; elements: CanvasElement[]; actor: string }
  | {
      type: "presence_update";
      sessionId: string;
      participant: Participant;
      cursor?: { x: number; y: number } | null;
    }
  | { type: "presence_leave"; sessionId: string; participantId: string }
  | { type: "permission_changed"; sessionId: string; session: InterviewSession }
  | { type: "session_ended"; sessionId: string };

interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  user: User;
}

interface SessionDetail {
  session: InterviewSession;
  participants: Participant[];
  link: GuestLink | null;
}

interface SessionListItem extends InterviewSession {
  participants: Participant[];
  link: GuestLink | null;
}

interface TokenInspection {
  session: InterviewSession;
  link: GuestLink;
  activeCount: number;
}

interface AuditEvent {
  id: string;
  session_id: string;
  event: string;
  at: string;
  actor: string;
}

let accessToken: string | null = null;
let loginRequest: Promise<string> | null = null;

function readStoredToken() {
  if (accessToken) return accessToken;
  if (typeof window !== "undefined") accessToken = window.sessionStorage.getItem(ACCESS_TOKEN_KEY);
  return accessToken;
}

function storeToken(token: string) {
  accessToken = token;
  if (typeof window !== "undefined") window.sessionStorage.setItem(ACCESS_TOKEN_KEY, token);
}

function clearToken() {
  accessToken = null;
  if (typeof window !== "undefined") window.sessionStorage.removeItem(ACCESS_TOKEN_KEY);
}

async function parseError(response: Response) {
  const body = (await response.json().catch(() => null)) as ApiErrorBody | null;
  const error = new Error(
    body?.message ?? `The API request failed (${response.status}).`,
  ) as Error & {
    code: string;
    status: number;
  };
  error.code = body?.code ?? "api_error";
  error.status = response.status;
  return error;
}

async function login(): Promise<string> {
  const stored = readStoredToken();
  if (stored) return stored;
  if (!loginRequest) {
    loginRequest = fetch(`${API_BASE_URL}/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: DEV_EMAIL, password: DEV_PASSWORD }),
    })
      .then(async (response) => {
        if (!response.ok) throw await parseError(response);
        const result = (await response.json()) as TokenResponse;
        storeToken(result.access_token);
        return result.access_token;
      })
      .finally(() => {
        loginRequest = null;
      });
  }
  return loginRequest;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  authenticated = true,
  retryAfterLogin = true,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (authenticated) headers.set("Authorization", `Bearer ${await login()}`);

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });
  if (response.status === 401 && authenticated && retryAfterLogin) {
    clearToken();
    return request<T>(path, options, authenticated, false);
  }
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as T;
}

function isGuestSession(sessionId: string) {
  return (
    typeof window !== "undefined" && window.sessionStorage.getItem(`sdip.me.${sessionId}`) !== null
  );
}

function sessionRequest<T>(sessionId: string, path: string, options?: RequestInit) {
  return request<T>(path, options, !isGuestSession(sessionId));
}

interface RoomConnection {
  socket: WebSocket | null;
  subscribers: Set<(message: RoomMessage) => void>;
  pending: RoomMessage[];
  reconnectTimer: ReturnType<typeof setTimeout> | null;
  closed: boolean;
}

const rooms = new Map<string, RoomConnection>();

function websocketUrl(sessionId: string) {
  const url = new URL(API_BASE_URL || window.location.origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = `${url.pathname.replace(/\/$/, "")}/v1/sessions/${encodeURIComponent(sessionId)}/realtime`;
  url.search = "";
  return url.toString();
}

async function connect(sessionId: string, room: RoomConnection) {
  if (room.closed || room.socket) return;
  const protocols = ["sdip"];
  if (!isGuestSession(sessionId)) protocols.push(`bearer.${await login()}`);
  if (room.closed || room.socket) return;

  const socket = new WebSocket(websocketUrl(sessionId), protocols);
  room.socket = socket;
  socket.addEventListener("open", () => {
    for (const message of room.pending.splice(0)) socket.send(JSON.stringify(message));
  });
  socket.addEventListener("message", (event) => {
    try {
      const message = JSON.parse(String(event.data)) as RoomMessage;
      if ("type" in message) room.subscribers.forEach((subscriber) => subscriber(message));
    } catch {
      // Ignore malformed gateway messages; valid protocol messages are JSON objects.
    }
  });
  socket.addEventListener("close", (event) => {
    if (room.socket === socket) room.socket = null;
    if (event.code === 4401 && !isGuestSession(sessionId)) clearToken();
    if (!room.closed && room.subscribers.size > 0) {
      room.reconnectTimer = setTimeout(() => void connect(sessionId, room), 1000);
    }
  });
}

function getRoom(sessionId: string) {
  let room = rooms.get(sessionId);
  if (!room) {
    room = {
      socket: null,
      subscribers: new Set(),
      pending: [],
      reconnectTimer: null,
      closed: false,
    };
    rooms.set(sessionId, room);
  }
  return room;
}

export function publish(message: RoomMessage) {
  if (typeof window === "undefined") return;
  const room = getRoom(message.sessionId);
  if (room.socket?.readyState === WebSocket.OPEN) room.socket.send(JSON.stringify(message));
  else room.pending.push(message);
  void connect(message.sessionId, room);
}

export function subscribe(sessionId: string, handler: (message: RoomMessage) => void) {
  if (typeof window === "undefined") return () => {};
  const room = getRoom(sessionId);
  room.closed = false;
  room.subscribers.add(handler);
  void connect(sessionId, room);
  return () => {
    room.subscribers.delete(handler);
    if (room.subscribers.size === 0) {
      room.closed = true;
      if (room.reconnectTimer) clearTimeout(room.reconnectTimer);
      room.socket?.close(1000, "Room no longer in use");
      rooms.delete(sessionId);
    }
  };
}

export const api = {
  getCurrentUser: () => request<User>("/v1/me"),
  listSessions: () => request<SessionListItem[]>("/v1/sessions"),
  getSession: (id: string) =>
    sessionRequest<SessionDetail>(id, `/v1/sessions/${encodeURIComponent(id)}`),
  createSession: (input: {
    title: string;
    prompt: string;
    duration_minutes: number;
    scheduled_at: string | null;
  }) => request<InterviewSession>("/v1/sessions", { method: "POST", body: JSON.stringify(input) }),
  updateSession: (id: string, patch: Partial<InterviewSession>) =>
    request<InterviewSession>(`/v1/sessions/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  startSession: (id: string) =>
    request<InterviewSession>(`/v1/sessions/${encodeURIComponent(id)}/start`, { method: "POST" }),
  endSession: (id: string) =>
    request<InterviewSession>(`/v1/sessions/${encodeURIComponent(id)}/end`, { method: "POST" }),
  archiveSession: (id: string) =>
    request<InterviewSession>(`/v1/sessions/${encodeURIComponent(id)}/archive`, { method: "POST" }),
  duplicateSession: (id: string) =>
    request<InterviewSession>(`/v1/sessions/${encodeURIComponent(id)}/duplicate`, {
      method: "POST",
    }),
  createGuestLink: (id: string, role_granted: Exclude<Role, "owner"> = "candidate") =>
    request<GuestLink>(`/v1/sessions/${encodeURIComponent(id)}/guest-links`, {
      method: "POST",
      body: JSON.stringify({ role_granted }),
    }),
  revokeGuestLink: (id: string, linkId: string) =>
    request<boolean>(
      `/v1/sessions/${encodeURIComponent(id)}/guest-links/${encodeURIComponent(linkId)}`,
      { method: "DELETE" },
    ),
  inspectToken: (token: string) =>
    request<TokenInspection>(`/v1/join/${encodeURIComponent(token)}`, {}, false),
  join: (token: string, display_name: string) =>
    request<{ participant: Participant; session: InterviewSession }>(
      `/v1/join/${encodeURIComponent(token)}`,
      { method: "POST", body: JSON.stringify({ display_name }) },
      false,
    ),
  joinAsOwner: (sessionId: string) =>
    request<Participant>(`/v1/sessions/${encodeURIComponent(sessionId)}/participants`, {
      method: "POST",
    }),
  removeParticipant: (sessionId: string, participantId: string) =>
    sessionRequest<boolean>(
      sessionId,
      `/v1/sessions/${encodeURIComponent(sessionId)}/participants/${encodeURIComponent(participantId)}`,
      { method: "DELETE" },
    ),
  leave: (sessionId: string, participantId: string) =>
    sessionRequest<boolean>(
      sessionId,
      `/v1/sessions/${encodeURIComponent(sessionId)}/participants/${encodeURIComponent(participantId)}`,
      { method: "DELETE" },
    ),
  getCanvas: (sessionId: string) =>
    sessionRequest<CanvasDocument>(
      sessionId,
      `/v1/sessions/${encodeURIComponent(sessionId)}/canvas`,
    ),
  saveCanvas: (sessionId: string, elements: CanvasElement[], actor: string) =>
    sessionRequest<string>(sessionId, `/v1/sessions/${encodeURIComponent(sessionId)}/canvas`, {
      method: "PUT",
      body: JSON.stringify({ elements, actor }),
    }),
  getAudit: (sessionId: string) =>
    request<AuditEvent[]>(`/v1/sessions/${encodeURIComponent(sessionId)}/audit`),
};
