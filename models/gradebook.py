# models/gradebook.py

import os, json
from datetime import datetime
from typing import Any, Callable
from models.student import Student
from models.category import Category
from models.assignment import Assignment
from models.submission import Submission


class Gradebook:

    def __init__(self):
        self.students = {}
        self.categories = {}
        self.assignments = {}
        self.submissions = {}
        self.metadata = {}

    @classmethod
    def create(cls, name, term, save_dir) -> "Gradebook":
        gradebook = cls()

        gradebook.metadata = {
            "name": name,
            "term": term,
            "created_at": datetime.now().isoformat(),
        }

        gradebook.save(save_dir)

        return gradebook

    @classmethod
    def load(cls, path) -> "Gradebook":
        def read_json(filename) -> list[Any] | dict[str, Any]:
            with open(os.path.join(path, filename), "r") as f:
                return json.load(f)

        def load_and_import(
            filename: str, import_fn: Callable[[list[Any]], None]
        ) -> None:
            data = read_json(filename)
            if not isinstance(data, list):
                raise ValueError(f"Expected {filename} to contain a list.")
            else:
                import_fn(data)

        gradebook = Gradebook()

        gradebook.metadata = read_json("metadata.json")

        load_and_import("students.json", gradebook.import_students)
        load_and_import("categories.json", gradebook.import_categories)
        load_and_import("assignments.json", gradebook.import_assignments)
        load_and_import("submissions.json", gradebook.import_submissions)

        return gradebook

    def save(self, path) -> None:
        def write_json(filename, data) -> None:
            with open(os.path.join(path, filename), "w") as f:
                json.dump(data, f, indent=2, sort_keys=True)

        write_json("metadata.json", self.metadata)
        write_json("students.json", [s.to_dict() for s in self.students.values()])
        write_json("categories.json", [c.to_dict() for c in self.categories.values()])
        write_json("assignments.json", [a.to_dict() for a in self.assignments.values()])
        write_json("submissions.json", [s.to_dict() for s in self.submissions.values()])

    def import_students(self, student_data: list) -> None:
        for student_dict in student_data:
            student = Student.from_dict(student_dict)
            self.add_student(student)

    def import_categories(self, category_data: list) -> None:
        for category_dict in category_data:
            category = Category.from_dict(category_dict)
            self.add_category(category)

    def import_assignments(self, assignment_data: list) -> None:
        for assignment_dict in assignment_data:
            assignment = Assignment.from_dict(assignment_dict)
            self.add_assignment(assignment)

    def import_submissions(self, submission_data: list) -> None:
        for submission_dict in submission_data:
            submission = Submission.from_dict(submission_dict)
            self.add_submission(submission)

    def add_student(self, student) -> None:
        self.students[student.id] = student

    def add_category(self, category) -> None:
        self.categories[category.id] = category

    def add_assignment(self, assignment) -> None:
        self.assignments[assignment.id] = assignment

    def add_submission(self, submission) -> None:
        self.submissions[submission.id] = submission
