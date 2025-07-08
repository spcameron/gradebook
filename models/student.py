# models/student.py


class Student:

    def __init__(
        self,
        id: str,
        first_name: str,
        last_name: str,
        email: str,
        enrolled: bool = True,
    ):
        self._id = id
        self._first_name = first_name
        self._last_name = last_name
        self._email = email
        self._is_enrolled = enrolled

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
        self._email = email

    @property
    def is_enrolled(self) -> bool:
        return self._is_enrolled

    @property
    def status(self) -> str:
        if self._is_enrolled:
            return "'ACTIVE'"
        else:
            return "'INACTIVE'"

    def toggle_enrollment_status(self) -> None:
        self._is_enrolled = False if self._is_enrolled else True

    def to_dict(self) -> dict:
        return {
            "id": self._id,
            "first_name": self._first_name,
            "last_name": self._last_name,
            "email": self._email,
            "enrolled": self._is_enrolled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Student":
        return cls(
            id=data["id"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data["email"],
            enrolled=data["enrolled"],
        )

    def __repr__(self) -> str:
        return f"Student({self._id}, {self._first_name}, {self._last_name}, {self._email}, {self._is_enrolled})"

    def __str__(self) -> str:
        return f"STUDENT: name: {self.full_name}, email: {self._email}, id: {self._id}"
