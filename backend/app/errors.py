"""Stable API errors returned by every backend failure path."""

from __future__ import annotations

class ApiException(Exception):
    """An application error that maps directly to the OpenAPI ApiError shape."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers or {}


def unauthorized(message: str = "Authentication is required.") -> ApiException:
    return ApiException(
        401,
        "authentication_required",
        message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def invalid_token(message: str = "The access token is invalid or expired.") -> ApiException:
    return ApiException(
        401,
        "invalid_token",
        message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def forbidden(message: str = "You do not have access to this resource.") -> ApiException:
    return ApiException(403, "forbidden", message)


def not_found(code: str, message: str) -> ApiException:
    return ApiException(404, code, message)


def conflict(code: str, message: str) -> ApiException:
    return ApiException(409, code, message)


def gone(code: str, message: str) -> ApiException:
    return ApiException(410, code, message)
