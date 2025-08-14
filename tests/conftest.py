# tests/conftest.py

import os
from datetime import datetime

import pytest

from models.assignment import Assignment
from models.category import Category
from models.gradebook import Gradebook
from models.student import Student
from models.submission import Submission

TEST_DATA_DIR = os.path.join(
    os.path.expanduser("~"), "repos", "gradebook", "tests", "test_data"
)


@pytest.fixture
def sample_gradebook():
    gradebook_response = Gradebook.create("THTR 274A", "FALL 2025", TEST_DATA_DIR)
    return gradebook_response.data["gradebook"]


@pytest.fixture
def create_new_gradebook():
    gradebook_response = Gradebook.create("THTR 274A", "FALL 2025", TEST_DATA_DIR)
    return gradebook_response.data["gradebook"]


@pytest.fixture
def load_gradebook_from_file():
    Gradebook.create("THTR 274B", "SPRING 2026", TEST_DATA_DIR)
    gradebook_response = Gradebook.load(TEST_DATA_DIR)
    return gradebook_response.data["gradebook"]


@pytest.fixture
def sample_student():
    return Student("s001", "Sean", "Cameron", "scameron@mmm.edu")


@pytest.fixture
def sample_assignment():
    due_date = datetime.strptime("1987-06-21 23:59", "%Y-%m-%d %H:%M")
    return Assignment(
        id="a001",
        name="test_assignment",
        category_id="c001",
        points_possible=50.0,
        due_date=due_date,
    )


@pytest.fixture
def sample_unweighted_category():
    return Category("c001", "test_category")


@pytest.fixture
def sample_weighted_category():
    return Category("c002", "test_category", 100.0)


@pytest.fixture
def sample_submission():
    return Submission(
        id="sub001",
        student_id="s001",
        assignment_id="a001",
        points_earned=40.0,
        is_late=False,
        is_exempt=False,
    )


@pytest.fixture
def sample_late_submission():
    return Submission("sub002", "s001", "a001", 40.0, True)
