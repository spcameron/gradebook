# gradebook.py

import os, json
from datetime import datetime


class Gradebook:

    def __init__(self):
        self.students = {}
        self.assignments = {}
        self.categories = {}
        self.submissions = []
        self.metadata = {}

    @classmethod
    def create(cls, name, term, path=None) -> "Gradebook":
        gradebook = cls()

        # ensure path exists
        if not path:
            path = os.path.join("Courses", f"{term}_{name}")

        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)

        # initialize metadata
        gradebook.metadata = {
            "name": name,
            "term": term,
            "created_at": datetime.now().isoformat(),
        }

        # call save
        gradebook.save(path)

        return gradebook

    def save(self, path) -> None:
        # internal helper method to write json
        def write_json(filename, data):
            with open(os.path.join(path, filename), "w") as f:
                json.dump(data, f, indent=2, sort_keys=True)

        write_json("students.json", [s.to_dict() for s in self.students.values()])
        write_json("assignments.json", [a.to_dict() for a in self.assignments.values()])
        write_json("submissions.json", [s.to_dict() for s in self.submissions])
        write_json("metadata.json", self.metadata)
