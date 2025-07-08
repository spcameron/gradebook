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
        self._id = id
        self._name = name
        self._category_id = category_id
        self._is_extra_credit = is_extra_credit
        # points_possible uses setter method for defensive validation
        self.points_possible = points_possible

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def category_id(self) -> str:
        return self._category_id

    @property
    def points_possible(self) -> float:
        return self._points_possible

    @points_possible.setter
    def points_possible(self, points: float) -> None:
        if points < 0:
            raise ValueError("Points possible cannot be less than zero.")
        self._points_possible = points

    @property
    def is_extra_credit(self) -> bool:
        return self._is_extra_credit

    def to_dict(self) -> dict:
        return {
            "id": self._id,
            "name": self._name,
            "category_id": self._category_id,
            "points_possible": self._points_possible,
            "extra_credit": self._is_extra_credit,
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
        return f"Assignment({self._id}, {self._name}, {self._category_id}, {self._points_possible}, {self._is_extra_credit})"

    def __str__(self) -> str:
        return f"ASSIGNMENT: name: {self._name}, id: {self._id}"
