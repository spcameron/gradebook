# models/gradebook.py

"""
The Gradebook model is the central data object of the program and represents the "source of truth" for all data records.

Linked Assignments, Categories, Students, and Submissions are stored in dictionaries and written to .json upon saving,
along with a Gradebook.metadata that stores course specific information.

Provides functions for loading a Gradebook from memory, and saving a Gradebook and all relevant linked data to memory.
Includes attributes that are session-scoped like dir_path (current save location) and unsaved_changes (unsaved mutations to linked data).
Provides functions for importing, adding, removing, and finding RecordTypes, as well as methods for verifying unique values before adding.
"""
import json
import os
from datetime import datetime
from typing import Any, Callable, Optional

from models.assignment import Assignment
from models.category import Category
from models.student import Student
from models.submission import Submission
from models.types import RecordType


class Gradebook:

    def __init__(self, save_dir_path: str):
        self.students = {}
        self.categories = {}
        self.assignments = {}
        self.submissions = {}
        self._metadata = {}  # assumed to contain name, term, and created_at
        self._dir_path = save_dir_path
        self._unsaved_changes = False

    @property
    def path(self) -> str:
        return self._dir_path

    @property
    def name(self) -> str:
        return self._metadata["name"]

    @property
    def term(self) -> str:
        return self._metadata["term"]

    @property
    def uses_weighting(self) -> bool:
        return self._metadata["uses_weighting"]

    def toggle_uses_weighting(self) -> None:
        self._metadata["uses_weighting"] = False if self.uses_weighting else True

    @property
    def unsaved_changes(self) -> bool:
        return self._unsaved_changes

    def mark_dirty(self) -> None:
        self._unsaved_changes = True

    @classmethod
    def create(cls, name: str, term: str, save_dir_path: str) -> "Gradebook":
        gradebook = cls(save_dir_path)
        gradebook._dir_path = save_dir_path
        gradebook._metadata = {
            "name": name,
            "term": term,
            "uses_weighting": False,
            "created_at": datetime.now().isoformat(),
        }

        gradebook.save(save_dir_path)

        return gradebook

    @classmethod
    def load(cls, save_dir_path: str) -> "Gradebook":
        def read_json(filename: str) -> list[Any] | dict[str, Any]:
            with open(os.path.join(save_dir_path, filename), "r") as f:
                return json.load(f)

        def load_and_import(
            filename: str, import_fn: Callable[[list[Any]], None]
        ) -> None:
            data = read_json(filename)
            if not isinstance(data, list):
                raise ValueError(f"Expected {filename} to contain a list.")
            else:
                import_fn(data)

        print("\nLoading Gradebook ...")

        gradebook = cls(save_dir_path)
        gradebook._dir_path = save_dir_path
        gradebook._metadata = read_json("metadata.json")

        load_and_import("students.json", gradebook.import_students)
        load_and_import("categories.json", gradebook.import_categories)
        load_and_import("assignments.json", gradebook.import_assignments)
        load_and_import("submissions.json", gradebook.import_submissions)

        print("... load complete.")

        return gradebook

    def save(self, save_dir_path: str) -> None:
        def write_json(filename: str, data: list | dict) -> None:
            with open(os.path.join(save_dir_path, filename), "w") as f:
                json.dump(data, f, indent=2, sort_keys=True)

        print("\nSaving Gradebook ...")

        write_json("metadata.json", self._metadata)
        write_json("students.json", [s.to_dict() for s in self.students.values()])
        write_json("categories.json", [c.to_dict() for c in self.categories.values()])
        write_json("assignments.json", [a.to_dict() for a in self.assignments.values()])
        write_json("submissions.json", [s.to_dict() for s in self.submissions.values()])

        print("... save complete.")

        self._unsaved_changes = False

    # === import methods ===

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

    # === add methods ===

    def add_record(self, record: RecordType, dictionary: dict) -> None:
        dictionary[record.id] = record

    def add_student(self, student: Student) -> None:
        self.add_record(student, self.students)

    def add_category(self, category: Category) -> None:
        self.add_record(category, self.categories)

    def add_assignment(self, assignment: Assignment) -> None:
        self.add_record(assignment, self.assignments)

    def add_submission(self, submission: Submission) -> None:
        self.add_record(submission, self.submissions)

    # === remove methods ===

    def remove_record(self, record: RecordType, dictionary: dict) -> None:
        try:
            del dictionary[record.id]
        except KeyError:
            print("\nERROR: No matching record could be found for deletion.")
            from cli.menu_helpers import confirm_action

            if confirm_action("Would you like to display the faulty deletion request?"):
                print(
                    f"\nThe following record was queued for deletion, but could not be located in the Gradebook:"
                )
                print(f" ... {record}")

    def remove_student(self, student: Student) -> None:
        """
        Removes a Student from self.students.

        Args:
            student: The Student targeted for deletion.

        Notes:
            Recursively deletes all linked Submissions as well.
        """
        self.remove_record(student, self.students)
        linked_submissions = self.get_records(
            self.submissions, lambda x: x.student_id == student.id
        )
        for submission in linked_submissions:
            self.remove_submission(submission)

    def remove_category(self, category: Category) -> None:
        """
        Removes a Category from self.categories.

        Args:
            category: The Category targeted for deletion.

        Notes:
            Recursively deletes all linked Assignments (and therefore Submissions) as well.
        """
        self.remove_record(category, self.categories)
        linked_assignments = self.get_records(
            self.assignments, lambda x: x.category_id == category.id
        )
        for assignment in linked_assignments:
            self.remove_assignment(assignment)

    def remove_assignment(self, assignment: Assignment) -> None:
        """
        Removes an Assignment from self.assignments.

        Args:
            assignment: The Assignment targeted for deletion.

        Notes:
            Recursively deletes all linked Submissions as well.
        """
        self.remove_record(assignment, self.assignments)
        linked_submissions = self.get_records(
            self.submissions, lambda x: x.assignment_id == assignment.id
        )
        for submission in linked_submissions:
            self.remove_submission(submission)

    def remove_submission(self, submission: Submission) -> None:
        """
        Removes a Submission from self.submissions.

        Args:
            submission: The Submission targeted for deletion.
        """
        self.remove_record(submission, self.submissions)

    # === find record by uuid ===

    def find_record_by_uuid(
        self, uuid: str, dictionary: dict[str, RecordType]
    ) -> Optional[RecordType]:
        return dictionary.get(uuid)

    def find_student_by_uuid(self, uuid: str) -> Optional[Student]:
        return self.find_record_by_uuid(uuid, self.students)

    def find_category_by_uuid(self, uuid: str) -> Optional[Category]:
        return self.find_record_by_uuid(uuid, self.categories)

    def find_assignment_by_uuid(self, uuid: str) -> Optional[Assignment]:
        return self.find_record_by_uuid(uuid, self.assignments)

    def find_submission_by_uuid(self, uuid: str) -> Optional[Submission]:
        return self.find_record_by_uuid(uuid, self.submissions)

    def find_submission_by_assignment_and_student(
        self, assignment_id: str, student_id: str
    ) -> Optional[Submission]:
        for submission in self.submissions.values():
            if (
                submission.assignment_id == assignment_id
                and submission.student_id == student_id
            ):
                return submission
        return None

    # === find record by query ===

    def find_student_by_query(self, query: str) -> list[Student]:
        matches = [
            student
            for student in self.students.values()
            if query in student.full_name.lower() or query in student.email.lower()
        ]

        return matches

    def find_category_by_query(self, query: str) -> list[Category]:
        matches = [
            category
            for category in self.categories.values()
            if query in category.name.lower()
        ]

        return matches

    def find_assignment_by_query(self, query: str) -> list[Assignment]:
        matches = [
            assignment
            for assignment in self.assignments.values()
            if query in assignment.name.lower()
        ]

        return matches

    # === get records ===

    def get_records(
        self,
        dictionary: dict[str, RecordType],
        predicate: Optional[Callable[[RecordType], bool]] = None,
    ) -> list[RecordType]:
        if predicate:
            return [record for record in dictionary.values() if predicate(record)]
        return list(dictionary.values())

    def get_assignment_and_student(
        self, submission: Submission
    ) -> tuple[Assignment, Student]:
        linked_assignment = self.find_assignment_by_uuid(submission.assignment_id)
        linked_student = self.find_student_by_uuid(submission.student_id)

        if linked_assignment is None:
            raise KeyError("No linked assignment could be found.")

        if linked_student is None:
            raise KeyError("No linked student could be found.")

        return (linked_assignment, linked_student)

    # === unique record validators ===

    def _normalize(self, input: str) -> str:
        return input.strip().lower()

    def require_unique_student_email(self, email: str) -> None:
        normalized = self._normalize(email)
        if any(self._normalize(s.email) == normalized for s in self.students.values()):
            raise ValueError(f"A student with the email '{email}' already exists.")

    def require_unique_category_name(self, name: str) -> None:
        normalized = self._normalize(name)
        if any(self._normalize(c.name) == normalized for c in self.categories.values()):
            raise ValueError(f"A category with the name '{name}' already exists.")

    def require_unique_assignment_name(self, name: str) -> None:
        normalized = self._normalize(name)
        if any(
            self._normalize(a.name) == normalized for a in self.assignments.values()
        ):
            raise ValueError(f"An assignment with the name '{name}' already exists.")

    # TODO: create secondary submissions index with (s_id, a_id) tuple as key
    def submission_already_exists(self, assignment_id: str, student_id: str) -> bool:
        return any(
            (s.assignment_id == assignment_id and s.student_id == student_id)
            for s in self.submissions.values()
        )
