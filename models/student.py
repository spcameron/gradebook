# models/student.py

"""
Represents a student enrolled in a course.

Stores core identifying information such as name, email, and a unique ID.
Supports toggling between active and inactive status to reflect enrollment changes.

Includes functionality for:
- Validating and normalizing email input
- Tracking attendance by date
- Serializing to and from JSON-compatible dictionaries
- Mutating individual fields via property access

Attendance is internally represented as a dictionary mapping `datetime.date` objects
to status values (e.g., Present, Absent, Excused). This allows for explicit representation
of attendance states and detection of unmarked records.
"""

from __future__ import annotations

import datetime
import re
from enum import Enum


class AttendanceStatus(str, Enum):
    PRESENT = "Present"
    ABSENT = "Absent"
    EXCUSED_ABSENCE = "Excused"
    LATE = "Late"
    UNMARKED = "Unmarked"


class Student:

    def __init__(
        self,
        id: str,
        first_name: str,
        last_name: str,
        email: str,
        active: bool = True,
    ):
        self._id: str = id
        self._first_name: str = first_name
        self._last_name: str = last_name
        self._email: str = email
        self._is_active: bool = active
        self._attendance: dict[datetime.date, AttendanceStatus] = {}

    # === properties ===

    @property
    def id(self) -> str:
        return self._id

    @property
    def first_name(self) -> str:
        return self._first_name

    @first_name.setter
    def first_name(self, first_name: str) -> None:
        self._first_name = first_name

    @property
    def last_name(self) -> str:
        return self._last_name

    @last_name.setter
    def last_name(self, last_name: str) -> None:
        self._last_name = last_name

    @property
    def full_name(self) -> str:
        return f"{self._first_name} {self._last_name}"

    @property
    def email(self) -> str:
        return self._email

    @email.setter
    def email(self, email: str) -> None:
        self._email = Student.validate_email_input(email)

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def status(self) -> str:
        return "'ACTIVE'" if self._is_active else "'INACTIVE'"

    def toggle_archived_status(self) -> None:
        self._is_active = not self._is_active

    # === persistence and import ===

    def to_dict(self) -> dict:
        return {
            "id": self._id,
            "first_name": self._first_name,
            "last_name": self._last_name,
            "email": self._email,
            "active": self._is_active,
            "attendance": {
                date.isoformat(): status.value
                for date, status in self._attendance.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> Student:
        student = cls(
            id=data["id"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data["email"],
            active=data["active"],
        )

        attendance_raw = data.get("attendance", {})
        student._attendance = {
            datetime.date.fromisoformat(date_str): AttendanceStatus(status_str)
            for date_str, status_str in attendance_raw.items()
        }

        return student

    # === dunder methods ===

    def __repr__(self) -> str:
        return f"Student({self._id}, {self._first_name}, {self._last_name}, {self._email}, {self._is_active})"

    def __str__(self) -> str:
        return f"STUDENT: name: {self.full_name}, email: {self._email}, id: {self._id}"

    # === data accessors ===

    # --- attendance methods ---

    @property
    def attendance_records(self) -> dict[datetime.date, AttendanceStatus]:
        return self._attendance.copy()

    def attendance_on(self, date: datetime.date) -> AttendanceStatus:
        return self._attendance.get(date, AttendanceStatus.UNMARKED)

    def was_present_on(self, date: datetime.date) -> bool:
        return self.attendance_on(date) == AttendanceStatus.PRESENT

    def was_absent_on(self, date: datetime.date) -> bool:
        return self.attendance_on(date) == AttendanceStatus.ABSENT

    def is_attendance_marked(self, date: datetime.date) -> bool:
        return date in self._attendance

    # === data manipulators ===

    # --- attendance methods ---

    def mark_attendance(
        self, date: datetime.date, attendance_status: AttendanceStatus
    ) -> None:
        self._attendance[date] = attendance_status

    # def mark_present(self, date: datetime.date) -> None:
    #     self._attendance[date] = AttendanceStatus.PRESENT
    #
    # def mark_absent(self, date: datetime.date) -> None:
    #     self._attendance[date] = AttendanceStatus.ABSENT
    #
    # def mark_excused(self, date: datetime.date) -> None:
    #     self._attendance[date] = AttendanceStatus.EXCUSED_ABSENCE
    #
    # def mark_late(self, date: datetime.date) -> None:
    #     self._attendance[date] = AttendanceStatus.LATE

    def clear_attendance(self, date: datetime.date) -> None:
        self._attendance.pop(date, None)

    # === data validators ===

    @staticmethod
    def validate_email_input(email: str) -> str:
        """
        Validates and normalizes a Student email address.

        Normalizes the input by stripping whitespace and converting to lowercase.
        Ensures the email:
            - Contains exactly one '@' symbol
            - Has non-whitespace characters on both sides of the '@'
            - Contains at least one '.' after the '@' to separate the domain and TLD

        Args:
            email: The input email string to validate.

        Returns:
            A normalized, lowercase version of the email if valid.

        Raises:
            ValueError: If the email does not conform to the expected format.
        """
        email = email.strip().lower()
        if not re.fullmatch(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            raise ValueError(
                "Invalid input. Email must be a valid address with one @ and a domain."
            )
        return email
