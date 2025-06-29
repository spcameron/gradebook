# tests/conftest.py

import pytest
from models.student import Student
from models.gradebook import Gradebook
from models.assignment import Assignment
from models.category import Category
from models.submission import Submission


@pytest.fixture
def sample_gradebook():
    return Gradebook()


@pytest.fixture
def sample_student():
    return Student("s001", "Sean Cameron", "scameron@mmm.edu")


@pytest.fixture
def sample_assignment():
    return Assignment("a001", "test_assignment", "c001", 50.0)


@pytest.fixture
def sample_unweighted_category():
    return Category("c001", "test_category")


@pytest.fixture
def sample_weighted_category():
    return Category("c002", "test_category", 100.0)


@pytest.fixture
def sample_submission():
    return Submission("sub001", "s001", "a001", 40.0)


@pytest.fixture
def sample_late_submission():
    return Submission("sub002", "s001", "a001", 40.0, True)
