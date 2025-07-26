# core/response.py

from __future__ import annotations

from enum import Enum


class ErrorCode(Enum):
    NOT_FOUND = "not_found"
    # add new error codes as needed during refactor


class Response:
    """
    Standard Response object for Gradebook manipulator and lookup methods.

    Attributes:
        success (bool): Indicates whether the operation succeeded.
        error (ErrorCode | str | None): Optional machine-readable error identifier.
        detail (str | None): Optional human-readable explanation.
        data (dict): Optional payload, varies by operation.
        status_code (int | None): Optional HTTP response code.
    """

    def __init__(
        self,
        success: bool,
        error: ErrorCode | str | None = None,
        detail: str | None = None,
        data: dict | None = None,
        status_code: int | None = None,
    ):
        self.success = success
        self.error = error
        self.detail = detail
        self.data = data or {}
        self.status_code = status_code

    # === public classmethods ===

    @classmethod
    def succeed(
        cls,
        detail: str | None = None,
        data: dict | None = None,
        status_code: int | None = 200,
    ) -> Response:
        return cls(
            success=True,
            error=None,
            detail=detail,
            data=data,
            status_code=status_code,
        )

    @classmethod
    def fail(
        cls,
        detail: str | None = None,
        error: ErrorCode | str | None = None,
        status_code: int | None = 400,
    ) -> Response:
        return cls(
            success=False,
            error=error,
            detail=detail,
            data=None,
            status_code=status_code,
        )

    # === persistence and import ===

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "error": self.error.value if isinstance(self.error, Enum) else self.error,
            "detail": self.detail,
            "data": self.data,
            "status_code": self.status_code,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> Response:
        error = payload.get("error")
        if error in ErrorCode._value2member_map_:
            error = ErrorCode(error)

        return cls(
            success=payload["success"],
            error=error,
            detail=payload.get("detail"),
            data=payload.get("data", {}),
            status_code=payload.get("status_code"),
        )

    # === dunder methods ===

    def __str__(self) -> str:
        if self.success:
            return f"Success: {self.detail or ''}"
        else:
            error_str = (
                self.error.value if isinstance(self.error, Enum) else self.error or ""
            )
            return f"Error: {error_str}"
