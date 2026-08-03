/**
 * MOCK BACKEND — replace with real HTTP/WebSocket calls later.
 *
 * Every function mirrors an endpoint from the spec (section 12) and returns a
 * promise with simulated latency. State lives in localStorage; realtime
 * fan-out is simulated with BroadcastChannel so multiple browser tabs behave
 * like multiple participants.
 */
import type {
  CanvasDocument,
  CanvasElement,
  GuestLink,
  InterviewSession,
  Participant,
  Role,
  SessionState,
  User,
} from "./types";

const KEY = "sdip.mock.db.v1";
const LATENCY = 140;

export interface MockDb {
  users: User[];
  currentUserId: string;
  sessions: InterviewSession[];
  links: GuestLink[];
  participants: Participant[];
  canvases: CanvasDocument[];
  audit: { id: string; session_id: string; event: string; at: string; actor: string }[];
}

export const PARTICIPANT_COLORS = [
  "#5eead4",
  "#fbbf24",
  "#f472b6",
  "#a78bfa",
  "#60a5fa",
  "#34d399",
  "#fb923c",
  "#e879f9",
];

const uid = (p: string) => `${p}_${Math.random().toString(36).slice(2, 10)}`;
const now = () => new Date().toISOString();
const token = () =>
  Array.from({ length: 4 }, () => Math.random().toString(36).slice(2, 10)).join("");

function seed(): MockDb {
  const user: User = {
    id: "usr_owner",
    email: "avery@northwind.dev",
    display_name: "Avery Chen",
    organization_id: "org_northwind",
    created_at: now(),
  };
  const mk = (
    title: string,
    prompt: string,
    state: SessionState,
    daysAgo: number,
  ): InterviewSession => {
    const at = new Date(Date.now() - daysAgo * 86400000).toISOString();
    return {
      id: uid("ses"),
      owner_user_id: user.id,
      title,
      prompt,
      state,
      candidate_editing_enabled: true,
      cursors_visible: true,
      duration_minutes: 60,
      scheduled_at: at,
      started_at: state === "draft" ? null : at,
      ended_at: state === "ended" || state === "archived" ? at : null,
      created_at: at,
      updated_at: at,
    };
  };
  const sessions = [
    mk(
      "Senior Backend — Design a URL shortener",
      "Design a URL shortening service handling 100M new links/day with analytics and custom aliases. Discuss data model, key generation, caching, and read scaling.",
      "live",
      0,
    ),
    mk(
      "Staff — Global chat infrastructure",
      "Design a realtime chat platform for 50M DAU with presence, delivery receipts, and multi-region failover.",
      "draft",
      1,
    ),
    mk(
      "Senior — Ride matching service",
      "Design the dispatch and matching subsystem for a ride-hailing product in a dense metro area.",
      "ended",
      6,
    ),
    mk(
      "Platform — Metrics ingestion pipeline",
      "Design a metrics ingestion and query pipeline handling 5M datapoints/sec with 13-month retention.",
      "archived",
      21,
    ),
  ];
  return {
    users: [user],
    currentUserId: user.id,
    sessions,
    links: [],
    participants: [],
    canvases: sessions.map((s) => ({
      id: uid("doc"),
      session_id: s.id,
      schema_version: 1,
      elements: [],
      updated_at: s.updated_at,
    })),
    audit: [],
  };
}

let memory: MockDb | null = null;

function read(): MockDb {
  if (typeof window === "undefined") return memory ?? (memory = seed());
  const raw = window.localStorage.getItem(KEY);
  if (raw) {
    try {
      return JSON.parse(raw) as MockDb;
    } catch {
      /* fall through to reseed */
    }
  }
  const db = seed();
  window.localStorage.setItem(KEY, JSON.stringify(db));
  return db;
}

function write(db: MockDb) {
  memory = db;
  if (typeof window !== "undefined") window.localStorage.setItem(KEY, JSON.stringify(db));
}

function mutate<T>(fn: (db: MockDb) => T): Promise<T> {
  return new Promise((resolve) =>
    setTimeout(() => {
      const db = read();
      const result = fn(db);
      write(db);
      resolve(result);
    }, LATENCY),
  );
}

function query<T>(fn: (db: MockDb) => T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(fn(read())), LATENCY));
}

function fail(code: string, message: string): never {
  const err = new Error(message) as Error & { code: string };
  err.code = code;
  throw err;
}

function audit(db: MockDb, session_id: string, event: string, actor: string) {
  db.audit.unshift({ id: uid("aud"), session_id, event, at: now(), actor });
}

/* ------------------------------------------------------------------ */
/* Realtime channel (mock of the collaboration gateway)                */
/* ------------------------------------------------------------------ */

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

let channel: BroadcastChannel | null = null;
function getChannel(): BroadcastChannel | null {
  if (typeof window === "undefined" || typeof BroadcastChannel === "undefined") return null;
  if (!channel) channel = new BroadcastChannel("sdip-room");
  return channel;
}

export function publish(msg: RoomMessage) {
  getChannel()?.postMessage(msg);
}

export function subscribe(sessionId: string, handler: (msg: RoomMessage) => void) {
  const ch = getChannel();
  if (!ch) return () => {};
  const listener = (e: MessageEvent<RoomMessage>) => {
    if (e.data?.sessionId === sessionId) handler(e.data);
  };
  ch.addEventListener("message", listener);
  return () => ch.removeEventListener("message", listener);
}

/* ------------------------------------------------------------------ */
/* API surface                                                         */
/* ------------------------------------------------------------------ */

export const api = {
  /** GET /v1/me */
  getCurrentUser: () => query((db) => db.users.find((u) => u.id === db.currentUserId)!),

  /** GET /v1/sessions */
  listSessions: () =>
    query((db) =>
      [...db.sessions].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).map((s) => ({
        ...s,
        participants: db.participants.filter((p) => p.session_id === s.id),
        link: db.links.find((l) => l.session_id === s.id && !l.revoked_at) ?? null,
      })),
    ),

  /** GET /v1/sessions/{id} */
  getSession: (id: string) =>
    query((db) => {
      const session = db.sessions.find((s) => s.id === id);
      if (!session) fail("session_not_found", "This interview does not exist.");
      return {
        session,
        participants: db.participants.filter((p) => p.session_id === id && !p.left_at),
        link: db.links.find((l) => l.session_id === id && !l.revoked_at) ?? null,
      };
    }),

  /** POST /v1/sessions */
  createSession: (input: {
    title: string;
    prompt: string;
    duration_minutes: number;
    scheduled_at: string | null;
  }) =>
    mutate((db) => {
      const session: InterviewSession = {
        id: uid("ses"),
        owner_user_id: db.currentUserId,
        title: input.title,
        prompt: input.prompt,
        state: "draft",
        candidate_editing_enabled: true,
        cursors_visible: true,
        duration_minutes: input.duration_minutes,
        scheduled_at: input.scheduled_at,
        started_at: null,
        ended_at: null,
        created_at: now(),
        updated_at: now(),
      };
      db.sessions.unshift(session);
      db.canvases.push({
        id: uid("doc"),
        session_id: session.id,
        schema_version: 1,
        elements: [],
        updated_at: now(),
      });
      audit(db, session.id, "session.created", db.currentUserId);
      return session;
    }),

  /** PATCH /v1/sessions/{id} */
  updateSession: (id: string, patch: Partial<InterviewSession>) =>
    mutate((db) => {
      const s = db.sessions.find((x) => x.id === id);
      if (!s) fail("session_not_found", "This interview does not exist.");
      Object.assign(s, patch, { updated_at: now() });
      audit(db, id, "session.updated", db.currentUserId);
      publish({ type: "permission_changed", sessionId: id, session: { ...s } });
      return { ...s };
    }),

  /** POST /v1/sessions/{id}/start */
  startSession: (id: string) =>
    mutate((db) => {
      const s = db.sessions.find((x) => x.id === id);
      if (!s) fail("session_not_found", "This interview does not exist.");
      s.state = "live";
      s.started_at = s.started_at ?? now();
      s.updated_at = now();
      audit(db, id, "session.started", db.currentUserId);
      publish({ type: "permission_changed", sessionId: id, session: { ...s } });
      return { ...s };
    }),

  /** POST /v1/sessions/{id}/end */
  endSession: (id: string) =>
    mutate((db) => {
      const s = db.sessions.find((x) => x.id === id);
      if (!s) fail("session_not_found", "This interview does not exist.");
      s.state = "ended";
      s.ended_at = now();
      s.updated_at = now();
      audit(db, id, "session.ended", db.currentUserId);
      publish({ type: "session_ended", sessionId: id });
      return { ...s };
    }),

  /** POST /v1/sessions/{id}/archive */
  archiveSession: (id: string) =>
    mutate((db) => {
      const s = db.sessions.find((x) => x.id === id);
      if (!s) fail("session_not_found", "This interview does not exist.");
      s.state = "archived";
      s.updated_at = now();
      audit(db, id, "session.archived", db.currentUserId);
      return { ...s };
    }),

  /** POST /v1/sessions/{id}/duplicate */
  duplicateSession: (id: string) =>
    mutate((db) => {
      const src = db.sessions.find((x) => x.id === id);
      if (!src) fail("session_not_found", "This interview does not exist.");
      const copy: InterviewSession = {
        ...src,
        id: uid("ses"),
        title: `${src.title} (copy)`,
        state: "draft",
        started_at: null,
        ended_at: null,
        created_at: now(),
        updated_at: now(),
      };
      db.sessions.unshift(copy);
      const srcDoc = db.canvases.find((c) => c.session_id === id);
      db.canvases.push({
        id: uid("doc"),
        session_id: copy.id,
        schema_version: 1,
        elements: srcDoc ? JSON.parse(JSON.stringify(srcDoc.elements)) : [],
        updated_at: now(),
      });
      return copy;
    }),

  /** POST /v1/sessions/{id}/guest-links */
  createGuestLink: (id: string, role_granted: Exclude<Role, "owner"> = "candidate") =>
    mutate((db) => {
      db.links
        .filter((l) => l.session_id === id && !l.revoked_at)
        .forEach((l) => (l.revoked_at = now()));
      const link: GuestLink = {
        id: uid("lnk"),
        session_id: id,
        token: token(),
        role_granted,
        expires_at: new Date(Date.now() + 7 * 86400000).toISOString(),
        max_uses: 10,
        revoked_at: null,
        created_at: now(),
      };
      db.links.push(link);
      audit(db, id, "link.rotated", db.currentUserId);
      return link;
    }),

  /** DELETE /v1/sessions/{id}/guest-links/{linkId} */
  revokeGuestLink: (id: string, linkId: string) =>
    mutate((db) => {
      const l = db.links.find((x) => x.id === linkId);
      if (l) l.revoked_at = now();
      audit(db, id, "link.revoked", db.currentUserId);
      return true;
    }),

  /** GET /v1/join/{token} — lobby pre-check */
  inspectToken: (tok: string) =>
    query((db) => {
      const link = db.links.find((l) => l.token === tok);
      if (!link) fail("invalid_token", "This link is not valid.");
      if (link.revoked_at) fail("revoked", "This invitation link has been revoked.");
      if (link.expires_at && link.expires_at < now()) fail("expired", "This link has expired.");
      const session = db.sessions.find((s) => s.id === link.session_id);
      if (!session) fail("session_not_found", "This interview no longer exists.");
      if (session.state === "archived") fail("archived", "This interview has been archived.");
      const active = db.participants.filter((p) => p.session_id === session.id && !p.left_at);
      if (link.max_uses && active.length >= link.max_uses)
        fail("at_capacity", "This interview has reached its participant limit.");
      return { session, link, activeCount: active.length };
    }),

  /** POST /v1/join/{token} */
  join: (tok: string, display_name: string) =>
    mutate((db) => {
      const link = db.links.find((l) => l.token === tok && !l.revoked_at);
      if (!link) fail("invalid_token", "This link is no longer valid.");
      const session = db.sessions.find((s) => s.id === link.session_id)!;
      const used = db.participants.filter((p) => p.session_id === session.id).length;
      const participant: Participant = {
        id: uid("par"),
        session_id: session.id,
        user_id: null,
        display_name,
        role: link.role_granted,
        color: PARTICIPANT_COLORS[used % PARTICIPANT_COLORS.length]!,
        joined_at: now(),
        left_at: null,
        connection: "connected",
      };
      db.participants.push(participant);
      audit(db, session.id, `participant.joined:${display_name}`, participant.id);
      publish({ type: "presence_update", sessionId: session.id, participant });
      return { participant, session };
    }),

  /** Owner/interviewer self-join (already authenticated) */
  joinAsOwner: (sessionId: string) =>
    mutate((db) => {
      const user = db.users.find((u) => u.id === db.currentUserId)!;
      let p = db.participants.find(
        (x) => x.session_id === sessionId && x.user_id === user.id && !x.left_at,
      );
      if (!p) {
        p = {
          id: uid("par"),
          session_id: sessionId,
          user_id: user.id,
          display_name: user.display_name,
          role: "owner",
          color: PARTICIPANT_COLORS[0]!,
          joined_at: now(),
          left_at: null,
          connection: "connected",
        };
        db.participants.push(p);
      }
      publish({ type: "presence_update", sessionId, participant: p });
      return p;
    }),

  /** DELETE /v1/sessions/{id}/participants/{pid} */
  removeParticipant: (sessionId: string, participantId: string) =>
    mutate((db) => {
      const p = db.participants.find((x) => x.id === participantId);
      if (p) p.left_at = now();
      audit(db, sessionId, "participant.removed", db.currentUserId);
      publish({ type: "presence_leave", sessionId, participantId });
      return true;
    }),

  leave: (sessionId: string, participantId: string) =>
    mutate((db) => {
      const p = db.participants.find((x) => x.id === participantId);
      if (p) p.left_at = now();
      publish({ type: "presence_leave", sessionId, participantId });
      return true;
    }),

  /** GET /v1/sessions/{id}/canvas */
  getCanvas: (sessionId: string) =>
    query((db) => {
      const doc = db.canvases.find((c) => c.session_id === sessionId);
      if (!doc) fail("canvas_not_found", "Canvas unavailable.");
      return doc;
    }),

  /** Autosave — batched persistent operations */
  saveCanvas: (sessionId: string, elements: CanvasElement[], actor: string) =>
    mutate((db) => {
      const doc = db.canvases.find((c) => c.session_id === sessionId);
      if (!doc) fail("canvas_not_found", "Canvas unavailable.");
      doc.elements = elements;
      doc.updated_at = now();
      const s = db.sessions.find((x) => x.id === sessionId);
      if (s) s.updated_at = now();
      publish({ type: "document_update", sessionId, elements, actor });
      return doc.updated_at;
    }),

  getAudit: (sessionId: string) =>
    query((db) => db.audit.filter((a) => a.session_id === sessionId)),

  resetMockData: () => {
    if (typeof window !== "undefined") window.localStorage.removeItem(KEY);
    memory = null;
  },
};
