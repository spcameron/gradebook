# models/gradebook.py

"""
The Gradebook model is the central data object of the program and represents the "source of truth" for all data records.

Linked Assignments, Categories, Students, and Submissions are stored in dictionaries and written to .json upon saving,
along with a Gradebook.metadata that stores course specific information.

Provides functions for loading a Gradebook from memory, and saving a Gradebook and all relevant linked data to memory.
Includes attributes that are session-scoped like dir_path (current save location) and unsaved_changes (unsaved mutations to linked data).
Provides functions for importing, adding, removing, and finding RecordTypes, as well as methods for verifying unique values before adding.
"""
from __future__ import annotations

import datetime
import json
import os
from typing import Any, Callable

from core.response import ErrorCode, Response
from models.assignment import Assignment
from models.category import Category
from models.student import AttendanceStatus, Student
from models.submission import Submission
from models.types import RecordType


class Gradebook:

    def __init__(self, save_dir_path: str):
        self._metadata: dict[str, Any] = {}
        self._students: dict[str, Student] = {}
        self._categories: dict[str, Category] = {}
        self._assignments: dict[str, Assignment] = {}
        self._submissions: dict[str, Submission] = {}
        self._class_dates: set[datetime.date] = set()
        # _dir_path uses property setter
        self.dir_path: str = save_dir_path
        self._unsaved_changes: bool = False

    # === properties ===

    # --- core data structures ---

    @property
    def students(self) -> dict[str, Student]:
        return self._students

    @property
    def categories(self) -> dict[str, Category]:
        return self._categories

    @property
    def assignments(self) -> dict[str, Assignment]:
        return self._assignments

    @property
    def submissions(self) -> dict[str, Submission]:
        return self._submissions

    @property
    def class_dates(self) -> set[datetime.date]:
        return self._class_dates

    # --- metadata fields ---

    @property
    def name(self) -> str:
        return self._metadata["name"]

    @property
    def term(self) -> str:
        return self._metadata["term"]

    @property
    def uses_weighting(self) -> bool:
        return self._metadata["uses_weighting"]

    @property
    def path(self) -> str:
        return self._dir_path

    # TODO: probably worth including validation and defense
    @path.setter
    def path(self, dir_path: str) -> None:
        self._dir_path = dir_path

    # --- status markers ---

    @property
    def has_unsaved_changes(self) -> bool:
        return self._unsaved_changes

    def weighting_status(self) -> str:
        return "[ENABLED]" if self.uses_weighting else "[DISABLED]"

    # === public classmethods ===

    @classmethod
    def create(cls, name: str, term: str, save_dir_path: str) -> Response:
        """
        Creates, saves, and returns a new `Gradebook` instance.

        Args:
            name (str): The course name.
            term (str): The course term.
            save_dir_path (str): The path for writing and reading serialized data.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the `Gradebook` object was created successfully.
                    - False if invalid data is passed or there is missing input.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, None.
                - error (ErrorCode | str | None):
                    - `ErrorCode.INVALID_FIELD_VALUE` if ValueError raised.
                    - `ErrorCode.MISSING_REQUIRED_FIELD` if TypeError raised.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None): Payload with the following keys:
                    - On success:
                        - "gradebook" (Gradebook): The newly created `Gradebook` object.
                    - On failure:
                        - None

        Notes:
            - This method writes to disk with `gradebook.save()` before returning.
        """
        try:
            gradebook = cls(save_dir_path)
            gradebook._metadata = {
                "name": name,
                "term": term,
                "uses_weighting": False,
                "created_at": datetime.datetime.now().isoformat(),
            }
            gradebook.save(save_dir_path)

        except ValueError as e:
            return Response.fail(
                detail=f"Invalid field value: {e}",
                error=ErrorCode.INVALID_FIELD_VALUE,
            )

        except TypeError as e:
            return Response.fail(
                detail=f"Missing required field: {e}",
                error=ErrorCode.MISSING_REQUIRED_FIELD,
            )

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            return Response.succeed(
                data={
                    "gradebook": gradebook,
                },
            )

    @classmethod
    def load(cls, save_dir_path: str) -> Response:
        """
        Loads previously serialized data from disk and returns a `Gradebook` instance.

        Args:
            save_dir_path (str): The directory path where the gradebook data is stored.

        Returns:
            Response: A structured response with the following contract:
                - success (bool): True if the load operation was successful.
                    - True if the load operation was successful and new `Gradebook` object was created successfully.
                    - False for JSON deserialization issues, invalid input, or missing fields.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, None.
                - error (ErrorCode | str | None):
                    - `ErrorCode.INVALID_INPUT` if JSONDecodeError raised.
                    - `ErrorCode.INVALID_FIELD_VALUE` if ValueError raised.
                    - `ErrorCode.MISSING_REQUIRED_FIELD` if TypeError raised.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None): Payload with the following keys:
                    - On success:
                        - "gradebook" (Gradebook): The newly created `Gradebook` object.
                    - On failure:
                        - None


        Notes:
            - The caller is responsible for ensuring that `save_dir_path` exists and is readable.
        """

        def read_json(filename: str) -> list[Any] | dict[str, Any]:
            """
            Helper method to open, load, and return JSON data.

            Args:
                filename (str): The file path for the target data.

            Returns:
               The deserialized JSON data, as either a dictionary or list.
            """
            with open(os.path.join(save_dir_path, filename), "r") as f:
                return json.load(f)

        def load_and_import(
            filename: str, import_fn: Callable[[list[Any]], None]
        ) -> None:
            """
            Helper method to handle JSON data according to custom import functions.

            Args:
                filename (str): The file path for the target data.
                import_fn (Callable[[list[Any]], None]): Function provided for loading the data into memory.
            """
            data = read_json(filename)
            if not isinstance(data, list):
                raise ValueError(f"Expected {filename} to contain a list.")
            else:
                import_fn(data)

        try:
            gradebook = cls(save_dir_path)
            gradebook.import_metadata(save_dir_path)

            load_and_import("students.json", gradebook.import_students)
            load_and_import("categories.json", gradebook.import_categories)
            load_and_import("assignments.json", gradebook.import_assignments)
            load_and_import("submissions.json", gradebook.import_submissions)

        except json.JSONDecodeError as e:
            return Response.fail(
                detail=f"Failed to parse JSON data: {e}",
                error=ErrorCode.INVALID_INPUT,
            )

        except ValueError as e:
            return Response.fail(
                detail=f"Invalid field value: {e}",
                error=ErrorCode.INVALID_FIELD_VALUE,
            )

        except TypeError as e:
            return Response.fail(
                detail=f"Missing required field: {e}",
                error=ErrorCode.MISSING_REQUIRED_FIELD,
            )

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            return Response.succeed(
                data={
                    "gradebook": gradebook,
                },
            )

    # === persistence and import ===

    def save(self, save_dir_path: str | None = None) -> Response:
        """
        Serializes and saves data to disk in JSON format.

        Args:
            save_dir_path (str):
                - The directory path where the gradebook data will be saved.
                - If no argument is provided, `self.dir_path` will be used by default.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the gradebook data was saved successfully to disk.
                    - False for JSON serialization issues, invalid input, or missing fields.
                - detail (str | None):
                    - On success:
                        - "Gradebook successfully saved to disk."
                    - On failure:
                        - Description of the error if the save failed.
                - error (ErrorCode | str | None):
                    - `ErrorCode.INVALID_FIELD_VALUE` if ValueError or TypeError raised.
                    - `ErrorCode.INTERNAL_ERROR` if OSError raised or for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None): Unused in this method.


        Notes:
            - The caller is responsible for ensuring that `save_dir_path` exists if passed as an argument.
        """

        def write_json(filename: str, data: list | dict) -> None:
            """
            Helper method to serialize data to JSON format and write to disk.

            Args:
                filename (str): The target file path for the saved data.
                data (list | dict): The list or dictionary being serialized.

            Notes:
                - This intentionally overwrites existing data.
            """
            nonlocal save_dir_path
            if save_dir_path is None:
                save_dir_path = self.dir_path

            with open(os.path.join(save_dir_path, filename), "w") as f:
                json.dump(data, f, indent=2, sort_keys=True)

        try:
            write_json("metadata.json", self._metadata)
            write_json("students.json", [s.to_dict() for s in self.students.values()])
            write_json(
                "categories.json", [c.to_dict() for c in self.categories.values()]
            )
            write_json(
                "assignments.json", [a.to_dict() for a in self.assignments.values()]
            )
            write_json(
                "submissions.json", [s.to_dict() for s in self.submissions.values()]
            )
            write_json("class_dates.json", [d.isoformat() for d in self.class_dates])

            self._unsaved_changes = False

        except ValueError as e:
            return Response.fail(
                detail=f"Invalid field value: {e}",
                error=ErrorCode.INVALID_FIELD_VALUE,
            )

        except TypeError as e:
            return Response.fail(
                detail=f"Object not JSON serializable: {e}",
                error=ErrorCode.INVALID_FIELD_VALUE,
            )

        except OSError as e:
            return Response.fail(
                detail=f"Failed to write data to disk: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            return Response.succeed(detail="Gradebook successfully saved to disk.")

    def import_metadata(self, dir_path: str) -> None:
        """
        Loads gradebook metadata and other optional class data from disk.

        Args:
            dir_path (str): The directory path where the gradebook data is stored.

        Raises:
            ValueError:
                - If `metadata.json` does not contain a dictionary.
                - If `class_dates.json` exists but does not contain a list of ISO-formatted strings.

        Notes:
            - If `class_dates.json` does not exist, no error is raised and `self._class_dates` is initialized as an empty set.
        """

        def read_json(filename: str) -> list[Any] | dict[str, Any]:
            """
            Helper method to open, load, and return JSON data.

            Args:
                filename (str): The file path for the target data.

            Returns:
                The deserialized JSON data, as either a dictionary or list.
            """
            with open(os.path.join(dir_path, filename), "r") as f:
                return json.load(f)

        # Load metadata
        raw_metadata = read_json("metadata.json")
        if not isinstance(raw_metadata, dict):
            raise ValueError("metadata.json must contain a dictionary.")
        self._metadata = raw_metadata

        # Load class_dates (optional)
        try:
            class_dates_raw = read_json("class_dates.json")
            if not isinstance(class_dates_raw, list):
                raise ValueError(
                    "class_dates.json must contain a list of date strings."
                )

            self._class_dates = set()
            for d in class_dates_raw:
                try:
                    self._class_dates.add(datetime.date.fromisoformat(d))
                except ValueError:
                    raise ValueError(
                        f"Invalid ISO date string in class_dates.json: {d}"
                    )

        except FileNotFoundError:
            self._class_dates = set()

    def import_students(self, student_data: list) -> None:
        """
        Imports a list of student records into the gradebook.

        Args:
            student_data (list[dict[str, Any]]): A list of dictionaries representing serialized `Student` objects.

        Raises:
            ValueError:
                - If any student dictionary is malformed or missing required fields.
                - If a deserialized student fails uniqueness validation (e.g., duplicate email).

            TypeError:
                - If the input structure is incorrect (e.g., not a list of dictionaries).

        Notes:
            - This method fails fast: if any `Student` object is invalid, the entire import is aborted.
            - Designed for internal use during gradebook loading.
        """
        for student_dict in student_data:
            try:
                student = Student.from_dict(student_dict)
                self.add_student(student)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Failed to import student: {student_dict} - {e}")

    def import_categories(self, category_data: list) -> None:
        """
        Imports a list of category records into the gradebook.

        Args:
            category_data (list[dict[str, Any]]): A list of dictionaries representing serialized `Category` objects.

        Raises:
            ValueError:
                - If any category dictionary is malformed or missing required fields.
                - If a deserialized category fails uniqueness validation (e.g., duplicate name).

            TypeError:
                - If the input structure is incorrect (e.g., not a list of dictionaries).

        Notes:
            - This method fails fast: if any `Category` object is invalid, the entire import is aborted.
            - Designed for internal use during gradebook loading.
        """
        for category_dict in category_data:
            try:
                category = Category.from_dict(category_dict)
                self.add_category(category)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Failed to import category: {category_dict} - {e}")

    def import_assignments(self, assignment_data: list) -> None:
        """
        Imports a list of assignment records into the gradebook.

        Args:
            assignment_data (list[dict[str, Any]]): A list of dictionaries representing serialized `Assignment` objects.

        Raises:
            ValueError:
                - If any assignment dictionary is malformed or missing required fields.
                - If a deserialized assignment fails uniqueness validation (e.g., duplicate name).

            TypeError:
                - If the input structure is incorrect (e.g., not a list of dictionaries).

        Notes:
            - This method fails fast: if any `Assignment` object is invalid, the entire import is aborted.
            - Designed for internal use during gradebook loading.
        """
        for assignment_dict in assignment_data:
            try:
                assignment = Assignment.from_dict(assignment_dict)
                self.add_assignment(assignment)
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Failed to import assignment: {assignment_dict} - {e}"
                )

    def import_submissions(self, submission_data: list) -> None:
        """
        Imports a list of submission records into the gradebook.

        Args:
            submission_data (list[dict[str, Any]]): A list of dictionaries representing serialized `Submissions` objects.

        Raises:
            ValueError:
                - If any submission dictionary is malformed or missing required fields.
                - If a deserialized submission fails uniqueness validation (e.g. linked assignment and student ids).

            TypeError:
                - If the input structure is incorrect (e.g., not a list of dictionaries).

        Notes:
            - This method fails fast: if any `Submission` object is invalid, the entire import is aborted.
            - Designed for internal use during gradebook loading.
        """
        for submission_dict in submission_data:
            try:
                submission = Submission.from_dict(submission_dict)
                self.add_submission(submission)
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Failed to import submission: {submission_dict} - {e}"
                )

    # === data accessors ===

    def get_records(
        self,
        dictionary: dict[str, RecordType],
        predicate: Callable[[RecordType], bool] | None = None,
    ) -> Response:
        """
        Fetches records from a dictionary, optionally filtered by a predicate.

        Args:
            dictionary (dict[str, RecordType]): A mapping of record IDs to record objects.
            predicate (Callable[[RecordType], bool]): Optional filter function. If omitted, all records are returned.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the operation succeeded, even if no records were found.
                    - False for unexpected errors.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, None.
                - error (ErrorCode | str | None):
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None): Payload with the following keys:
                    - On success:
                        - "records" (list[RecordType]): The list of matching records (may be empty).
                    - On failure:
                        - None

        Notes:
            - This method is read-only and never raises exceptions.
            - The "records" key is always included on success, even if the result is empty.
        """
        try:
            if predicate:
                records = list(filter(predicate, dictionary.values()))
            else:
                records = list(dictionary.values())

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            return Response.succeed(
                data={
                    "records": records,
                }
            )

    # --- submission methods ---

    def get_assignment_and_student(self, submission: Submission) -> Response:
        """
        Finds the `Assignment` and `Student` objects linked to a given `Submission`.

        Args:
            submission (Submission): The `Submission` object whose associated records will be retrieved.

        Returns:
            Response: A structured response with the following contract:
                - success (bool): True if both linked records were retrieved.
                - detail (str | None): Description of the error if either record lookup fails.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if a linked record is not found.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 404 if either record not found
                    - 400 on failure
                - data (dict | None): Payload with the following keys:
                    - On success:
                        - "assignment" (Assignment): The linked `Assignment` object.
                        - "student" (Student): The linked `Student` object.
                    - On failure:
                        - None

        Notes:
            - This method is read-only and does not raise.
            - The caller is responsible for extracting and casting the records from `response.data["assignment"]` and `response.data["student"]`.
        """
        assignment_response = self.find_assignment_by_uuid(submission.assignment_id)
        if not assignment_response.success:
            return Response.fail(
                detail=f"Could not resolve assignment for submission: {assignment_response.detail}",
                error=assignment_response.error,
                status_code=assignment_response.status_code,
            )

        student_response = self.find_student_by_uuid(submission.student_id)
        if not student_response.success:
            return Response.fail(
                detail=f"Could not resolve student for submission: {student_response.detail}",
                error=student_response.error,
                status_code=student_response.status_code,
            )

        return Response.succeed(
            data={
                "assignment": assignment_response.data["record"],
                "student": student_response.data["record"],
            }
        )

    # --- attendance records ---

    def get_attendance_for_date(self, class_date: datetime.date) -> Response:
        """
        Generates an attendance report for all active students on a given class date.

        Args:
            class_date (datetime.date): The date for which to generate the attendance report.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the attendance report was generated successfully.
                    - False if the date is not in the course schedule or if no active students were found.
                - detail (str | None):
                    - On failure, a human-readable explanation of the problem.
                    - On success, None.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if the date is not part of the course schedule or if the roster is empty.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors when retrieving student records.
                - status_code (int | None):
                    - 200 on success
                    - 404 if the date is invalid or no active students exist
                    - 400 on internal failure
                - data (dict[str, dict[str, str]] | None): Payload with the following keys:
                    - On success:
                        - "attendance" (dict[str, str]): A dictionary mapping student IDs to attendance status strings for the given date.
                    - On failure:
                        - None

        Notes:
            - This method is read-only and does not raise.
            - Students are sorted by last name and then first name in the output.
            - The return data dictionary always uses a named key ("attendance") to support consistent response unpacking and future extensibility.
        """
        if class_date not in self.class_dates:
            return Response.fail(
                detail=f"The selected date could not be found in the course schedule: {class_date.isoformat()}.",
                error=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        attendance_report = {}

        students_response = self.get_records(
            self.students,
            lambda x: x.is_active,
        )

        if not students_response.success:
            return Response.fail(
                detail=f"Could not populate the list of active students: {students_response.detail}",
                error=students_response.error,
                status_code=students_response.status_code,
            )

        active_students = students_response.data["records"]

        if not active_students:
            return Response.fail(
                detail=f"No active students found to report attendance for {class_date.isoformat()}.",
                error=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        for student in sorted(
            active_students, key=lambda x: (x.last_name, x.first_name)
        ):
            status = student.attendance_on(class_date)
            attendance_report[student.id] = (
                "[UNMARKED]" if status == AttendanceStatus.UNMARKED else status.value
            )

        return Response.succeed(
            data={
                "attendance": attendance_report,
            },
        )

    def get_attendance_for_student(self, student: Student) -> Response:
        """
        Generates an attendance report for the given student across all scheduled class dates.

        Args:
            student (Student): The student for whom the attendance report is generated.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the report was generated successfully.
                    - False if the student is not in the roster.
                - detail (str | None):
                    - On failure, a human-readable explanation of the problem.
                    - On success, None.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if the student is not found.
                - status_code (int | None):
                    - 200 on success
                    - 404 if the student is not found
                - data (dict | None):
                    - On success:
                        - "attendance" (dict[datetime.date, str]): A dictionary mapping `datetime.date` objects to attendance status strings.
                    - On failure:
                        - None

        Notes:
            - This method is read-only and does not raise.
            - The output dictionary is sorted by class date in ascending order.
            - Dates are returned as `datetime.date` objects, not strings.
        """
        if student.id not in self.students:
            return Response.fail(
                detail=f"The selected student is not in the class roster: {student.full_name}.",
                error=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        attendance_report = {}

        for class_date in sorted(self.class_dates):
            status = student.attendance_on(class_date)
            attendance_report[class_date] = (
                "[UNMARKED]" if status == AttendanceStatus.UNMARKED else status.value
            )

        return Response.succeed(
            data={
                "attendance": attendance_report,
            },
        )

    # TODO: resume refactor from here
    def get_total_absences_for_student(self, student: Student) -> int:
        return sum(1 for absence in student.absences if absence in self.class_dates)

    # --- find record by uuid ---

    def find_record_by_uuid(
        self,
        uuid: str,
        dictionary: dict[str, RecordType],
    ) -> Response:
        """
        Finds a record by UUID within a given dictionary.

        Args:
            uuid (str): The unique ID of the record.
            dictionary (dict[str, RecordType]): The dictionary of records to search.

        Returns:
            Response: A structured response with the following contract:
                - success (bool): True if the record was found.
                - detail (str | None): Description of the error if no match was found or the operation failed.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if no match is found.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 404 if not found
                    - 400 on failure
                - data (dict): Payload with the following keys:
                    - On success:
                        - "record" (RecordType): The matched record object. Included only if found.
                    - On failure:
                        - None

        Notes:
            - This method is read-only and does not raise.
            - The "record" key is only included in the response on success.
            - The caller is responsible for extracting and casting the record from `response.data["record"]`.
        """
        try:
            record = dictionary.get(uuid)

            if record is None:
                return Response.fail(
                    detail=f"No matching record found for {uuid}.",
                    error=ErrorCode.NOT_FOUND,
                    status_code=404,
                )

            return Response.succeed(
                data={
                    "record": record,
                },
            )
        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

    def find_student_by_uuid(self, uuid: str) -> Response:
        """
        Finds a `Student` object by UUID within `gradebook.students`.

        Args:
            uuid (str): The unique ID of the `Student` object.

        Returns:
            Response: A structured response with the following contract:
                - success (bool): True if the `Student` object was found.
                - detail (str | None): Description of the error if no match was found or the operation failed.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if no match is found.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 404 if no match is found
                    - 400 on failure
                - data (dict): Payload with the following keys:
                    - On success:
                        - "record" (Student): The matched `Student` object. Included only if found.
                    - On failure:
                        None

        Notes:
            - This method is read-only and does not raise.
            - The "record" key is only included in the response on success.
            - The caller is responsible for extracting and casting the `Student` object from `response.data["record"]`.
        """
        return self.find_record_by_uuid(uuid, self.students)

    def find_category_by_uuid(self, uuid: str) -> Response:
        """
        Finds a `Category` object by UUID within `gradebook.categories`.

        Args:
            uuid (str): The unique ID of the `Category` object.

        Returns:
            Response: A structured response with the following contract:
                - success (bool): True if the `Category` object was found.
                - detail (str | None): Description of the error if no match was found or the operation failed.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if no match is found.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 404 if no match is found
                    - 400 on failure
                - data (dict): Payload with the following keys:
                    - On success:
                        - "record" (Category): The matched `Category` object. Included only if found.
                    - On failure:
                        None
        Notes:
            - This method is read-only and does not raise.
            - The "record" key is only included in the response on success.
            - The caller is responsible for extracting and casting the `Category` object from `response.data["record"]`.
        """
        return self.find_record_by_uuid(uuid, self.categories)

    def find_assignment_by_uuid(self, uuid: str) -> Response:
        """
        Finds an `Assignment` object by UUID within `gradebook.assignments`.

        Args:
            uuid (str): The unique ID of the `Assignment` object.

        Returns:
            Response: A structured response with the following contract:
                - success (bool): True if the `Assignment` object was found.
                - detail (str | None): Description of the error if no match was found or the operation failed.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if no match is found.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 404 if no match is found
                    - 400 on failure
                - data (dict): Payload with the following keys:
                    - On success:
                        - "record" (Assignment): The matched `Assignment` object. Included only if found.
                    - On failure:
                        None

        Notes:
            - This method is read-only and does not raise.
            - The "record" key is only included in the response on success.
            - The caller is responsible for extracting and casting the `Assignment` object from `response.data["record"]`.
        """
        return self.find_record_by_uuid(uuid, self.assignments)

    def find_submission_by_uuid(self, uuid: str) -> Response:
        """
        Finds a `Submission` object by UUID within `gradebook.submissions`.

        Args:
            uuid (str): The unique ID of the `Submission` object.

        Returns:
            Response: A structured response with the following contract:
                - success (bool): True if the `Submission` object was found.
                - detail (str | None): Description of the error if no match was found or the operation failed.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if no match is found.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 404 if no match if found
                    - 400 on failure
                - data (dict): Payload with the following keys:
                    - On success:
                        - "record" (Submission): The matched `Submission` object. Included only if found.
                    - On failure:
                        None

        Notes:
            - This method is read-only and does not raise.
            - The "record" key is only included in the response on success.
            - The caller is responsible for extracting and casting the `Submission` object from `response.data["record"]`.
        """
        return self.find_record_by_uuid(uuid, self.submissions)

    # TODO:
    def find_submission_by_assignment_and_student(
        self, assignment_id: str, student_id: str
    ) -> Submission | None:
        for submission in self.submissions.values():
            if (
                submission.assignment_id == assignment_id
                and submission.student_id == student_id
            ):
                return submission
        return None

    # --- find record by query ---

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

    # === data manipulators ===

    def mark_dirty(self) -> None:
        self._unsaved_changes = True

    # --- category weighting methods ---

    def toggle_is_weighted(self) -> None:
        if self.uses_weighting:
            self._metadata["uses_weighting"] = False
            self.reset_category_weights()
        else:
            self._metadata["uses_weighting"] = True

    # TODO: update w/ boolean return values
    def reset_category_weights(self) -> None:
        active_categories = self.get_records(
            self.categories,
            lambda x: x.is_active,
        )

        for category in active_categories:
            category.weight = None

    # --- add records ---

    def add_record(self, record: RecordType, dictionary: dict) -> None:
        dictionary[record.id] = record

    # TODO: unique record validation
    def add_student(self, student: Student) -> None:
        self.add_record(student, self.students)

    def add_category(self, category: Category) -> None:
        self.add_record(category, self.categories)

    def add_assignment(self, assignment: Assignment) -> None:
        self.add_record(assignment, self.assignments)

    def add_submission(self, submission: Submission) -> None:
        self.add_record(submission, self.submissions)

    # --- remove records ---

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

    # --- attendance methods ---

    def add_class_date(self, class_date: datetime.date) -> bool:
        if class_date in self.class_dates:
            return False

        self.class_dates.add(class_date)
        self.mark_dirty()
        return True

    def batch_add_class_dates(self, class_dates: list[datetime.date]) -> bool:
        for class_date in class_dates:
            self.add_class_date(class_date)

        if any(date not in self.class_dates for date in class_dates):
            return False

        return True

    def remove_class_date(self, class_date: datetime.date) -> bool:
        if class_date not in self.class_dates:
            return False

        self.class_dates.discard(class_date)

        for student in self.students.values():
            student.remove_absence(class_date)

        self.mark_dirty()
        return True

    def remove_all_class_dates(self) -> bool:
        for class_date in list(self.class_dates):
            self.remove_class_date(class_date)

        if len(self.class_dates) > 0:
            return False

        return True

    def mark_student_absent(self, student: Student, class_date: datetime.date) -> bool:
        if student.id not in self.students:
            raise ValueError(
                f"Cannot mark absence: {student.full_name} is not enrolled in this course."
            )

        if class_date not in self.class_dates:
            raise ValueError(
                f"Cannot mark absence: {class_date.strftime('%Y-%m-%d')} is not in the class schedule."
            )

        if student.mark_absent(class_date):
            self.mark_dirty()
            return True

        return False

    def unmark_student_absent(
        self, student: Student, class_date: datetime.date
    ) -> bool:
        if student.id not in self.students:
            raise ValueError(
                f"Cannot unmark absence: {student.full_name} is not enrolled in this course."
            )

        if class_date not in self.class_dates:
            raise ValueError(
                f"Cannot unmark absence: {class_date.strftime('%Y-%m-%d')} is not in the class schedule."
            )

        if student.remove_absence(class_date):
            self.mark_dirty()
            return True

        return False

    # === data validators ===

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


# docstring template for methods that return Response objects


"""
TEMPLATE FOR DOCSTRINGS THAT RETURN A RESPONSE

<One-sentence summary of what this method does.>

Args:
    <param1> (<type>): <description>.
    <param2> (<type>): <description>.
    ...

Returns:
    Response: A structured response with the following contract:
        - success (bool): True if the operation was successful.
        - detail (str | None): Description of the result for display or logging.
        - error (ErrorCode | str | None): A machine-readable error code, if any.
        - status_code (int | None): HTTP-style status code (e.g., 200, 404). Optional in CLI.
        - data (dict | None): Payload with the following keys:
            - "<key1>" (<type>): <description of value>.
            - "<key2>" (<type>): <description of value>.
            ...

Notes:
    - <State if method is read-only or mutates gradebook state>.
    - <Mention any expected preconditions or invariants>.
    - <What does success/failure look like, if not clear from above?>
    - <What assumptions must the caller uphold?>
    - <Does this touch or cascade to other objects?>
"""
