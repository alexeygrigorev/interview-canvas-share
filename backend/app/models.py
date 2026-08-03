"""Pydantic models for the HTTP and realtime API contract."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class APIModel(BaseModel):
    """Base model with the contract's strict request-object behavior."""

    model_config = ConfigDict(extra="forbid")


class ApiError(APIModel):
    code: str
    message: str


TrueResponse = Literal[True]


class User(BaseModel):
    id: str
    email: EmailStr
    display_name: str
    organization_id: str | None
    created_at: datetime


SessionState = Literal["draft", "live", "ended", "archived"]
Role = Literal["owner", "interviewer", "candidate", "observer"]
GuestRole = Literal["interviewer", "candidate", "observer"]


class InterviewSession(BaseModel):
    id: str
    owner_user_id: str
    title: str
    prompt: str
    state: SessionState
    candidate_editing_enabled: bool
    cursors_visible: bool
    duration_minutes: int = Field(ge=1)
    scheduled_at: datetime | None
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime
    updated_at: datetime


class GuestLink(BaseModel):
    id: str
    session_id: str
    token: str
    role_granted: GuestRole
    expires_at: datetime | None
    max_uses: int | None = Field(default=None, ge=1)
    revoked_at: datetime | None
    created_at: datetime


class Cursor(APIModel):
    x: float
    y: float


class Participant(APIModel):
    id: str
    session_id: str
    user_id: str | None
    display_name: str
    role: Role
    color: str
    joined_at: datetime
    left_at: datetime | None
    connection: Literal["connected", "reconnecting", "offline"]
    cursor: Cursor | None = None


class CanvasDocument(BaseModel):
    id: str
    session_id: str
    schema_version: int
    elements: list["CanvasElement"]
    updated_at: datetime


ElementKind = Literal["node", "connector", "stroke", "text", "note"]


class BaseElement(APIModel):
    id: str
    kind: ElementKind
    created_by: str
    created_at: datetime
    updated_at: datetime


class NodeElement(BaseElement):
    kind: Literal["node", "text", "note"]
    componentType: str
    x: float
    y: float
    width: float
    height: float
    label: str
    description: str | None = None
    color: str | None = None


class ConnectorElement(BaseElement):
    kind: Literal["connector"]
    from_: str = Field(alias="from")
    to: str
    style: Literal["straight", "elbow", "curved"]
    dashed: bool
    arrowStart: bool
    arrowEnd: bool
    width: float
    label: str

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class StrokeElement(BaseElement):
    kind: Literal["stroke"]
    points: list[float]
    color: str
    width: float
    opacity: float


CanvasElement = Annotated[
    Union[NodeElement, ConnectorElement, StrokeElement],
    Field(discriminator="kind"),
]


class SessionRelations(BaseModel):
    participants: list[Participant]
    link: GuestLink | None


class SessionListItem(InterviewSession):
    participants: list[Participant]
    link: GuestLink | None


class SessionDetail(APIModel):
    session: InterviewSession
    participants: list[Participant]
    link: GuestLink | None


class CreateSessionRequest(APIModel):
    title: str
    prompt: str
    duration_minutes: int = Field(ge=1)
    scheduled_at: datetime | None


class UpdateSessionRequest(APIModel):
    title: str | None = None
    prompt: str | None = None
    candidate_editing_enabled: bool | None = None
    cursors_visible: bool | None = None
    duration_minutes: int | None = Field(default=None, ge=1)
    scheduled_at: datetime | None = None

    @model_validator(mode="after")
    def require_a_change(self) -> "UpdateSessionRequest":
        if not self.model_fields_set:
            raise ValueError("At least one session field must be provided.")
        return self


class CreateGuestLinkRequest(APIModel):
    role_granted: GuestRole = "candidate"


class JoinRequest(APIModel):
    display_name: str = Field(min_length=1)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Display name must not be blank.")
        return value


class TokenInspection(BaseModel):
    session: InterviewSession
    link: GuestLink
    activeCount: int = Field(ge=0)


class JoinResponse(BaseModel):
    participant: Participant
    session: InterviewSession


class SaveCanvasRequest(APIModel):
    elements: list[CanvasElement]
    actor: str


class AuditEvent(BaseModel):
    id: str
    session_id: str
    event: str
    at: datetime
    actor: str


class DocumentUpdateMessage(APIModel):
    type: Literal["document_update"]
    sessionId: str
    elements: list[CanvasElement]
    actor: str


class PresenceUpdateMessage(APIModel):
    type: Literal["presence_update"]
    sessionId: str
    participant: Participant
    cursor: Cursor | None = None


class PresenceLeaveMessage(APIModel):
    type: Literal["presence_leave"]
    sessionId: str
    participantId: str


class PermissionChangedMessage(APIModel):
    type: Literal["permission_changed"]
    sessionId: str
    session: InterviewSession


class SessionEndedMessage(APIModel):
    type: Literal["session_ended"]
    sessionId: str


RoomMessage = Annotated[
    Union[
        DocumentUpdateMessage,
        PresenceUpdateMessage,
        PresenceLeaveMessage,
        PermissionChangedMessage,
        SessionEndedMessage,
    ],
    Field(discriminator="type"),
]


class LoginRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"]
    user: User


CanvasDocument.model_rebuild()
