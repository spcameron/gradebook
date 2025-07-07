# tests/conftest.py

import os
import pytest
from models.student import Student
from models.gradebook import Gradebook
from models.assignment import Assignment
from models.category import Category
from models.submission import Submission

TEST_DATA_DIR = os.path.join(
    os.path.expanduser("~"), "repos", "gradebook", "tests", "test_data"
)


@pytest.fixture
def sample_gradebook():
    return Gradebook.create("THTR 274A", "FALL 2025", TEST_DATA_DIR)


@pytest.fixture
def create_new_gradebook():
    return Gradebook.create("THTR 274A", "FALL 2025", TEST_DATA_DIR)


@pytest.fixture
def load_gradebook_from_file():
    Gradebook.create("THTR 274B", "SPRING 2026", TEST_DATA_DIR)
    return Gradebook.load(TEST_DATA_DIR)


@pytest.fixture
def sample_student():
    return Student("s001", "Sean", "Cameron", "scameron@mmm.edu")


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
