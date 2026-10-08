# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
class AtonixError(Exception):
    """Base exception for all Atonix library errors."""

    pass


class AuthenticationError(AtonixError):
    """Raised when authentication fails or the API key is invalid (401)."""

    pass


class PermissionDeniedError(AtonixError):
    """Raised when the user does not have permission to access a resource (403)."""

    pass


class NotFoundError(AtonixError):
    """Raised when a requested resource (Asset, Tag, etc.) is not found (404)."""

    pass


class RateLimitError(AtonixError):
    """Raised when the API rate limit is exceeded (429) after all retry attempts."""

    pass


class ServerError(AtonixError):
    """Raised when the Atonix server returns an internal error (5xx)."""

    pass


class APIError(AtonixError):
    """
    Raised for other non-success API responses or network-related issues.

    Attributes:
        status_code: The HTTP status code returned by the API.
        response_content: The raw response body from the server.
    """

    def __init__(self, message: str, status_code: int | None = None, response_content: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_content = response_content

    def __str__(self):
        if self.status_code:
            return f"{super().__str__()} (Status: {self.status_code})"
        return super().__str__()
