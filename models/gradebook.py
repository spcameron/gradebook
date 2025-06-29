# models/gradebook.py

import os, json
from datetime import datetime


class Gradebook:

    def __init__(self):
        self.students = {}
        self.assignments = {}
        self.categories = {}
        self.submissions = {}
        self.metadata = {}

    @classmethod
    def create(cls, name, term, path=None) -> "Gradebook":
        gradebook = cls()

        if not path:
            path = os.path.join("Courses", f"{term}_{name}")

        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)

        gradebook.metadata = {
            "name": name,
            "term": term,
            "created_at": datetime.now().isoformat(),
        }

        gradebook.save(path)

        return gradebook

    def save(self, path) -> None:
        def write_json(filename, data):
            with open(os.path.join(path, filename), "w") as f:
                json.dump(data, f, indent=2, sort_keys=True)

        write_json("students.json", [s.to_dict() for s in self.students.values()])
        write_json("assignments.json", [a.to_dict() for a in self.assignments.values()])
        write_json("submissions.json", [s.to_dict() for s in self.submissions.values()])
        write_json("metadata.json", self.metadata)

    def add_student(self, student) -> None:
        self.students[student.id] = student

    def add_assignment(self, assignment) -> None:
        self.assignments[assignment.id] = assignment

    def add_category(self, category) -> None:
        self.categories[category.id] = category

    def add_submission(self, submission) -> None:
        self.submissions[submission.id] = submission
