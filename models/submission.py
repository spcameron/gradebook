# models/submission.py

"""
Represents a student's submission for a specific assignment.

Each `Submission` records the student's ID, the assignment ID, the number of points earned,
and optional flags for lateness and exemption. These flags influence grading and reporting
but do not directly alter the stored score.

Includes functionality for:
- Validating and updating `points_earned`
- Toggling `is_late` and `is_exempt` status flags
- Serializing to and from JSON-compatible dictionaries

Notes:
- Validation is enforced via the `points_earned` setter and `validate_points_input()`.
- A submission may be marked both late and exempt simultaneously.
- Actual grade calculations are handled externally by the Gradebook.
"""

from __future__ import annotations

import math
from typing import Any


class Submission:

    def __init__(
        self,
        id: str,
        student_id: str,
        assignment_id: str,
        points_earned: float,
        is_late: bool = False,
        is_exempt: bool = False,
    ):
        self.id = id
        self._student_id = student_id
        self._assignment_id = assignment_id
        self._points_earned = points_earned
        self._is_late = is_late
        self._is_exempt = is_exempt
        # self.resolved_refs = False

    # === properties ===

    @property
    def student_id(self) -> str:
        return self._student_id

    @property
    def assignment_id(self) -> str:
        return self._assignment_id

    @property
    def points_earned(self) -> float:
        return self._points_earned

    @points_earned.setter
    def points_earned(self, points_earned: float) -> None:
        self._points_earned = Submission.validate_points_input(points_earned)

    @property
    def is_late(self) -> bool:
        return self._is_late

    @property
    def late_status(self) -> str:
        return "'LATE'" if self._is_late else "'NOT LATE'"

    def toggle_late_status(self) -> None:
        self._is_late = not self._is_late

    @property
    def is_exempt(self) -> bool:
        return self._is_exempt

    @property
    def exempt_status(self) -> str:
        return "'EXEMPT'" if self._is_exempt else "'NOT EXEMPT'"

    def toggle_exempt_status(self) -> None:
        self._is_exempt = not self._is_exempt

    # === persistence and import ===

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "student_id": self._student_id,
            "assignment_id": self._assignment_id,
            "points_earned": self._points_earned,
            "is_late": self._is_late,
            "is_exempt": self._is_exempt,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Submission:
        return cls(
            id=data["id"],
            student_id=data["student_id"],
            assignment_id=data["assignment_id"],
            points_earned=data["points_earned"],
            is_late=data["is_late"],
            is_exempt=data["is_exempt"],
        )

    # === dunder methods ===

    def __repr__(self) -> str:
        return f"Submission({self.id}, {self._student_id}, {self._assignment_id}, {self._points_earned}, {self._is_late}, {self._is_exempt})"

    def __str__(self) -> str:
        return f"SUBMISSION: id: {self.id}, student id: {self._student_id}, assignment id: {self._assignment_id}"

    # === data validators ===

    @staticmethod
    def validate_points_input(points: Any) -> float:
        """
        Validates and normalizes input for a `Submission` points_earned value.

        Accepts any input, and then:
            - Casts to float.
            - Ensures the number is finite.
            - Ensures it is non-negative.

        Args:
            points (Any): The input value to validate.

        Returns:
            The normalized points value (float).

        Raises:
            TypeError: If the input cannot be case to float.
            ValueError: If the input is non-finite or less than zero.
        """
        try:
            points = float(points)

        except (TypeError, ValueError):
            raise TypeError("Invalid input. Points earned must be a number.") from None

        if not math.isfinite(points):
            raise ValueError("Invalid input. Points earned must be a finite number.")

        if points < 0:
            raise ValueError("Invalid input. Points earned cannot be less than zero.")

        return points
