# models/student.py

"""
The Student model represents the individual students enrolled in a class.

Includes a method for validating email addresses.
"""

import re


class Student:

    def __init__(
        self,
        id: str,
        first_name: str,
        last_name: str,
        email: str,
        active: bool = True,
    ):
        self._id = id
        self._first_name = first_name
        self._last_name = last_name
        self._email = email
        self._is_active = active

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
        self._is_active = False if self._is_active else True

    def to_dict(self) -> dict:
        return {
            "id": self._id,
            "first_name": self._first_name,
            "last_name": self._last_name,
            "email": self._email,
            "active": self._is_active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Student":
        return cls(
            id=data["id"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data["email"],
            active=data["active"],
        )

    def __repr__(self) -> str:
        return f"Student({self._id}, {self._first_name}, {self._last_name}, {self._email}, {self._is_active})"

    def __str__(self) -> str:
        return f"STUDENT: name: {self.full_name}, email: {self._email}, id: {self._id}"

    # === data validators ===

    @staticmethod
    def validate_email_input(email: str) -> str:
        """
        Validates and normalizes a Student email address.

        Normalizes the input by stripping whitespace and converting to lowercase.
        Ensures the email:
            - Contains exactly one '@' symbol
            - Has non-whitespace characters on both sides of the '@'
            - Contains at least one '.' after the '@' to spearate the domain and TLD

        Args:
            email: The input email string to validate.

        Returns:
            A normalized, lowercase version of the email if valid.

        Raises:
            ValueError: If the email does not confrom to the expected format.
        """
        email = email.strip().lower()
        if not re.fullmatch(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            raise ValueError("Email must be a valid address with one @ and a domain.")
        return email

    # === data manipulators ===
