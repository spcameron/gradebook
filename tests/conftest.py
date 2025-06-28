# tests/conftest.py

import pytest, os
from models.student import Student
from models.gradebook import Gradebook


@pytest.fixture
def sample_gradebook():
    return Gradebook()


@pytest.fixture
def sample_student():
    return Student("s001", "Sean Cameron", "scameron@mmm.edu")
