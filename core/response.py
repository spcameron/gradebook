# core/response.py

from __future__ import annotations

from enum import Enum

"""
TEMPLATE FOR DOCSTRINGS THAT RETURN A RESPONSE

<One-sentence summary of what this method does.>

Args:
    <param1> (<type>): <description>.
    <param2> (<type>): <description>.
    ...

Returns:
    Response: A structured response with the following contract:
        - success (bool): True if the operation was successful.
        - detail (str | None): Description of the result for display or logging.
        - error (ErrorCode | str | None): A machine-readable error code, if any.
        - status_code (int | None): HTTP-style status code (e.g., 200, 404). Optional in CLI.
        - data (dict | None): Payload with the following keys:
            - "<key1>" (<type>): <description of value>.
            - "<key2>" (<type>): <description of value>.
            ...

Notes:
    - <State if method is read-only or mutates gradebook state>.
    - <Mention any expected preconditions or invariants>.
    - <What does success/failure look like, if not clear from above?>
    - <What assumptions must the caller uphold?>
    - <Does this touch or cascade to other objects?>
"""


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
