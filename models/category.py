# models/category.py

"""
The Category model represents a grouping of related Assignments, and may optionally be assigned a weighted percentage of the final grade.
"""

import math
from typing import Any, Optional


class Category:

    def __init__(
        self,
        id: str,
        name: str,
        weight: Optional[float] = None,
        active: bool = True,
    ):
        self._id = id
        self._name = name
        self._is_active = active
        # weight uses setter method for defensive validation
        self.weight = weight

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        self._name = name

    @property
    def weight(self) -> Optional[float]:
        weight = 0.0 if not self._is_active else self._weight
        return weight

    @weight.setter
    def weight(self, weight: Optional[float]) -> None:
        self._weight = Category.validate_weight_input(weight)

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def is_archived(self) -> bool:
        """Deprecated: use 'is_active' instead."""
        return not self._is_active

    @property
    def status(self) -> str:
        return "'ACTIVE'" if self._is_active else "'ARCHIVED'"

    def toggle_archived_status(self) -> None:
        self._is_active = False if self._is_active else True

    def to_dict(self) -> dict:
        return {
            "id": self._id,
            "name": self._name,
            "weight": self._weight,
            "active": self._is_active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Category":
        return cls(
            id=data["id"],
            name=data["name"],
            weight=data["weight"],
            active=data["active"],
        )

    def __repr__(self) -> str:
        return f"Category({self._id}, {self._name}, {self._weight}, {self._is_active})"

    def __str__(self) -> str:
        return f"CATEGORY: name: {self._name}, weight: {self._weight}, id: {self._id}"

    # === data validators ===
    @staticmethod
    def validate_weight_input(weight: Any) -> Optional[float]:
        """
        Validates and normalizes input for a Category weight.

        Accepts None as a valid input, otherwise:
            - Casts to float,
            - Ensures the number is finite
            - Ensures it is between 0 and 100, inclusive

        Args:
            weight: The input value to validate.

        Returns:
            The normalized weight value (float or None).

        Raises:
            TypeError: If the input is not None or cannot be cast to float.
            ValueError: If the input is non-finite or out of bounds.
        """
        if weight is None:
            return None

        try:
            weight = float(weight)
        except (TypeError, ValueError):
            raise TypeError("Weight must be a number or None.")

        if not math.isfinite(weight):
            raise ValueError("Weight must be a finite number.")

        if weight < 0 or weight > 100:
            raise ValueError("Weight must be between 0 and 100.")

        return weight

    # === data manipulators ===

    def update_category_weight(self, weight: Any) -> bool:
        try:
            self.weight = weight
            return True
        except Exception:
            return False
