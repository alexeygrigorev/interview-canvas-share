// Domain types mirroring the MVP spec data model (section 11).

export type SessionState = "draft" | "live" | "ended" | "archived";
export type Role = "owner" | "interviewer" | "candidate" | "observer";

export interface User {
  id: string;
  email: string;
  display_name: string;
  organization_id: string | null;
  created_at: string;
}

export interface InterviewSession {
  id: string;
  owner_user_id: string;
  title: string;
  prompt: string;
  state: SessionState;
  candidate_editing_enabled: boolean;
  cursors_visible: boolean;
  duration_minutes: number;
  scheduled_at: string | null;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface GuestLink {
  id: string;
  session_id: string;
  token: string; // mock only — real backend stores token_hash
  role_granted: Exclude<Role, "owner">;
  expires_at: string | null;
  max_uses: number | null;
  revoked_at: string | null;
  created_at: string;
}

export interface Participant {
  id: string;
  session_id: string;
  user_id: string | null;
  display_name: string;
  role: Role;
  color: string;
  joined_at: string;
  left_at: string | null;
  connection: "connected" | "reconnecting" | "offline";
  cursor?: { x: number; y: number } | null;
}

export interface CanvasDocument {
  id: string;
  session_id: string;
  schema_version: number;
  elements: CanvasElement[];
  updated_at: string;
}

export type ElementKind = "node" | "connector" | "stroke" | "text" | "note";

export interface BaseElement {
  id: string;
  kind: ElementKind;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface NodeElement extends BaseElement {
  kind: "node" | "text" | "note";
  componentType: string;
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
  description?: string;
  color?: string;
}

export interface ConnectorElement extends BaseElement {
  kind: "connector";
  from: string;
  to: string;
  style: "straight" | "elbow" | "curved";
  dashed: boolean;
  arrowStart: boolean;
  arrowEnd: boolean;
  width: number;
  label: string;
}

export interface StrokeElement extends BaseElement {
  kind: "stroke";
  points: number[]; // flat [x,y,...]
  color: string;
  width: number;
  opacity: number;
}

export type CanvasElement = NodeElement | ConnectorElement | StrokeElement;

export interface ApiError extends Error {
  code: string;
}
