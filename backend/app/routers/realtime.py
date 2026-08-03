"""WebSocket fan-out for canvas and participant presence messages."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import TypeAdapter, ValidationError

from ..auth import authenticate_websocket
from ..errors import ApiException
from ..models import (
    DocumentUpdateMessage,
    PermissionChangedMessage,
    PresenceLeaveMessage,
    PresenceUpdateMessage,
    RoomMessage,
    SessionEndedMessage,
)
from ..store import DatabaseStore, get_store

router = APIRouter(tags=["Realtime"])
room_message_adapter = TypeAdapter(RoomMessage)


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, session_id: str, websocket: WebSocket, subprotocol: str | None = None) -> None:
        await websocket.accept(subprotocol=subprotocol)
        self.connections[session_id].add(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        connections = self.connections.get(session_id)
        if connections is None:
            return
        connections.discard(websocket)
        if not connections:
            self.connections.pop(session_id, None)

    async def broadcast(self, session_id: str, message: dict[str, object]) -> None:
        stale: list[WebSocket] = []
        for websocket in list(self.connections.get(session_id, ())):
            try:
                await websocket.send_json(message)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(session_id, websocket)


manager = ConnectionManager()


async def broadcast_message(session_id: str, message: object) -> None:
    """Publish a validated server message to every connected room client."""

    await manager.broadcast(
        session_id,
        message.model_dump(mode="json", by_alias=True),  # type: ignore[union-attr]
    )


def _websocket_error_code(error: ApiException) -> int:
    return {
        401: 4401,
        403: 4403,
        404: 4404,
    }.get(error.status_code, 4400)


async def _send_validation_error(websocket: WebSocket, message: str) -> None:
    await websocket.send_json({"code": "validation_error", "message": message})


@router.websocket("/v1/sessions/{id}/realtime")
async def realtime(id: str, websocket: WebSocket, store: DatabaseStore = Depends(get_store)) -> None:
    try:
        protocols = [
            protocol.strip()
            for protocol in websocket.headers.get("sec-websocket-protocol", "").split(",")
            if protocol.strip()
        ]
        authorization = websocket.headers.get("authorization")
        if authorization is None:
            bearer_protocol = next(
                (protocol for protocol in protocols if protocol.startswith("bearer.")),
                None,
            )
            if bearer_protocol is not None:
                authorization = f"Bearer {bearer_protocol.removeprefix('bearer.')}"
        principal = authenticate_websocket(
            authorization,
            websocket.cookies.get("sdip_guest_session"),
            store,
        )
        session = store.get_session(id)
        if session is None:
            raise ApiException(404, "session_not_found", "This interview does not exist.")
        if not store.principal_can_access(
            id,
            user_id=principal.user_id,
            participant_id=principal.participant_id,
        ):
            raise ApiException(403, "forbidden", "You are not a participant in this interview.")
    except ApiException as error:
        await websocket.close(code=_websocket_error_code(error), reason=error.message)
        return

    await manager.connect(id, websocket, "sdip" if "sdip" in protocols else None)
    try:
        while True:
            payload = await websocket.receive_json()
            try:
                message = room_message_adapter.validate_python(payload)
            except ValidationError:
                await _send_validation_error(websocket, "The realtime message is invalid.")
                continue

            if message.sessionId != id:
                await _send_validation_error(websocket, "The message sessionId does not match the room.")
                continue
            if isinstance(message, (PermissionChangedMessage, SessionEndedMessage)):
                await _send_validation_error(websocket, "This message type is server-generated.")
                continue

            if isinstance(message, DocumentUpdateMessage):
                if not store.principal_can_edit(
                    id,
                    user_id=principal.user_id,
                    participant_id=principal.participant_id,
                ):
                    await _send_validation_error(websocket, "You cannot edit this canvas.")
                    continue
                if store.save_canvas(id, message.elements, message.actor) is None:
                    await _send_validation_error(websocket, "Canvas unavailable.")
                    continue
            elif isinstance(message, PresenceUpdateMessage):
                can_update = message.participant.id == principal.participant_id
                if principal.user_id is not None:
                    can_update = message.participant.user_id == principal.user_id
                if not can_update:
                    await _send_validation_error(websocket, "You can only update your own presence.")
                    continue
                updated = store.update_presence(id, message.participant.id, message.cursor)
                if updated is None:
                    await _send_validation_error(websocket, "Participant unavailable.")
                    continue
                message = message.model_copy(update={"participant": updated})
            elif isinstance(message, PresenceLeaveMessage):
                can_leave = message.participantId == principal.participant_id
                if principal.user_id is not None:
                    participant = store.get_participant(id, message.participantId)
                    can_leave = bool(participant and participant.user_id == principal.user_id)
                if not can_leave:
                    await _send_validation_error(websocket, "You can only leave as yourself.")
                    continue
                if store.leave_participant(id, message.participantId, principal.user_id or message.participantId) is None:
                    await _send_validation_error(websocket, "Participant unavailable.")
                    continue

            await manager.broadcast(id, message.model_dump(mode="json", by_alias=True))
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(id, websocket)
