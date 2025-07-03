# models/student.py


class Student:

    def __init__(
        self,
        id: str,
        first_name: str,
        last_name: str,
        email: str,
        status: str = "active",
    ):
        self.id = id
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.status = status

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def first_name(self) -> str:
        return self.first_name

    @first_name.setter
    def first_name(self, first_name: str) -> None:
        self.first_name = first_name

    @property
    def last_name(self) -> str:
        return self.last_name

    @last_name.setter
    def last_name(self, last_name: str) -> None:
        self.last_name = last_name

    @property
    def email(self) -> str:
        return self.email

    @email.setter
    def email(self, email: str) -> None:
        self.email = email

    def toggle_enrollment_status(self) -> None:
        self.status = "inactive" if self.status == "active" else "active"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Student":
        return cls(
            id=data["id"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data["email"],
            status=data["status"],
        )

    def __repr__(self) -> str:
        return f"Student({self.id}, {self.first_name}, {self.last_name}, {self.email})"

    def __str__(self) -> str:
        return f"STUDENT: name: {self.first_name} {self.last_name}, id: {self.id}, email: {self.email}"
