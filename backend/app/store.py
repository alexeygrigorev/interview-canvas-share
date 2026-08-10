"""Database-backed repository and deterministic development seed data."""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pwdlib import PasswordHash
from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import HTTPConnection

from .database import (
    AuditEventRow,
    CanvasRow,
    GuestLinkRow,
    GuestSessionRow,
    InterviewSessionRow,
    ParticipantRow,
    UserRow,
    create_database_engine,
    create_session_factory,
    initialize_schema,
    lock_schema,
)
from .errors import conflict, forbidden, gone, not_found
from .models import (
    AuditEvent,
    CanvasDocument,
    CanvasElement,
    Cursor,
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
    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


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
class GuestJoinResult:
    participant: Participant
    session: InterviewSession
    cookie_value: str


class DatabaseStore:
    """Synchronous repository backed by any SQLAlchemy-supported database."""

    def __init__(self, engine: Engine):
        self.engine = engine
        self.session_factory: sessionmaker[Session] = create_session_factory(engine)
        initialize_schema(engine)

    @classmethod
    def from_url(cls, url: str | None = None) -> DatabaseStore:
        return cls(create_database_engine(url))

    @classmethod
    def seeded(cls, url: str | None = "sqlite://") -> DatabaseStore:
        store = cls.from_url(url)
        store.seed()
        return store

    @contextmanager
    def _transaction(self) -> Iterator[Session]:
        database = self.session_factory()
        try:
            yield database
            database.commit()
        except Exception:
            database.rollback()
            raise
        finally:
            database.close()

    def seed(self) -> None:
        """Seed an empty database, leaving existing databases untouched."""

        with self._transaction() as database:
            lock_schema(database)
            if database.scalar(select(func.count()).select_from(UserRow)):
                return
            password_hash = PasswordHash.recommended()
            now = utcnow()
            users = [
                UserRow(
                    id="usr_avery",
                    email="avery@northwind.dev",
                    display_name="Avery Chen",
                    organization_id="org_northwind",
                    created_at=now - timedelta(days=90),
                    password_hash=password_hash.hash(SEED_PASSWORD),
                ),
                UserRow(
                    id="usr_jordan",
                    email="jordan@northwind.dev",
                    display_name="Jordan Lee",
                    organization_id="org_northwind",
                    created_at=now - timedelta(days=70),
                    password_hash=password_hash.hash(SEED_PASSWORD),
                ),
                UserRow(
                    id="usr_priya",
                    email="priya@northwind.dev",
                    display_name="Priya Shah",
                    organization_id="org_northwind",
                    created_at=now - timedelta(days=45),
                    password_hash=password_hash.hash(SEED_PASSWORD),
                ),
            ]
            database.add_all(users)
            # No ORM relationships are mapped, so the unit of work cannot infer
            # that sessions and participants depend on these rows; flush each
            # level explicitly to satisfy the foreign keys PostgreSQL enforces.
            database.flush()
            live_created = now - timedelta(hours=2)
            live_started = now - timedelta(hours=1, minutes=45)
            live_updated = now - timedelta(minutes=3)
            draft_created = now - timedelta(days=1)
            ended_created = now - timedelta(days=6)
            archived_created = now - timedelta(days=21)
            sessions = [
                InterviewSessionRow(
                    id="ses_url_shortener",
                    owner_user_id="usr_avery",
                    title="Senior Backend — Design a URL shortener",
                    prompt="Design a URL shortening service handling 100M new links/day with analytics and custom aliases. Discuss data model, key generation, caching, and read scaling.",
                    state="live",
                    candidate_editing_enabled=True,
                    cursors_visible=True,
                    duration_minutes=60,
                    scheduled_at=live_created,
                    started_at=live_started,
                    ended_at=None,
                    created_at=live_created,
                    updated_at=live_updated,
                ),
                InterviewSessionRow(
                    id="ses_global_chat",
                    owner_user_id="usr_jordan",
                    title="Staff — Global chat infrastructure",
                    prompt="Design a realtime chat platform for 50M DAU with presence, delivery receipts, and multi-region failover.",
                    state="draft",
                    candidate_editing_enabled=True,
                    cursors_visible=True,
                    duration_minutes=75,
                    scheduled_at=now + timedelta(days=2),
                    started_at=None,
                    ended_at=None,
                    created_at=draft_created,
                    updated_at=draft_created,
                ),
                InterviewSessionRow(
                    id="ses_ride_matching",
                    owner_user_id="usr_avery",
                    title="Senior — Ride matching service",
                    prompt="Design the dispatch and matching subsystem for a ride-hailing product in a dense metro area.",
                    state="ended",
                    candidate_editing_enabled=True,
                    cursors_visible=True,
                    duration_minutes=60,
                    scheduled_at=ended_created,
                    started_at=ended_created + timedelta(minutes=5),
                    ended_at=ended_created + timedelta(hours=1, minutes=2),
                    created_at=ended_created,
                    updated_at=ended_created + timedelta(hours=1, minutes=2),
                ),
                InterviewSessionRow(
                    id="ses_metrics_pipeline",
                    owner_user_id="usr_avery",
                    title="Platform — Metrics ingestion pipeline",
                    prompt="Design a metrics ingestion and query pipeline handling 5M datapoints/sec with 13-month retention.",
                    state="archived",
                    candidate_editing_enabled=False,
                    cursors_visible=False,
                    duration_minutes=45,
                    scheduled_at=archived_created,
                    started_at=archived_created,
                    ended_at=archived_created + timedelta(minutes=43),
                    created_at=archived_created,
                    updated_at=archived_created + timedelta(minutes=43),
                ),
            ]
            database.add_all(sessions)
            database.flush()
            database.add_all(
                [
                    CanvasRow(
                        id="doc_url_shortener",
                        session_id="ses_url_shortener",
                        schema_version=1,
                        elements=self._seed_canvas_elements(live_updated),
                        updated_at=live_updated,
                    ),
                    CanvasRow(
                        id="doc_global_chat",
                        session_id="ses_global_chat",
                        schema_version=1,
                        elements=[],
                        updated_at=draft_created,
                    ),
                    CanvasRow(
                        id="doc_ride_matching",
                        session_id="ses_ride_matching",
                        schema_version=1,
                        elements=[],
                        updated_at=ended_created + timedelta(hours=1, minutes=2),
                    ),
                    CanvasRow(
                        id="doc_metrics_pipeline",
                        session_id="ses_metrics_pipeline",
                        schema_version=1,
                        elements=[],
                        updated_at=archived_created + timedelta(minutes=43),
                    ),
                ]
            )
            database.add_all(
                [
                    ParticipantRow(
                        id="par_avery_url",
                        session_id="ses_url_shortener",
                        user_id="usr_avery",
                        display_name="Avery Chen",
                        role="owner",
                        color=PARTICIPANT_COLORS[0],
                        joined_at=live_started,
                        left_at=None,
                        connection="connected",
                        cursor=None,
                    ),
                    ParticipantRow(
                        id="par_priya_url",
                        session_id="ses_url_shortener",
                        user_id="usr_priya",
                        display_name="Priya Shah",
                        role="interviewer",
                        color=PARTICIPANT_COLORS[3],
                        joined_at=live_started + timedelta(minutes=2),
                        left_at=None,
                        connection="connected",
                        cursor=None,
                    ),
                    ParticipantRow(
                        id="par_sam_url",
                        session_id="ses_url_shortener",
                        user_id=None,
                        display_name="Sam Rivera",
                        role="candidate",
                        color=PARTICIPANT_COLORS[1],
                        joined_at=live_started + timedelta(minutes=5),
                        left_at=None,
                        connection="connected",
                        cursor=None,
                    ),
                    ParticipantRow(
                        id="par_jordan_chat",
                        session_id="ses_global_chat",
                        user_id="usr_jordan",
                        display_name="Jordan Lee",
                        role="owner",
                        color=PARTICIPANT_COLORS[0],
                        joined_at=draft_created,
                        left_at=None,
                        connection="connected",
                        cursor=None,
                    ),
                    ParticipantRow(
                        id="par_avery_ride",
                        session_id="ses_ride_matching",
                        user_id="usr_avery",
                        display_name="Avery Chen",
                        role="owner",
                        color=PARTICIPANT_COLORS[0],
                        joined_at=ended_created + timedelta(minutes=5),
                        left_at=ended_created + timedelta(hours=1, minutes=2),
                        connection="offline",
                        cursor=None,
                    ),
                ]
            )
            database.add(
                GuestLinkRow(
                    id="lnk_url_shortener",
                    session_id="ses_url_shortener",
                    token_hash=hash_credential(SEED_GUEST_TOKEN),
                    role_granted="candidate",
                    expires_at=now + timedelta(days=7),
                    max_uses=10,
                    revoked_at=None,
                    created_at=live_started,
                )
            )
            self._record_audit(
                database,
                "ses_url_shortener",
                "session.created",
                "usr_avery",
                live_created,
            )
            self._record_audit(
                database,
                "ses_url_shortener",
                "session.started",
                "usr_avery",
                live_started,
            )
            self._record_audit(
                database,
                "ses_url_shortener",
                "participant.joined:Sam Rivera",
                "par_sam_url",
                live_updated,
            )
            self._record_audit(
                database,
                "ses_global_chat",
                "session.created",
                "usr_jordan",
                draft_created,
            )
            self._record_audit(
                database,
                "ses_ride_matching",
                "session.ended",
                "usr_avery",
                ended_created + timedelta(hours=1),
            )

    @staticmethod
    def _seed_canvas_elements(at: datetime) -> list[dict[str, object]]:
        common: dict[str, object] = {
            "created_by": "par_avery_url",
            "created_at": at.isoformat(),
            "updated_at": at.isoformat(),
        }
        return [
            {
                **common,
                "id": "elm_client",
                "kind": "node",
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
                **common,
                "id": "elm_api",
                "kind": "node",
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
                **common,
                "id": "elm_cache",
                "kind": "node",
                "componentType": "cache",
                "x": 650,
                "y": 90,
                "width": 160,
                "height": 76,
                "label": "URL Cache",
                "color": "#fbbf24",
            },
            {
                **common,
                "id": "elm_db",
                "kind": "node",
                "componentType": "database",
                "x": 650,
                "y": 270,
                "width": 160,
                "height": 76,
                "label": "Link Store",
                "color": "#a78bfa",
            },
            {
                **common,
                "id": "elm_client_api",
                "kind": "connector",
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
                **common,
                "id": "elm_api_cache",
                "kind": "connector",
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
                **common,
                "id": "elm_api_db",
                "kind": "connector",
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

    @staticmethod
    def _user(row: UserRow) -> UserRecord:
        return UserRecord(
            row.id,
            row.email,
            row.display_name,
            row.organization_id,
            _aware(row.created_at),
            row.password_hash,
        )  # type: ignore[arg-type]

    @staticmethod
    def _session(row: InterviewSessionRow) -> InterviewSession:
        return InterviewSession.model_validate(
            {
                column.name: _aware(getattr(row, column.name))
                if isinstance(getattr(row, column.name), datetime)
                else getattr(row, column.name)
                for column in InterviewSessionRow.__table__.columns
            }
        )

    @staticmethod
    def _participant(row: ParticipantRow) -> Participant:
        return Participant(
            id=row.id,
            session_id=row.session_id,
            user_id=row.user_id,
            display_name=row.display_name,
            role=row.role,
            color=row.color,
            joined_at=_aware(row.joined_at),
            left_at=_aware(row.left_at),
            connection=row.connection,
            cursor=Cursor.model_validate(row.cursor) if row.cursor else None,
        )  # type: ignore[arg-type]

    @staticmethod
    def _link(row: GuestLinkRow, token: str = "[redacted]") -> GuestLink:
        return GuestLink(
            id=row.id,
            session_id=row.session_id,
            token=token,
            role_granted=row.role_granted,
            expires_at=_aware(row.expires_at),
            max_uses=row.max_uses,
            revoked_at=_aware(row.revoked_at),
            created_at=_aware(row.created_at),
        )  # type: ignore[arg-type]

    @staticmethod
    def _canvas(row: CanvasRow) -> CanvasDocument:
        return CanvasDocument(
            id=row.id,
            session_id=row.session_id,
            schema_version=row.schema_version,
            elements=row.elements,
            updated_at=_aware(row.updated_at),
        )  # type: ignore[arg-type]

    @staticmethod
    def _active_participant_query(
        session_id: str, user_id: str
    ) -> Select[tuple[ParticipantRow]]:
        return select(ParticipantRow).where(
            ParticipantRow.session_id == session_id,
            ParticipantRow.user_id == user_id,
            ParticipantRow.left_at.is_(None),
        )

    def _record_audit(
        self,
        database: Session,
        session_id: str,
        event: str,
        actor: str,
        at: datetime | None = None,
    ) -> None:
        database.add(
            AuditEventRow(
                id=_id("aud"),
                session_id=session_id,
                event=event,
                at=at or utcnow(),
                actor=actor,
            )
        )

    def record_audit(self, session_id: str, event: str, actor: str) -> None:
        with self._transaction() as database:
            self._record_audit(database, session_id, event, actor)

    def get_user(self, user_id: str) -> UserRecord | None:
        with self._transaction() as database:
            row = database.get(UserRow, user_id)
            return self._user(row) if row else None

    def find_user_by_email(self, email: str) -> UserRecord | None:
        with self._transaction() as database:
            row = database.scalar(
                select(UserRow).where(func.lower(UserRow.email) == email.casefold())
            )
            return self._user(row) if row else None

    def _active_link(self, database: Session, session_id: str) -> GuestLinkRow | None:
        now = utcnow()
        return database.scalar(
            select(GuestLinkRow)
            .where(
                GuestLinkRow.session_id == session_id,
                GuestLinkRow.revoked_at.is_(None),
                or_(GuestLinkRow.expires_at.is_(None), GuestLinkRow.expires_at > now),
            )
            .order_by(GuestLinkRow.created_at.desc())
        )

    def _can_access(
        self, database: Session, session: InterviewSessionRow, user_id: str
    ) -> bool:
        return (
            session.owner_user_id == user_id
            or database.scalar(self._active_participant_query(session.id, user_id))
            is not None
        )

    def list_sessions_for_user(self, user_id: str) -> list[SessionListItem]:
        with self._transaction() as database:
            rows = database.scalars(
                select(InterviewSessionRow)
                .where(
                    or_(
                        InterviewSessionRow.owner_user_id == user_id,
                        InterviewSessionRow.id.in_(
                            select(ParticipantRow.session_id).where(
                                ParticipantRow.user_id == user_id,
                                ParticipantRow.left_at.is_(None),
                            )
                        ),
                    )
                )
                .order_by(InterviewSessionRow.updated_at.desc())
            ).all()
            result = []
            for row in rows:
                participants = [
                    self._participant(item)
                    for item in database.scalars(
                        select(ParticipantRow).where(
                            ParticipantRow.session_id == row.id
                        )
                    ).all()
                ]
                link = self._active_link(database, row.id)
                result.append(
                    SessionListItem(
                        **self._session(row).model_dump(),
                        participants=participants,
                        link=self._link(link) if link else None,
                    )
                )
            return result

    def session_detail(self, session_id: str) -> SessionDetail | None:
        with self._transaction() as database:
            row = database.get(InterviewSessionRow, session_id)
            if row is None:
                return None
            participants = [
                self._participant(item)
                for item in database.scalars(
                    select(ParticipantRow).where(
                        ParticipantRow.session_id == session_id,
                        ParticipantRow.left_at.is_(None),
                    )
                ).all()
            ]
            link = self._active_link(database, session_id)
            return SessionDetail(
                session=self._session(row),
                participants=participants,
                link=self._link(link) if link else None,
            )

    def get_session(self, session_id: str) -> InterviewSession | None:
        with self._transaction() as database:
            row = database.get(InterviewSessionRow, session_id)
            return self._session(row) if row else None

    def get_canvas(self, session_id: str) -> CanvasDocument | None:
        with self._transaction() as database:
            row = database.scalar(
                select(CanvasRow).where(CanvasRow.session_id == session_id)
            )
            return self._canvas(row) if row else None

    def create_session(
        self,
        owner_user_id: str,
        title: str,
        prompt: str,
        duration_minutes: int,
        scheduled_at: datetime | None,
    ) -> InterviewSession:
        with self._transaction() as database:
            now = utcnow()
            row = InterviewSessionRow(
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
            database.add(row)
            database.flush()
            database.add(
                CanvasRow(
                    id=_id("doc"),
                    session_id=row.id,
                    schema_version=1,
                    elements=[],
                    updated_at=now,
                )
            )
            self._record_audit(database, row.id, "session.created", owner_user_id, now)
            return self._session(row)

    def update_session(
        self, session_id: str, changes: dict[str, object], actor: str
    ) -> InterviewSession | None:
        with self._transaction() as database:
            row = database.get(InterviewSessionRow, session_id)
            if row is None:
                return None
            for name, value in changes.items():
                setattr(row, name, value)
            row.updated_at = utcnow()
            self._record_audit(database, session_id, "session.updated", actor)
            database.flush()
            return self._session(row)

    def transition_session(
        self, session_id: str, state: str, actor: str
    ) -> InterviewSession | None:
        with self._transaction() as database:
            row = database.get(InterviewSessionRow, session_id)
            if row is None:
                return None
            now = utcnow()
            row.state = state
            row.updated_at = now
            if state == "live":
                row.started_at = row.started_at or now
            elif state == "ended":
                row.ended_at = now
            self._record_audit(database, session_id, f"session.{state}", actor)
            database.flush()
            return self._session(row)

    def duplicate_session(
        self, session_id: str, owner_user_id: str
    ) -> InterviewSession | None:
        with self._transaction() as database:
            source = database.get(InterviewSessionRow, session_id)
            if source is None:
                return None
            now = utcnow()
            row = InterviewSessionRow(
                id=_id("ses"),
                owner_user_id=owner_user_id,
                title=f"{source.title} (copy)",
                prompt=source.prompt,
                state="draft",
                candidate_editing_enabled=source.candidate_editing_enabled,
                cursors_visible=source.cursors_visible,
                duration_minutes=source.duration_minutes,
                scheduled_at=source.scheduled_at,
                started_at=None,
                ended_at=None,
                created_at=now,
                updated_at=now,
            )
            database.add(row)
            database.flush()
            source_canvas = database.scalar(
                select(CanvasRow).where(CanvasRow.session_id == session_id)
            )
            database.add(
                CanvasRow(
                    id=_id("doc"),
                    session_id=row.id,
                    schema_version=1,
                    elements=source_canvas.elements if source_canvas else [],
                    updated_at=now,
                )
            )
            self._record_audit(
                database, row.id, "session.duplicated", owner_user_id, now
            )
            return self._session(row)

    def create_guest_link(
        self, session_id: str, role_granted: GuestRole, actor: str
    ) -> tuple[GuestLink, str]:
        with self._transaction() as database:
            now = utcnow()
            database.execute(
                update(GuestLinkRow)
                .where(
                    GuestLinkRow.session_id == session_id,
                    GuestLinkRow.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
            raw_token = secrets.token_urlsafe(32)
            row = GuestLinkRow(
                id=_id("lnk"),
                session_id=session_id,
                token_hash=hash_credential(raw_token),
                role_granted=role_granted,
                expires_at=now + timedelta(days=7),
                max_uses=10,
                revoked_at=None,
                created_at=now,
            )
            database.add(row)
            self._record_audit(database, session_id, "link.rotated", actor, now)
            database.flush()
            return self._link(row, raw_token), raw_token

    def revoke_guest_link(
        self, session_id: str, link_id: str, actor: str
    ) -> bool | None:
        with self._transaction() as database:
            row = database.get(GuestLinkRow, link_id)
            if row is None or row.session_id != session_id:
                return None
            row.revoked_at = row.revoked_at or utcnow()
            self._record_audit(database, session_id, "link.revoked", actor)
            return True

    def get_guest_link_hash(self, link_id: str) -> str | None:
        with self._transaction() as database:
            row = database.get(GuestLinkRow, link_id)
            return row.token_hash if row else None

    def _validate_guest_token(
        self, database: Session, token: str
    ) -> tuple[GuestLinkRow, InterviewSessionRow, int]:
        link = database.scalar(
            select(GuestLinkRow).where(
                GuestLinkRow.token_hash == hash_credential(token)
            )
        )
        if link is None:
            raise not_found("invalid_token", "This invitation link is not valid.")
        if link.revoked_at is not None:
            raise gone("revoked", "This invitation link has been revoked.")
        if _aware(link.expires_at) is not None and _aware(link.expires_at) <= utcnow():  # type: ignore[operator]
            raise gone("expired", "This invitation link has expired.")
        session = database.get(InterviewSessionRow, link.session_id)
        if session is None:
            raise not_found("session_not_found", "This interview no longer exists.")
        if session.state == "archived":
            raise gone("archived", "This interview has been archived.")
        if session.state not in {"draft", "live"}:
            raise conflict(
                "session_not_joinable",
                "This interview is no longer accepting participants.",
            )
        active_count = (
            database.scalar(
                select(func.count())
                .select_from(ParticipantRow)
                .where(
                    ParticipantRow.session_id == session.id,
                    ParticipantRow.left_at.is_(None),
                )
            )
            or 0
        )
        if link.max_uses is not None and active_count >= link.max_uses:
            raise conflict(
                "at_capacity", "This interview has reached its participant limit."
            )
        return link, session, active_count

    def inspect_guest_token(self, token: str) -> TokenInspection:
        with self._transaction() as database:
            link, session, active_count = self._validate_guest_token(database, token)
            return TokenInspection(
                session=self._session(session),
                link=self._link(link, token),
                activeCount=active_count,
            )

    def join_guest(self, token: str, display_name: str) -> GuestJoinResult:
        with self._transaction() as database:
            link, session, active_count = self._validate_guest_token(database, token)
            now = utcnow()
            row = ParticipantRow(
                id=_id("par"),
                session_id=session.id,
                user_id=None,
                display_name=display_name,
                role=link.role_granted,
                color=PARTICIPANT_COLORS[active_count % len(PARTICIPANT_COLORS)],
                joined_at=now,
                left_at=None,
                connection="connected",
                cursor=None,
            )
            database.add(row)
            database.flush()
            cookie_value = secrets.token_urlsafe(32)
            database.add(
                GuestSessionRow(
                    token_hash=hash_credential(cookie_value),
                    participant_id=row.id,
                    expires_at=now + GUEST_SESSION_TTL,
                )
            )
            self._record_audit(
                database, session.id, f"participant.joined:{display_name}", row.id, now
            )
            return GuestJoinResult(
                self._participant(row), self._session(session), cookie_value
            )

    def resolve_guest_cookie(self, cookie_value: str) -> Participant | None:
        with self._transaction() as database:
            guest_session = database.get(GuestSessionRow, hash_credential(cookie_value))
            if guest_session is None:
                return None
            if _aware(guest_session.expires_at) <= utcnow():  # type: ignore[operator]
                database.delete(guest_session)
                return None
            participant = database.get(ParticipantRow, guest_session.participant_id)
            if participant is None or participant.left_at is not None:
                return None
            return self._participant(participant)

    def join_authenticated_participant(
        self, session_id: str, user_id: str
    ) -> Participant:
        with self._transaction() as database:
            session = database.get(InterviewSessionRow, session_id)
            if session is None:
                raise not_found("session_not_found", "This interview does not exist.")
            existing = database.scalar(
                self._active_participant_query(session_id, user_id)
            )
            if existing:
                return self._participant(existing)
            if session.owner_user_id != user_id:
                raise forbidden(
                    "Only an interviewer assigned to this session can join it."
                )
            user = database.get(UserRow, user_id)
            assert user is not None
            row = ParticipantRow(
                id=_id("par"),
                session_id=session_id,
                user_id=user_id,
                display_name=user.display_name,
                role="owner",
                color=PARTICIPANT_COLORS[0],
                joined_at=utcnow(),
                left_at=None,
                connection="connected",
                cursor=None,
            )
            database.add(row)
            self._record_audit(
                database, session_id, "participant.joined:owner", user_id
            )
            database.flush()
            return self._participant(row)

    def get_participant(
        self, session_id: str, participant_id: str
    ) -> Participant | None:
        with self._transaction() as database:
            row = database.get(ParticipantRow, participant_id)
            return (
                self._participant(row) if row and row.session_id == session_id else None
            )

    def active_participant_for_user(
        self, session_id: str, user_id: str
    ) -> Participant | None:
        with self._transaction() as database:
            row = database.scalar(self._active_participant_query(session_id, user_id))
            return self._participant(row) if row else None

    def user_can_access(self, session_id: str, user_id: str) -> bool:
        with self._transaction() as database:
            session = database.get(InterviewSessionRow, session_id)
            return bool(session and self._can_access(database, session, user_id))

    def user_can_manage(self, session_id: str, user_id: str) -> bool:
        with self._transaction() as database:
            session = database.get(InterviewSessionRow, session_id)
            if session is None:
                return False
            if session.owner_user_id == user_id:
                return True
            participant = database.scalar(
                self._active_participant_query(session_id, user_id)
            )
            return bool(participant and participant.role == "interviewer")

    def principal_can_access(
        self,
        session_id: str,
        *,
        user_id: str | None = None,
        participant_id: str | None = None,
    ) -> bool:
        with self._transaction() as database:
            if user_id is not None:
                session = database.get(InterviewSessionRow, session_id)
                return bool(session and self._can_access(database, session, user_id))
            if participant_id is not None:
                participant = database.get(ParticipantRow, participant_id)
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
        with self._transaction() as database:
            session = database.get(InterviewSessionRow, session_id)
            if session is None or session.state not in {"draft", "live"}:
                return False
            participant = None
            if user_id is not None:
                if session.owner_user_id == user_id:
                    return True
                participant = database.scalar(
                    self._active_participant_query(session_id, user_id)
                )
            elif participant_id is not None:
                participant = database.get(ParticipantRow, participant_id)
                if participant and (
                    participant.session_id != session_id
                    or participant.left_at is not None
                ):
                    participant = None
            if participant is None or participant.role == "observer":
                return False
            return participant.role != "candidate" or session.candidate_editing_enabled

    def leave_participant(
        self, session_id: str, participant_id: str, actor: str
    ) -> bool | None:
        with self._transaction() as database:
            participant = database.get(ParticipantRow, participant_id)
            if participant is None or participant.session_id != session_id:
                return None
            if participant.left_at is None:
                participant.left_at = utcnow()
                participant.connection = "offline"
                self._record_audit(database, session_id, "participant.left", actor)
            return True

    def update_presence(
        self, session_id: str, participant_id: str, cursor: object
    ) -> Participant | None:
        with self._transaction() as database:
            participant = database.get(ParticipantRow, participant_id)
            if (
                participant is None
                or participant.session_id != session_id
                or participant.left_at is not None
            ):
                return None
            participant.cursor = (
                cursor.model_dump() if hasattr(cursor, "model_dump") else cursor
            )  # type: ignore[union-attr,assignment]
            participant.connection = "connected"
            database.flush()
            return self._participant(participant)

    def save_canvas(
        self, session_id: str, elements: list[CanvasElement], actor: str
    ) -> datetime | None:
        with self._transaction() as database:
            canvas = database.scalar(
                select(CanvasRow).where(CanvasRow.session_id == session_id)
            )
            session = database.get(InterviewSessionRow, session_id)
            if canvas is None or session is None:
                return None
            now = utcnow()
            canvas.elements = [
                element.model_dump(mode="json", by_alias=True)
                if hasattr(element, "model_dump")
                else element
                for element in elements
            ]  # type: ignore[union-attr,misc]
            canvas.updated_at = now
            session.updated_at = now
            self._record_audit(database, session_id, "canvas.saved", actor, now)
            return now

    def list_audit(self, session_id: str) -> list[AuditEvent]:
        with self._transaction() as database:
            rows = database.scalars(
                select(AuditEventRow)
                .where(AuditEventRow.session_id == session_id)
                .order_by(AuditEventRow.at.desc())
            ).all()
            return [
                AuditEvent(
                    id=row.id,
                    session_id=row.session_id,
                    event=row.event,
                    at=_aware(row.at),
                    actor=row.actor,
                )
                for row in rows
            ]  # type: ignore[arg-type]


def get_store(connection: HTTPConnection) -> DatabaseStore:
    """Resolve the repository from the ASGI application."""

    return connection.app.state.store
