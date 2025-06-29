# models/assignment.py


class Assignment:

    def __init__(
        self,
        id: str,
        name: str,
        category_id: str,
        points_possible: float,
        is_extra_credit: bool = False,
    ):
        self.id = id
        self.name = name
        self.category_id = category_id
        self.points_possible = points_possible
        self.is_extra_credit = is_extra_credit

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "category_id": self.category_id,
            "points_possible": self.points_possible,
            "extra_credit": self.is_extra_credit,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Assignment":
        return cls(
            id=data["id"],
            name=data["name"],
            category_id=data["category_id"],
            points_possible=data["points_possible"],
            is_extra_credit=data["extra_credit"],
        )

    def __repr__(self) -> str:
        return f"Assignment({self.id}, {self.name}, {self.category_id}, {self.points_possible}, {self.is_extra_credit})"

    def __str__(self) -> str:
        return f"ASSIGNMENT: name: {self.name}, id: {self.id}"
