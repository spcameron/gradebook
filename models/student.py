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
