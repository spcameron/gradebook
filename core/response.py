# core/response.py

from __future__ import annotations


class Response:
    def __init__(
        self,
        success: bool,
        error: str | None = None,
        message: str | None = None,
        data: dict | None = None,
    ):
        self.success = success
        self.error = error
        self.message = message
        self.data = data or {}

    @classmethod
    def succeed(cls, message: str | None = None, data: dict | None = None) -> Response:
        return cls(True, error=None, message=message, data=data)

    @classmethod
    def fail(cls, message: str | None = None, error: str | None = None) -> Response:
        return cls(False, error=error, message=message, data=None)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "error": self.error,
            "message": self.message,
            "data": self.data,
        }

    def __str__(self) -> str:
        if self.success:
            return f"Success: {self.message or ''}"
        else:
            return f"Error: {self.error or ''}"
