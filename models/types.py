# models/types.py

"""
Holds TypeVar definition for simplifying type checks.
"""

from typing import TypeVar

from .assignment import Assignment
from .category import Category
from .student import Student
from .submission import Submission

RecordType = TypeVar("RecordType", Assignment, Category, Student, Submission)
