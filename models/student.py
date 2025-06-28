# student.py


class Student:

    def __init__(self, id: str, name: str, email: str, status: str = "active"):
        self.id = id
        self.name = name
        self.email = email
        self.status = status

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Student":
        return cls(
            id=data["id"],
            name=data["name"],
            email=data.get("email", ""),
            status=data["status"],
        )

    def __repr__(self) -> str:
        return f"Student({self.id}, {self.name}, {self.email})"

    def __str__(self) -> str:
        return f"STUDENT: name: {self.name}, id: {self.id}, email: {self.email}"
