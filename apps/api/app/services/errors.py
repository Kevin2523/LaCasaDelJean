"""Domain exceptions mapped to the Fase 1 error envelope."""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base domain error with machine-readable code and HTTP status."""

    code: str = "DOMAIN_ERROR"
    status_code: int = 400

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class DomainValidationError(DomainError):
    """Raised when business or input invariants are violated."""

    code = "VALIDATION_ERROR"
    status_code = 422


class ResourceNotFoundError(DomainError):
    """Raised when a requested resource does not exist or is not visible."""

    code = "RESOURCE_NOT_FOUND"
    status_code = 404


class ConflictError(DomainError):
    """Raised on uniqueness or state conflicts."""

    code = "CONFLICT"
    status_code = 409


class UnauthorizedError(DomainError):
    """Raised when authentication is missing or invalid."""

    code = "UNAUTHORIZED"
    status_code = 401


class ForbiddenError(DomainError):
    """Raised when the authenticated actor lacks required permissions."""

    code = "FORBIDDEN"
    status_code = 403
