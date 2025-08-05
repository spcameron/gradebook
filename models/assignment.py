# models/assignment.py

"""
The Assignment model represents classroom assignments, assessments, or any other graded component.
"""

from __future__ import annotations

import datetime
import math
from typing import Any


class Assignment:

    def __init__(
        self,
        id: str,
        name: str,
        category_id: str | None,
        points_possible: float,
        due_date: datetime.datetime | None,
        is_extra_credit: bool = False,
        active: bool = True,
    ):
        self._id = id
        self._name = name
        self._category_id = category_id
        # points_possible uses setter method for defensive validation
        self.points_possible = points_possible
        self._due_date_dt = due_date
        self._is_extra_credit = is_extra_credit
        self._is_active = active

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        self._name = name

    @property
    def category_id(self) -> str | None:
        return self._category_id

    @category_id.setter
    def category_id(self, category_id: str | None) -> None:
        self._category_id = category_id

    @property
    def points_possible(self) -> float:
        return self._points_possible

    @points_possible.setter
    def points_possible(self, points: float) -> None:
        self._points_possible = Assignment.validate_points_input(points)

    @property
    def due_date_dt(self) -> datetime.datetime | None:
        return self._due_date_dt

    @due_date_dt.setter
    def due_date_dt(self, due_date_dt: datetime.datetime | None) -> None:
        self._due_date_dt = due_date_dt

    @property
    def due_date_iso(self) -> str | None:
        return self._due_date_dt.isoformat() if self._due_date_dt else None

    @property
    def due_date_str(self) -> str | None:
        return self._due_date_dt.strftime("%Y-%m-%d") if self._due_date_dt else None

    @property
    def due_time_str(self) -> str | None:
        return self._due_date_dt.strftime("%H:%M") if self._due_date_dt else None

    @property
    def is_extra_credit(self) -> bool:
        return self._is_extra_credit

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def status(self) -> str:
        return "'ACTIVE'" if self._is_active else "'INACTIVE'"

    def toggle_archived_status(self) -> None:
        self._is_active = not self._is_active

    def to_dict(self) -> dict:
        return {
            "id": self._id,
            "name": self._name,
            "category_id": self._category_id,
            "points_possible": self._points_possible,
            "due_date": self.due_date_iso,
            "extra_credit": self._is_extra_credit,
            "active": self._is_active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Assignment":
        due_date_str = data.get("due_date")
        due_date = (
            datetime.datetime.fromisoformat(due_date_str) if due_date_str else None
        )

        return cls(
            id=data["id"],
            name=data["name"],
            category_id=data["category_id"],
            points_possible=data["points_possible"],
            due_date=due_date,
            is_extra_credit=data["extra_credit"],
            active=data["active"],
        )

    # TODO: update with due_date_dt and is_active
    def __repr__(self) -> str:
        return f"Assignment({self._id}, {self._name}, {self._category_id}, {self._points_possible}, {self._is_extra_credit})"

    def __str__(self) -> str:
        return f"ASSIGNMENT: name: {self._name}, id: {self._id}"

    # === data validators ===

    @staticmethod
    def validate_points_input(points: Any) -> float:
        """
        Validates and normalizes input for an `Assignment` points_possible value.

        Accepts any input, and then:
            - Casts to float.
            - Ensures the number is finite.
            - Ensures it is non-negative.

        Args:
            points (Any): The input value to validate.

        Returns:
            The normalized points value (float).

        Raises:
            TypeError: If the input cannot be cast to float.
            ValueError: If the input is non-finite or less than zero.
        """
        try:
            points = float(points)

        except (TypeError, ValueError):
            raise TypeError("Invalid input. Points possible must be a number.")

        if not math.isfinite(points):
            raise ValueError("Invalid input. Points possible must be a finite number.")

        if points < 0:
            raise ValueError("Invalid input. Points possible cannot be less than zero.")

        return points

    @staticmethod
    def validate_due_date_input(
        due_date: str | None, due_time: str | None
    ) -> datetime.datetime | None:
        """
        Validates and normalizes input for an `Assignment` due date.

        Accepts strings or None as input, and then:
            - Calls `datetime.strptime` to create a datetime.datetime object if both arguments are not None
            - Otherwise returns None

        Raises:
            TypeError: If `strptime()` cannot create a datetime.datetime object from the input

        Notes:
            - Strictly uses YYYY-MM-DD and 24-hour HH:MM formatting for input
        """
        try:
            due_date_dt = (
                datetime.datetime.strptime(f"{due_date} {due_time}", "%Y-%m-%d %H:%M")
                if due_date and due_time
                else None
            )

        except (ValueError, TypeError):
            raise TypeError(
                "Invalid input. The date must be formatted as YYYY-MM-DD and the time as 24-hour HH:MM."
            )

        return due_date_dt
