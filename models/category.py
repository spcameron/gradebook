# models/category.py

"""
Represents a grade category within the Gradebook.

Each `Category` groups related `Assignment` records and may optionally carry a weight
used for calculating weighted grades. If weighting is disabled, all categories are treated equally.

Key behaviors:
- `weight`: Accepts a float from 0 to 100, or None if unweighted. Returns 0.0 if the category is archived.
- `is_active`: Controls whether the category is currently included in grade calculations.
- `toggle_archived_status()`: Used to archive or restore a category.
- `to_dict()` / `from_dict()`: Used for serialization and persistence.

Notes:
- The `is_archived` property is deprecated; use `is_active` for clarity.
- All weight validation is handled through `validate_weight_input()` and enforced via the setter.
"""

from __future__ import annotations

import math
from typing import Any


class Category:

    def __init__(
        self,
        id: str,
        name: str,
        weight: float | None = None,
        active: bool = True,
    ):
        self._id = id
        self._name = name
        self._is_active = active
        # weight uses setter method for defensive validation
        self.weight = weight

    # === properties ===

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
    def weight(self) -> float | None:
        weight = 0.0 if not self._is_active else self._weight
        return weight

    @weight.setter
    def weight(self, weight: float | str | None) -> None:
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
        self._is_active = not self._is_active

    # === persistence and import ===

    def to_dict(self) -> dict:
        return {
            "id": self._id,
            "name": self._name,
            "weight": self._weight,
            "active": self._is_active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Category:
        return cls(
            id=data["id"],
            name=data["name"],
            weight=data["weight"],
            active=data["active"],
        )

    # === dunder methods ===

    def __repr__(self) -> str:
        return f"Category({self._id}, {self._name}, {self._weight}, {self._is_active})"

    def __str__(self) -> str:
        return f"CATEGORY: name: {self._name}, weight: {self._weight}, id: {self._id}"

    # === data validators ===

    @staticmethod
    def validate_weight_input(weight: Any) -> float | None:
        """
        Validates and normalizes input for a `Category` weight.

        Accepts None as a valid input, otherwise:
            - Casts to float.
            - Ensures the number is finite.
            - Ensures it is between 0 and 100, inclusive.

        Args:
            weight (Any): The input value to validate.

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
