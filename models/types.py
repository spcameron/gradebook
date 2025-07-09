# models/types.py

from .assignment import Assignment
from .category import Category
from .student import Student
from .submission import Submission
from typing import TypeVar

RecordType = TypeVar("RecordType", Assignment, Category, Student, Submission)
