"""Thread-safe in-memory data store and deterministic development seed data."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hmac import compare_digest
from threading import RLock
from uuid import uuid4

from pwdlib import PasswordHash
from starlette.requests import HTTPConnection

from .errors import conflict, forbidden, gone, not_found
from .models import (
    AuditEvent,
    CanvasDocument,
    CanvasElement,
    GuestLink,
    GuestRole,
    InterviewSession,
    Participant,
    SessionDetail,
    SessionListItem,
    TokenInspection,
    User,
)

GUEST_COOKIE_NAME = "sdip_guest_session"
GUEST_SESSION_TTL = timedelta(hours=12)
PARTICIPANT_COLORS = (
    "#5eead4",
    "#fbbf24",
    "#f472b6",
    "#a78bfa",
    "#60a5fa",
    "#34d399",
    "#fb923c",
    "#e879f9",
)
SEED_PASSWORD = "demo-password"
SEED_GUEST_TOKEN = "demo-url-shortener-guest-token"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def hash_credential(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class UserRecord:
    id: str
    email: str
    display_name: str
    organization_id: str | None
    created_at: datetime
    password_hash: str

    def public(self) -> User:
        return User(
            id=self.id,
            email=self.email,
            display_name=self.display_name,
            organization_id=self.organization_id,
            created_at=self.created_at,
        )


@dataclass(slots=True)
class GuestLinkRecord:
    id: str
    session_id: str
    token_hash: str
    role_granted: GuestRole
    expires_at: datetime | None
    max_uses: int | None
    revoked_at: datetime | None
    created_at: datetime

    def public(self, token: str | None = None) -> GuestLink:
        return GuestLink(
            id=self.id,
            session_id=self.session_id,
            # A token is returned when it is created or inspected with the
            # plaintext credential. It is intentionally redacted in stored
            # session relations because the store retains only token_hash.
            token=token if token is not None else "[redacted]",
            role_granted=self.role_granted,
            expires_at=self.expires_at,
            max_uses=self.max_uses,
            revoked_at=self.revoked_at,
            created_at=self.created_at,
        )


@dataclass(slots=True)
class GuestSessionRecord:
    token_hash: str
    participant_id: str
    expires_at: datetime


@dataclass(slots=True)
class GuestJoinResult:
    participant: Participant
    session: InterviewSession
    cookie_value: str


class InMemoryStore:
    """A small repository abstraction that can be replaced by a database later."""

    def __init__(self) -> None:
        self.lock = RLock()
        self.users: dict[str, UserRecord] = {}
        self.sessions: dict[str, InterviewSession] = {}
        self.links: dict[str, GuestLinkRecord] = {}
        self.participants: dict[str, Participant] = {}
        self.canvases: dict[str, CanvasDocument] = {}
        self.audit_events: list[AuditEvent] = []
        self.guest_sessions: dict[str, GuestSessionRecord] = {}

    @classmethod
    def seeded(cls) -> "InMemoryStore":
        """Create the development store with users, sessions, and active rooms."""

        store = cls()
        password_hash = PasswordHash.recommended()
        created = utcnow()

        store._add_user(
            UserRecord(
                id="usr_avery",
                email="avery@northwind.dev",
                display_name="Avery Chen",
                organization_id="org_northwind",
                created_at=created - timedelta(days=90),
                password_hash=password_hash.hash(SEED_PASSWORD),
            )
        )
        store._add_user(
            UserRecord(
                id="usr_jordan",
                email="jordan@northwind.dev",
                display_name="Jordan Lee",
                organization_id="org_northwind",
                created_at=created - timedelta(days=70),
                password_hash=password_hash.hash(SEED_PASSWORD),
            )
        )
        store._add_user(
            UserRecord(
                id="usr_priya",
                email="priya@northwind.dev",
                display_name="Priya Shah",
                organization_id="org_northwind",
                created_at=created - timedelta(days=45),
                password_hash=password_hash.hash(SEED_PASSWORD),
            )
        )

        live_created = created - timedelta(hours=2)
        live_started = created - timedelta(hours=1, minutes=45)
        live_updated = created - timedelta(minutes=3)
        draft_created = created - timedelta(days=1)
        ended_created = created - timedelta(days=6)
        archived_created = created - timedelta(days=21)

        store._add_session(
            InterviewSession(
                id="ses_url_shortener",
                owner_user_id="usr_avery",
                title="Senior Backend — Design a URL shortener",
                prompt=(
                    "Design a URL shortening service handling 100M new links/day with analytics "
                    "and custom aliases. Discuss data model, key generation, caching, and read scaling."
                ),
                state="live",
                candidate_editing_enabled=True,
                cursors_visible=True,
                duration_minutes=60,
                scheduled_at=live_created,
                started_at=live_started,
                ended_at=None,
                created_at=live_created,
                updated_at=live_updated,
            )
        )
        store._add_session(
            InterviewSession(
                id="ses_global_chat",
                owner_user_id="usr_jordan",
                title="Staff — Global chat infrastructure",
                prompt=(
                    "Design a realtime chat platform for 50M DAU with presence, delivery receipts, "
                    "and multi-region failover."
                ),
                state="draft",
                candidate_editing_enabled=True,
                cursors_visible=True,
                duration_minutes=75,
                scheduled_at=created + timedelta(days=2),
                started_at=None,
                ended_at=None,
                created_at=draft_created,
                updated_at=draft_created,
            )
        )
        store._add_session(
            InterviewSession(
                id="ses_ride_matching",
                owner_user_id="usr_avery",
                title="Senior — Ride matching service",
                prompt=(
                    "Design the dispatch and matching subsystem for a ride-hailing product in a dense "
                    "metro area."
                ),
                state="ended",
                candidate_editing_enabled=True,
                cursors_visible=True,
                duration_minutes=60,
                scheduled_at=ended_created,
                started_at=ended_created + timedelta(minutes=5),
                ended_at=ended_created + timedelta(hours=1, minutes=2),
                created_at=ended_created,
                updated_at=ended_created + timedelta(hours=1, minutes=2),
            )
        )
        store._add_session(
            InterviewSession(
                id="ses_metrics_pipeline",
                owner_user_id="usr_avery",
                title="Platform — Metrics ingestion pipeline",
                prompt=(
                    "Design a metrics ingestion and query pipeline handling 5M datapoints/sec with "
                    "13-month retention."
                ),
                state="archived",
                candidate_editing_enabled=False,
                cursors_visible=False,
                duration_minutes=45,
                scheduled_at=archived_created,
                started_at=archived_created,
                ended_at=archived_created + timedelta(minutes=43),
                created_at=archived_created,
                updated_at=archived_created + timedelta(minutes=43),
            )
        )

        for session_id in store.sessions:
            store.canvases[session_id] = CanvasDocument(
                id=f"doc_{session_id.removeprefix('ses_')}",
                session_id=session_id,
                schema_version=1,
                elements=[],
                updated_at=store.sessions[session_id].updated_at,
            )

        # Give the active room a small, valid architecture sketch so a real
        # frontend immediately has something useful to render.
        store.canvases["ses_url_shortener"] = CanvasDocument(
            id="doc_url_shortener",
            session_id="ses_url_shortener",
            schema_version=1,
            elements=store._seed_canvas_elements(live_updated),
            updated_at=live_updated,
        )

        store._add_participant(
            Participant(
                id="par_avery_url",
                session_id="ses_url_shortener",
                user_id="usr_avery",
                display_name="Avery Chen",
                role="owner",
                color=PARTICIPANT_COLORS[0],
                joined_at=live_started,
                left_at=None,
                connection="connected",
            )
        )
        store._add_participant(
            Participant(
                id="par_priya_url",
                session_id="ses_url_shortener",
                user_id="usr_priya",
                display_name="Priya Shah",
                role="interviewer",
                color=PARTICIPANT_COLORS[3],
                joined_at=live_started + timedelta(minutes=2),
                left_at=None,
                connection="connected",
            )
        )
        store._add_participant(
            Participant(
                id="par_sam_url",
                session_id="ses_url_shortener",
                user_id=None,
                display_name="Sam Rivera",
                role="candidate",
                color=PARTICIPANT_COLORS[1],
                joined_at=live_started + timedelta(minutes=5),
                left_at=None,
                connection="connected",
            )
        )
        store._add_participant(
            Participant(
                id="par_jordan_chat",
                session_id="ses_global_chat",
                user_id="usr_jordan",
                display_name="Jordan Lee",
                role="owner",
                color=PARTICIPANT_COLORS[0],
                joined_at=draft_created,
                left_at=None,
                connection="connected",
            )
        )
        store._add_participant(
            Participant(
                id="par_avery_ride",
                session_id="ses_ride_matching",
                user_id="usr_avery",
                display_name="Avery Chen",
                role="owner",
                color=PARTICIPANT_COLORS[0],
                joined_at=ended_created + timedelta(minutes=5),
                left_at=ended_created + timedelta(hours=1, minutes=2),
                connection="offline",
            )
        )

        store._add_link(
            GuestLinkRecord(
                id="lnk_url_shortener",
                session_id="ses_url_shortener",
                token_hash=hash_credential(SEED_GUEST_TOKEN),
                role_granted="candidate",
                expires_at=created + timedelta(days=7),
                max_uses=10,
                revoked_at=None,
                created_at=live_started,
            )
        )

        store._record_audit("ses_url_shortener", "session.created", "usr_avery", live_created)
        store._record_audit("ses_url_shortener", "session.started", "usr_avery", live_started)
        store._record_audit("ses_url_shortener", "participant.joined:Sam Rivera", "par_sam_url", live_updated)
        store._record_audit("ses_global_chat", "session.created", "usr_jordan", draft_created)
        store._record_audit("ses_ride_matching", "session.ended", "usr_avery", ended_created + timedelta(hours=1))
        return store

    @staticmethod
    def _seed_canvas_elements(at: datetime) -> list[CanvasElement]:
        return [
            {
                "id": "elm_client",
                "kind": "node",
                "created_by": "par_avery_url",
                "created_at": at,
                "updated_at": at,
                "componentType": "client",
                "x": 80,
                "y": 180,
                "width": 150,
                "height": 76,
                "label": "Client",
                "description": "Browser or mobile client",
                "color": "#60a5fa",
            },
            {
                "id": "elm_api",
                "kind": "node",
                "created_by": "par_avery_url",
                "created_at": at,
                "updated_at": at,
                "componentType": "service",
                "x": 340,
                "y": 180,
                "width": 170,
                "height": 76,
                "label": "Redirect API",
                "description": "Create and resolve short links",
                "color": "#5eead4",
            },
            {
                "id": "elm_cache",
                "kind": "node",
                "created_by": "par_avery_url",
                "created_at": at,
                "updated_at": at,
                "componentType": "cache",
                "x": 650,
                "y": 90,
                "width": 160,
                "height": 76,
                "label": "URL Cache",
                "color": "#fbbf24",
            },
            {
                "id": "elm_db",
                "kind": "node",
                "created_by": "par_avery_url",
                "created_at": at,
                "updated_at": at,
                "componentType": "database",
                "x": 650,
                "y": 270,
                "width": 160,
                "height": 76,
                "label": "Link Store",
                "color": "#a78bfa",
            },
            {
                "id": "elm_client_api",
                "kind": "connector",
                "created_by": "par_avery_url",
                "created_at": at,
                "updated_at": at,
                "from": "elm_client",
                "to": "elm_api",
                "style": "straight",
                "dashed": False,
                "arrowStart": False,
                "arrowEnd": True,
                "width": 2,
                "label": "HTTPS",
            },
            {
                "id": "elm_api_cache",
                "kind": "connector",
                "created_by": "par_avery_url",
                "created_at": at,
                "updated_at": at,
                "from": "elm_api",
                "to": "elm_cache",
                "style": "curved",
                "dashed": False,
                "arrowStart": False,
                "arrowEnd": True,
                "width": 2,
                "label": "read-through",
            },
            {
                "id": "elm_api_db",
                "kind": "connector",
                "created_by": "par_avery_url",
                "created_at": at,
                "updated_at": at,
                "from": "elm_api",
                "to": "elm_db",
                "style": "elbow",
                "dashed": False,
                "arrowStart": False,
                "arrowEnd": True,
                "width": 2,
                "label": "persist",
            },
        ]

    def _add_user(self, user: UserRecord) -> None:
        self.users[user.id] = user

    def _add_session(self, session: InterviewSession) -> None:
        self.sessions[session.id] = session

    def _add_participant(self, participant: Participant) -> None:
        self.participants[participant.id] = participant

    def _add_link(self, link: GuestLinkRecord) -> None:
        self.links[link.id] = link

    def _record_audit(
        self,
        session_id: str,
        event: str,
        actor: str,
        at: datetime | None = None,
    ) -> None:
        self.audit_events.insert(
            0,
            AuditEvent(
                id=_id("aud"),
                session_id=session_id,
                event=event,
                at=at or utcnow(),
                actor=actor,
            ),
        )

    def record_audit(self, session_id: str, event: str, actor: str) -> None:
        with self.lock:
            self._record_audit(session_id, event, actor)

    def get_user(self, user_id: str) -> UserRecord | None:
        with self.lock:
            return self.users.get(user_id)

    def find_user_by_email(self, email: str) -> UserRecord | None:
        normalized = email.casefold()
        with self.lock:
            return next((user for user in self.users.values() if user.email.casefold() == normalized), None)

    def list_sessions_for_user(self, user_id: str) -> list[SessionListItem]:
        with self.lock:
            visible = [
                session
                for session in self.sessions.values()
                if self.user_can_access(session.id, user_id)
            ]
            visible.sort(key=lambda session: session.updated_at, reverse=True)
            return [self._session_list_item(session) for session in visible]

    def _active_link(self, session_id: str) -> GuestLinkRecord | None:
        now = utcnow()
        return next(
            (
                link
                for link in self.links.values()
                if link.session_id == session_id
                and link.revoked_at is None
                and (link.expires_at is None or link.expires_at > now)
            ),
            None,
        )

    def _session_list_item(self, session: InterviewSession) -> SessionListItem:
        participants = [
            participant.model_copy(deep=True)
            for participant in self.participants.values()
            if participant.session_id == session.id
        ]
        link = self._active_link(session.id)
        return SessionListItem(
            **session.model_dump(),
            participants=participants,
            link=link.public() if link else None,
        )

    def session_detail(self, session_id: str) -> SessionDetail | None:
        with self.lock:
            session = self.sessions.get(session_id)
            if session is None:
                return None
            participants = [
                participant.model_copy(deep=True)
                for participant in self.participants.values()
                if participant.session_id == session_id and participant.left_at is None
            ]
            link = self._active_link(session_id)
            return SessionDetail(
                session=session.model_copy(deep=True),
                participants=participants,
                link=link.public() if link else None,
            )

    def get_session(self, session_id: str) -> InterviewSession | None:
        with self.lock:
            session = self.sessions.get(session_id)
            return session.model_copy(deep=True) if session else None

    def get_canvas(self, session_id: str) -> CanvasDocument | None:
        with self.lock:
            canvas = self.canvases.get(session_id)
            return canvas.model_copy(deep=True) if canvas else None

    def create_session(
        self,
        owner_user_id: str,
        title: str,
        prompt: str,
        duration_minutes: int,
        scheduled_at: datetime | None,
    ) -> InterviewSession:
        with self.lock:
            now = utcnow()
            session = InterviewSession(
                id=_id("ses"),
                owner_user_id=owner_user_id,
                title=title,
                prompt=prompt,
                state="draft",
                candidate_editing_enabled=True,
                cursors_visible=True,
                duration_minutes=duration_minutes,
                scheduled_at=scheduled_at,
                started_at=None,
                ended_at=None,
                created_at=now,
                updated_at=now,
            )
            self.sessions[session.id] = session
            self.canvases[session.id] = CanvasDocument(
                id=_id("doc"),
                session_id=session.id,
                schema_version=1,
                elements=[],
                updated_at=now,
            )
            self._record_audit(session.id, "session.created", owner_user_id, now)
            return session.model_copy(deep=True)

    def update_session(
        self,
        session_id: str,
        changes: dict[str, object],
        actor: str,
    ) -> InterviewSession | None:
        with self.lock:
            current = self.sessions.get(session_id)
            if current is None:
                return None
            updated = current.model_copy(update={**changes, "updated_at": utcnow()})
            self.sessions[session_id] = updated
            self._record_audit(session_id, "session.updated", actor)
            return updated.model_copy(deep=True)

    def transition_session(self, session_id: str, state: str, actor: str) -> InterviewSession | None:
        with self.lock:
            current = self.sessions.get(session_id)
            if current is None:
                return None
            now = utcnow()
            changes: dict[str, object] = {"state": state, "updated_at": now}
            if state == "live":
                changes["started_at"] = current.started_at or now
            elif state == "ended":
                changes["ended_at"] = now
            updated = current.model_copy(update=changes)
            self.sessions[session_id] = updated
            self._record_audit(session_id, f"session.{state}", actor)
            return updated.model_copy(deep=True)

    def duplicate_session(self, session_id: str, owner_user_id: str) -> InterviewSession | None:
        with self.lock:
            source = self.sessions.get(session_id)
            if source is None:
                return None
            now = utcnow()
            copy = source.model_copy(
                deep=True,
                update={
                    "id": _id("ses"),
                    "owner_user_id": owner_user_id,
                    "title": f"{source.title} (copy)",
                    "state": "draft",
                    "started_at": None,
                    "ended_at": None,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            self.sessions[copy.id] = copy
            source_canvas = self.canvases.get(session_id)
            self.canvases[copy.id] = CanvasDocument(
                id=_id("doc"),
                session_id=copy.id,
                schema_version=1,
                elements=source_canvas.model_copy(deep=True).elements if source_canvas else [],
                updated_at=now,
            )
            self._record_audit(copy.id, "session.duplicated", owner_user_id, now)
            return copy.model_copy(deep=True)

    def create_guest_link(self, session_id: str, role_granted: GuestRole, actor: str) -> tuple[GuestLink, str]:
        with self.lock:
            now = utcnow()
            for link in self.links.values():
                if link.session_id == session_id and link.revoked_at is None:
                    link.revoked_at = now
            raw_token = secrets.token_urlsafe(32)
            link = GuestLinkRecord(
                id=_id("lnk"),
                session_id=session_id,
                token_hash=hash_credential(raw_token),
                role_granted=role_granted,
                expires_at=now + timedelta(days=7),
                max_uses=10,
                revoked_at=None,
                created_at=now,
            )
            self.links[link.id] = link
            self._record_audit(session_id, "link.rotated", actor, now)
            return link.public(raw_token), raw_token

    def revoke_guest_link(self, session_id: str, link_id: str, actor: str) -> bool | None:
        with self.lock:
            link = self.links.get(link_id)
            if link is None or link.session_id != session_id:
                return None
            if link.revoked_at is None:
                link.revoked_at = utcnow()
            self._record_audit(session_id, "link.revoked", actor)
            return True

    def _find_guest_link(self, token: str) -> GuestLinkRecord | None:
        token_hash = hash_credential(token)
        return next(
            (link for link in self.links.values() if compare_digest(link.token_hash, token_hash)),
            None,
        )

    def _validate_guest_token(self, token: str) -> tuple[GuestLinkRecord, InterviewSession, int]:
        link = self._find_guest_link(token)
        if link is None:
            raise not_found("invalid_token", "This invitation link is not valid.")
        if link.revoked_at is not None:
            raise gone("revoked", "This invitation link has been revoked.")
        if link.expires_at is not None and link.expires_at <= utcnow():
            raise gone("expired", "This invitation link has expired.")
        session = self.sessions.get(link.session_id)
        if session is None:
            raise not_found("session_not_found", "This interview no longer exists.")
        if session.state == "archived":
            raise gone("archived", "This interview has been archived.")
        if session.state not in {"draft", "live"}:
            raise conflict("session_not_joinable", "This interview is no longer accepting participants.")
        active_count = sum(
            1
            for participant in self.participants.values()
            if participant.session_id == session.id and participant.left_at is None
        )
        if link.max_uses is not None and active_count >= link.max_uses:
            raise conflict("at_capacity", "This interview has reached its participant limit.")
        return link, session, active_count

    def inspect_guest_token(self, token: str) -> TokenInspection:
        with self.lock:
            link, session, active_count = self._validate_guest_token(token)
            return TokenInspection(
                session=session.model_copy(deep=True),
                link=link.public(token),
                activeCount=active_count,
            )

    def join_guest(self, token: str, display_name: str) -> GuestJoinResult:
        with self.lock:
            link, session, active_count = self._validate_guest_token(token)
            now = utcnow()
            participant = Participant(
                id=_id("par"),
                session_id=session.id,
                user_id=None,
                display_name=display_name,
                role=link.role_granted,
                color=PARTICIPANT_COLORS[active_count % len(PARTICIPANT_COLORS)],
                joined_at=now,
                left_at=None,
                connection="connected",
            )
            self.participants[participant.id] = participant
            cookie_value = secrets.token_urlsafe(32)
            self.guest_sessions[hash_credential(cookie_value)] = GuestSessionRecord(
                token_hash=hash_credential(cookie_value),
                participant_id=participant.id,
                expires_at=now + GUEST_SESSION_TTL,
            )
            self._record_audit(session.id, f"participant.joined:{display_name}", participant.id, now)
            return GuestJoinResult(
                participant=participant.model_copy(deep=True),
                session=session.model_copy(deep=True),
                cookie_value=cookie_value,
            )

    def resolve_guest_cookie(self, cookie_value: str) -> Participant | None:
        with self.lock:
            key = hash_credential(cookie_value)
            record = self.guest_sessions.get(key)
            if record is None:
                return None
            if record.expires_at <= utcnow():
                self.guest_sessions.pop(key, None)
                return None
            participant = self.participants.get(record.participant_id)
            if participant is None or participant.left_at is not None:
                return None
            return participant.model_copy(deep=True)

    def join_authenticated_participant(self, session_id: str, user_id: str) -> Participant:
        with self.lock:
            session = self.sessions.get(session_id)
            if session is None:
                raise not_found("session_not_found", "This interview does not exist.")
            existing = self.active_participant_for_user(session_id, user_id)
            if existing:
                return existing
            if session.owner_user_id != user_id:
                raise forbidden("Only an interviewer assigned to this session can join it.")
            user = self.users[user_id]
            participant = Participant(
                id=_id("par"),
                session_id=session_id,
                user_id=user_id,
                display_name=user.display_name,
                role="owner",
                color=PARTICIPANT_COLORS[0],
                joined_at=utcnow(),
                left_at=None,
                connection="connected",
            )
            self.participants[participant.id] = participant
            self._record_audit(session_id, "participant.joined:owner", user_id)
            return participant.model_copy(deep=True)

    def get_participant(self, session_id: str, participant_id: str) -> Participant | None:
        with self.lock:
            participant = self.participants.get(participant_id)
            if participant is None or participant.session_id != session_id:
                return None
            return participant.model_copy(deep=True)

    def active_participant_for_user(self, session_id: str, user_id: str) -> Participant | None:
        return next(
            (
                participant.model_copy(deep=True)
                for participant in self.participants.values()
                if participant.session_id == session_id
                and participant.user_id == user_id
                and participant.left_at is None
            ),
            None,
        )

    def user_can_access(self, session_id: str, user_id: str) -> bool:
        session = self.sessions.get(session_id)
        if session is None:
            return False
        if session.owner_user_id == user_id:
            return True
        return self.active_participant_for_user(session_id, user_id) is not None

    def user_can_manage(self, session_id: str, user_id: str) -> bool:
        session = self.sessions.get(session_id)
        if session is None:
            return False
        if session.owner_user_id == user_id:
            return True
        participant = self.active_participant_for_user(session_id, user_id)
        return participant is not None and participant.role == "interviewer"

    def principal_can_access(
        self,
        session_id: str,
        *,
        user_id: str | None = None,
        participant_id: str | None = None,
    ) -> bool:
        with self.lock:
            if user_id is not None:
                return self.user_can_access(session_id, user_id)
            if participant_id is not None:
                participant = self.participants.get(participant_id)
                return bool(
                    participant
                    and participant.session_id == session_id
                    and participant.left_at is None
                )
            return False

    def principal_can_edit(
        self,
        session_id: str,
        *,
        user_id: str | None = None,
        participant_id: str | None = None,
    ) -> bool:
        with self.lock:
            session = self.sessions.get(session_id)
            if session is None or session.state not in {"draft", "live"}:
                return False
            if user_id is not None:
                if session.owner_user_id == user_id:
                    return True
                participant = self.active_participant_for_user(session_id, user_id)
            elif participant_id is not None:
                participant = self.participants.get(participant_id)
                if participant and (
                    participant.session_id != session_id or participant.left_at is not None
                ):
                    participant = None
            else:
                return False
            if participant is None or participant.role == "observer":
                return False
            return participant.role != "candidate" or session.candidate_editing_enabled

    def leave_participant(self, session_id: str, participant_id: str, actor: str) -> bool | None:
        with self.lock:
            participant = self.participants.get(participant_id)
            if participant is None or participant.session_id != session_id:
                return None
            if participant.left_at is None:
                participant.left_at = utcnow()
                participant.connection = "offline"
                self._record_audit(session_id, "participant.left", actor)
            return True

    def update_presence(
        self,
        session_id: str,
        participant_id: str,
        cursor: object,
    ) -> Participant | None:
        with self.lock:
            participant = self.participants.get(participant_id)
            if participant is None or participant.session_id != session_id or participant.left_at is not None:
                return None
            participant.cursor = cursor
            participant.connection = "connected"
            return participant.model_copy(deep=True)

    def save_canvas(self, session_id: str, elements: list[CanvasElement], actor: str) -> datetime | None:
        with self.lock:
            canvas = self.canvases.get(session_id)
            session = self.sessions.get(session_id)
            if canvas is None or session is None:
                return None
            now = utcnow()
            canvas.elements = [element for element in elements]
            canvas.updated_at = now
            self.sessions[session_id] = session.model_copy(update={"updated_at": now})
            self._record_audit(session_id, "canvas.saved", actor, now)
            return now

    def list_audit(self, session_id: str) -> list[AuditEvent]:
        with self.lock:
            events = [event.model_copy(deep=True) for event in self.audit_events if event.session_id == session_id]
            events.sort(key=lambda event: event.at, reverse=True)
            return events


def get_store(connection: HTTPConnection) -> InMemoryStore:
    """Resolve the store from the ASGI application for HTTP and WebSocket calls."""

    return connection.app.state.store
