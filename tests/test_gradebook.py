# tests/test_gradebook.py

import os
import json
import tempfile
from models.student import Student


def test_add_student(sample_gradebook, sample_student):
    sample_gradebook.add_student(sample_student)
    assert sample_student in sample_gradebook.students.values()


def test_add_student_and_save(sample_gradebook, sample_student):
    sample_gradebook.add_student(sample_student)

    with tempfile.TemporaryDirectory() as temp_dir:
        sample_gradebook.metadata = {
            "name": "Test Course",
            "term": "Fall 1987",
            "created_at": "Testing",
        }

        sample_gradebook.save(temp_dir)

        students_path = os.path.join(temp_dir, "students.json")
        assert os.path.exists(students_path)

        with open(students_path) as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "s001"
        assert data[0]["last_name"] == "Cameron"


def test_add_assignment(sample_gradebook, sample_assignment):
    sample_gradebook.add_assignment(sample_assignment)
    assert sample_assignment in sample_gradebook.assignments.values()


def test_add_assignment_and_save(sample_gradebook, sample_assignment):
    sample_gradebook.add_assignment(sample_assignment)

    with tempfile.TemporaryDirectory() as temp_dir:
        sample_gradebook.metadata = {
            "name": "Test Course",
            "term": "Fall 1987",
            "created_at": "Testing",
        }

        sample_gradebook.save(temp_dir)

        assignments_path = os.path.join(temp_dir, "assignments.json")
        assert os.path.exists(assignments_path)

        with open(assignments_path) as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "a001"
        assert data[0]["name"] == "test_assignment"


def test_create_new_gradebook(create_new_gradebook):
    assert create_new_gradebook.name == "THTR 274A"
    assert create_new_gradebook.term == "FALL 2025"


def test_load_gradebook_from_file(load_gradebook_from_file):
    assert load_gradebook_from_file.name == "THTR 274B"
    assert load_gradebook_from_file.term == "SPRING 2026"


def test_add_students_and_remove_one(create_new_gradebook):
    gradebook = create_new_gradebook
    student_1 = Student("s001", "Harry", "Potter", "hpotter@hogwarts.edu")
    student_2 = Student("s002", "Ron", "Weasley", "rweasley@hogwarts.edu")

    gradebook.add_student(student_1)
    gradebook.add_student(student_2)

    assert student_1 in gradebook.students.values()
    assert student_2 in gradebook.students.values()

    gradebook.remove_student(student_1)

    assert student_1 not in gradebook.students.values()
    assert student_2 in gradebook.students.values()
