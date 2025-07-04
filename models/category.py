# models/category.py


from typing import Optional


class Category:

    def __init__(self, id: str, name: str, weight: Optional[float] = None):
        self._id = id
        self._name = name
        self._weight = weight

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def weight(self) -> float | None:
        return self._weight

    def to_dict(self) -> dict:
        return {
            "id": self._id,
            "name": self._name,
            "weight": self._weight,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Category":
        return cls(
            id=data["id"],
            name=data["name"],
            weight=data["weight"],
        )

    def __repr__(self) -> str:
        return f"Category({self._id}, {self._name}, {self._weight})"

    def __str__(self) -> str:
        return f"CATEGORY: name: {self._name}, weight: {self._weight}, id: {self._id}"
