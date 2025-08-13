# core/response.py

from __future__ import annotations

from enum import Enum


class ErrorCode(Enum):
    # === Not Found ===
    NOT_FOUND = "NOT_FOUND"

    # STUDENT_NOT_FOUND, ASSIGNMENT_NOT FOUND, etc.

    # === Constraint Violations ===

    # DUPLICATE_NAME, DUPLICATE_EMAIL, etc.

    # === Validation Failures ===
    # required argument or attribute is missing
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"

    # input structure is malformed or incomplete
    INVALID_INPUT = "INVALID_INPUT"

    # field value is out of bounds or incorrectly formatted
    INVALID_FIELD_VALUE = "INVALID_FIELD_VALUE"

    # the value is valid in isolation, but violates system rules
    VALIDATION_FAILED = "VALIDATION_FAILED"

    # INVALID_DATE_FORMAT
    # INVALID_SCORE_VALUE
    # MISSING_IDENTIFIER

    # === State Restrictions ===

    # ARCHIVED_RECORD
    # SUBMISSION_EXEMPT
    # ASSIGNMENT_UNGRADED

    # === Internal Faults ===
    INTERNAL_ERROR = "INTERNAL_ERROR"
    LOGIC_ERROR = "LOGIC_ERROR"


class Response:
    """
    Standard Response object for Gradebook manipulator and lookup methods.

    Attributes:
        success (bool): Indicates whether the operation succeeded.
        detail (str | None): Optional human-readable explanation.
        error (ErrorCode | str | None): Optional machine-readable error identifier.
        status_code (int | None): Optional HTTP response code.
        data (dict): Optional payload, varies by operation.
        trace (str | None): Optional exception traceback when errors occur.
    """

    def __init__(
        self,
        success: bool,
        detail: str | None = None,
        error: ErrorCode | str | None = None,
        status_code: int | None = None,
        data: dict | None = None,
        trace: str | None = None,
    ):
        self._success = success
        self._detail = detail
        self._error = error
        self._status_code = status_code
        self._data = data or {}
        self._trace = trace

    # === properties ===

    @property
    def success(self) -> bool:
        return self._success

    @property
    def detail(self) -> str | None:
        return self._detail

    @property
    def error(self) -> ErrorCode | str | None:
        return self._error

    @property
    def status_code(self) -> int | None:
        return self._status_code

    @property
    def data(self) -> dict:
        return self._data or {}

    @property
    def trace(self) -> str | None:
        return self._trace

    # === public classmethods ===

    @classmethod
    def succeed(
        cls,
        detail: str | None = None,
        status_code: int | None = 200,
        data: dict | None = None,
    ) -> Response:
        return cls(
            success=True,
            detail=detail,
            error=None,
            status_code=status_code,
            data=data,
        )

    @classmethod
    def fail(
        cls,
        detail: str | None = None,
        error: ErrorCode | str | None = None,
        status_code: int | None = 400,
        data: dict | None = None,
    ) -> Response:
        return cls(
            success=False,
            detail=detail,
            error=error,
            status_code=status_code,
            data=data,
        )

    # === persistence and import ===

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "error": self.error.value if isinstance(self.error, Enum) else self.error,
            "detail": self.detail,
            "data": self.data,
            "status_code": self.status_code,
            "trace": self.trace,
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
            trace=payload.get("trace"),
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
