# models/category.py


from typing import Optional


class Category:

    def __init__(self, id: str, name: str, weight: Optional[float] = None):
        self.id = id
        self.name = name
        self.weight = weight

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "weight": self.weight,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Category":
        return cls(
            id=data["id"],
            name=data["name"],
            weight=data["weight"],
        )

    def __repr__(self) -> str:
        return f"Category({self.id}, {self.name}, {self.weight})"

    def __str__(self) -> str:
        return f"CATEGORY: name: {self.name}, id: {self.id}, weight: {self.weight}"
