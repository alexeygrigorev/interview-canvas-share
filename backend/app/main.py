"""FastAPI application entrypoint."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .errors import ApiException
from .models import ApiError
from .routers import auth, canvas, guest, me, participants, realtime, review, sessions
from .store import DatabaseStore


def _validation_message(exc: RequestValidationError) -> str:
    first = exc.errors()[0] if exc.errors() else None
    if first is None:
        return "The request body or parameters are invalid."
    location = ".".join(str(part) for part in first.get("loc", ()))
    message = str(first.get("msg", "The value is invalid.")).replace("Value error, ", "")
    return f"{location}: {message}" if location else message


def create_app(
    store: DatabaseStore | None = None,
    static_dir: str | Path | None = None,
) -> FastAPI:
    application = FastAPI(
        title="System Design Interview Platform API",
        version="1.0.0",
        description=(
            "Backend for collaborative system-design interview sessions. "
            "Guest access is established by the sdip_guest_session cookie."
        ),
    )
    application.state.store = store or DatabaseStore.seeded(url=None)

    origins = [
        origin.strip()
        for origin in os.getenv(
            "SDIP_CORS_ORIGINS",
            (
                "http://localhost:5173,http://127.0.0.1:5173,"
                "http://localhost:8081,http://127.0.0.1:8081"
            ),
        ).split(",")
        if origin.strip()
    ]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(auth.router)
    application.include_router(me.router)
    application.include_router(sessions.router)
    application.include_router(guest.router)
    application.include_router(participants.router)
    application.include_router(canvas.router)
    application.include_router(review.router)
    application.include_router(realtime.router)

    @application.get("/health", include_in_schema=False)
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.exception_handler(ApiException)
    async def handle_api_exception(_: Request, exc: ApiException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ApiError(code=exc.code, message=exc.message).model_dump(),
            headers=exc.headers,
        )

    @application.exception_handler(RequestValidationError)
    async def handle_validation_exception(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ApiError(code="validation_error", message=_validation_message(exc)).model_dump(),
        )

    @application.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "http_error"
        return JSONResponse(
            status_code=exc.status_code,
            content=ApiError(code=code, message=str(exc.detail)).model_dump(),
            headers=exc.headers or {},
        )

    def custom_openapi() -> dict[str, Any]:
        if application.openapi_schema:
            return application.openapi_schema
        schema = get_openapi(
            title=application.title,
            version=application.version,
            description=application.description,
            routes=application.routes,
        )
        schema.setdefault("components", {}).setdefault("schemas", {})["ApiError"] = {
            "type": "object",
            "required": ["code", "message"],
            "properties": {
                "code": {"type": "string", "description": "Stable machine-readable error code."},
                "message": {"type": "string", "description": "Human-readable error message."},
            },
        }
        security_schemes = schema.setdefault("components", {}).setdefault("securitySchemes", {})
        if "bearerAuth" in security_schemes:
            security_schemes["bearerAuth"].update(
                {
                    "bearerFormat": "JWT",
                    "description": "Authenticated interviewer, owner, or observer access token.",
                }
            )
        if "guestSession" in security_schemes:
            security_schemes["guestSession"]["description"] = (
                "Short-lived session credential issued after a successful guest join."
            )
        schema["security"] = [{"bearerAuth": []}]
        schema.setdefault("components", {}).setdefault("parameters", {}).update(
            {
                "SessionId": {
                    "name": "id",
                    "in": "path",
                    "required": True,
                    "description": "Interview session identifier.",
                    "schema": {"type": "string"},
                },
                "LinkId": {
                    "name": "linkId",
                    "in": "path",
                    "required": True,
                    "description": "Guest link identifier.",
                    "schema": {"type": "string"},
                },
                "GuestToken": {
                    "name": "token",
                    "in": "path",
                    "required": True,
                    "description": "Plaintext guest invitation token.",
                    "schema": {"type": "string", "minLength": 1},
                },
                "ParticipantId": {
                    "name": "pid",
                    "in": "path",
                    "required": True,
                    "description": "Participant identifier.",
                    "schema": {"type": "string"},
                },
            }
        )

        error_response = {
            "description": "An API error.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ApiError"},
                }
            },
        }
        response_codes = {
            ("/v1/me", "get"): ["401"],
            ("/v1/sessions", "get"): ["401"],
            ("/v1/sessions", "post"): ["401", "422"],
            ("/v1/sessions/{id}", "get"): ["401", "403", "404"],
            ("/v1/sessions/{id}", "patch"): ["401", "403", "404", "422"],
            ("/v1/sessions/{id}/start", "post"): ["401", "403", "404", "409"],
            ("/v1/sessions/{id}/end", "post"): ["401", "403", "404", "409"],
            ("/v1/sessions/{id}/archive", "post"): ["401", "403", "404", "409"],
            ("/v1/sessions/{id}/duplicate", "post"): ["401", "403", "404"],
            ("/v1/sessions/{id}/guest-links", "post"): ["401", "403", "404"],
            ("/v1/sessions/{id}/guest-links/{linkId}", "delete"): ["401", "403", "404"],
            ("/v1/join/{token}", "get"): ["404", "409", "410"],
            ("/v1/join/{token}", "post"): ["404", "409", "410", "422"],
            ("/v1/sessions/{id}/participants", "post"): ["401", "403", "404"],
            ("/v1/sessions/{id}/participants/{pid}", "delete"): ["401", "403", "404"],
            ("/v1/sessions/{id}/canvas", "get"): ["401", "403", "404"],
            ("/v1/sessions/{id}/canvas", "put"): ["401", "403", "404", "422"],
            ("/v1/sessions/{id}/audit", "get"): ["401", "403", "404"],
        }
        for (path, method), codes in response_codes.items():
            operation = schema.get("paths", {}).get(path, {}).get(method)
            if operation is None:
                continue
            for code in codes:
                operation.setdefault("responses", {})[code] = error_response

        for path, method in [
            ("/v1/auth/login", "post"),
            ("/v1/join/{token}", "get"),
            ("/v1/join/{token}", "post"),
        ]:
            operation = schema.get("paths", {}).get(path, {}).get(method)
            if operation is not None:
                operation["security"] = []

        schema["x-websocket"] = {
            "description": "Realtime room channel used for canvas fan-out and presence.",
            "endpoint": {
                "path": "/v1/sessions/{id}/realtime",
                "protocol": "wss",
                "security": [{"bearerAuth": []}, {"guestSession": []}],
                "pathParameters": {"id": {"$ref": "#/components/parameters/SessionId"}},
            },
            "clientMessages": [
                {"type": "document_update", "body": {"$ref": "#/components/schemas/DocumentUpdateMessage"}},
                {"type": "presence_update", "body": {"$ref": "#/components/schemas/PresenceUpdateMessage"}},
                {"type": "presence_leave", "body": {"$ref": "#/components/schemas/PresenceLeaveMessage"}},
            ],
            "serverMessages": [
                {"type": "document_update", "body": {"$ref": "#/components/schemas/DocumentUpdateMessage"}},
                {"type": "presence_update", "body": {"$ref": "#/components/schemas/PresenceUpdateMessage"}},
                {"type": "presence_leave", "body": {"$ref": "#/components/schemas/PresenceLeaveMessage"}},
                {"type": "permission_changed", "body": {"$ref": "#/components/schemas/PermissionChangedMessage"}},
                {"type": "session_ended", "body": {"$ref": "#/components/schemas/SessionEndedMessage"}},
            ],
        }
        application.openapi_schema = schema
        return schema

    application.openapi = custom_openapi  # type: ignore[method-assign]

    frontend_dir = Path(
        static_dir or os.getenv("SDIP_STATIC_DIR", Path(__file__).parent / "static")
    ).resolve()
    frontend_index = frontend_dir / "index.html"
    if frontend_index.is_file():

        @application.get("/{path:path}", include_in_schema=False)
        async def serve_frontend(path: str) -> FileResponse:
            # API typos must retain the API's JSON 404 response rather than
            # falling through to the SPA shell.
            if path == "v1" or path.startswith("v1/"):
                raise HTTPException(status_code=404, detail="Not Found")

            requested_file = (frontend_dir / path).resolve()
            if requested_file.is_relative_to(frontend_dir) and requested_file.is_file():
                return FileResponse(requested_file)
            return FileResponse(frontend_index)

    return application


app = create_app()
