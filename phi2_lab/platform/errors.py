"""Shared service-layer exceptions for the platform API."""
from __future__ import annotations


class PlatformError(Exception):
    """Base error with an HTTP status code for API translation."""

    status_code = 400

    def __init__(self, detail: str, *, status_code: int | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code


class UnauthorizedError(PlatformError):
    status_code = 401


class ForbiddenError(PlatformError):
    status_code = 403


class NotFoundError(PlatformError):
    status_code = 404


class ConflictError(PlatformError):
    status_code = 409
