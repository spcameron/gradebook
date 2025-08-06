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

import cli.formatters as formatters
from core.response import ErrorCode, Response
from models.assignment import Assignment
from models.category import Category
from models.student import AttendanceStatus, Student
from models.submission import Submission
from models.types import RecordType


class Gradebook:
    _tracking_maps: dict[type, str] = {
        Student: "students",
        Category: "categories",
        Assignment: "assignments",
        Submission: "submissions",
    }

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
                - data (dict | None):
                    - Always None, this method does not return any payload.


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
            self._unsaved_changes = False

            return Response.succeed(detail="Gradebook successfully saved to disk.")

    def import_metadata(self, dir_path: str) -> None:
        """
        Loads gradebook metadata and other optional class data from disk.

        Args:
            dir_path (str): The directory path where the gradebook data is stored.

        Raises:
            - ValueError:
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

    def _import_records(
        self,
        data: list[dict[str, Any]],
        from_dict_fn: Callable[[dict[str, Any]], RecordType],
        add_fn: Callable[[RecordType], Response],
        record_name: str,
    ) -> None:
        """
        Deserializes and imports a list of records into the gradebook, failing fast on error.

        Args:
            data (list[dict[str, Any]]): A list of dictionaries representing serialized records.
            from_dict_fn (Callable[[dict[str, Any]], RecordType]): A function that deserializes a record dictionary into a `RecordType` object.
            add_fn (Callable[[RecordType], Response]): A function that attempts to add the deserialized record and returns a `Response`.
            record_name (str): A human-readable name used in error messages (e.g., "student", "assignment").

        Raises:
            - ValueError:
                - If a record dictionary is malformed or fails validation.
            - TypeError:
                - If the input dictionary is not properly structured.
            - RuntimeError:
                - If an internal error occurs during the add operation.
            - Exception:
                - For all other unexpected failures.

        Notes:
            - Designed for internal use by `import_students()`, `import_assignments()`, etc.
            - This method fails fast: if any record fails deserialization or insertion, the import is aborted.
        """
        for record_dict in data:
            try:
                record = from_dict_fn(record_dict)
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Failed to deserialize {record_name}: {record_dict} - {e}"
                )

            response = add_fn(record)

            if not response.success:
                message = (
                    f"Failed to import {record_name}: {record_dict} - {response.detail}"
                )
                match response.error:
                    case ErrorCode.VALIDATION_FAILED:
                        raise ValueError(message)
                    case ErrorCode.INTERNAL_ERROR:
                        raise RuntimeError(message)
                    case _:
                        raise Exception(message)

    def import_students(self, student_data: list) -> None:
        """
        Imports a list of student records into the gradebook.

        Args:
            student_data (list[dict[str, Any]]): A list of dictionaries, each representing serialized `Student` objects.

        Raises:
            - ValueError:
                - If any student dictionary is malformed or missing required fields.
                - If a deserialized student fails uniqueness validation (e.g., duplicate email).

            - TypeError:
                - If any record dictionary has incorrect structure during deserialization.

            - RuntimeError:
                - If unexpected errors occur during `add_student()`.

        Notes:
            - This method fails fast: if any record fails to deserialize or insert, the entire import is aborted.
            - Designed for internal use during gradebook loading.
        """
        self._import_records(
            data=student_data,
            from_dict_fn=Student.from_dict,
            add_fn=self.add_student,
            record_name="student",
        )

    def import_categories(self, category_data: list) -> None:
        """
        Imports a list of category records into the gradebook.

        Args:
            category_data (list[dict[str, Any]]): A list of dictionaries, each representing serialized `Category` objects.

        Raises:
            - ValueError:
                - If any category dictionary is malformed or missing required fields.
                - If a deserialized category fails uniqueness validation (e.g., duplicate name).

            - TypeError:
                - If the input structure is incorrect (e.g., not a list of dictionaries).

            - RuntimeError:
                - If unexpected errors occur during `add_category()`.

        Notes:
            - This method fails fast: if any `Category` object is invalid, the entire import is aborted.
            - Designed for internal use during gradebook loading.
        """
        self._import_records(
            data=category_data,
            from_dict_fn=Category.from_dict,
            add_fn=self.add_category,
            record_name="category",
        )

    def import_assignments(self, assignment_data: list) -> None:
        """
        Imports a list of assignment records into the gradebook.

        Args:
            assignment_data (list[dict[str, Any]]): A list of dictionaries, each representing serialized `Assignment` objects.

        Raises:
            - ValueError:
                - If any assignment dictionary is malformed or missing required fields.
                - If a deserialized assignment fails uniqueness validation (e.g., duplicate name).

            - TypeError:
                - If the input structure is incorrect (e.g., not a list of dictionaries).

            - RuntimeError:
                - If unexpected errors occur during `add_assignment()`.

        Notes:
            - This method fails fast: if any `Assignment` object is invalid, the entire import is aborted.
            - Designed for internal use during gradebook loading.
        """
        self._import_records(
            data=assignment_data,
            from_dict_fn=Assignment.from_dict,
            add_fn=self.add_assignment,
            record_name="assignment",
        )

    def import_submissions(self, submission_data: list) -> None:
        """
        Imports a list of submission records into the gradebook.

        Args:
            submission_data (list[dict[str, Any]]): A list of dictionaries, each representing serialized `Submissions` objects.

        Raises:
            - ValueError:
                - If any submission dictionary is malformed or missing required fields.
                - If a deserialized submission fails uniqueness validation (e.g. linked assignment and student ids).

            - TypeError:
                - If the input structure is incorrect (e.g., not a list of dictionaries).

            - RuntimeError:
                - If unexpected errors occur during `add_submission()`.

        Notes:
            - This method fails fast: if any `Submission` object is invalid, the entire import is aborted.
            - Designed for internal use during gradebook loading.
        """
        self._import_records(
            data=submission_data,
            from_dict_fn=Submission.from_dict,
            add_fn=self.add_submission,
            record_name="submission",
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
                - success (bool):
                    - True if both linked records were retrieved.
                    - False if a linked record is not found.
                - detail (str | None):
                    - On failure, human-readable explanation of the error.
                    - On success, None.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if a linked record is not found.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 404 if either record not found
                    - 400 for other failures (e.g., unexpected errors)
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

    def submission_already_exists(self, assignment_id: str, student_id: str) -> bool:
        return any(
            (s.assignment_id == assignment_id and s.student_id == student_id)
            for s in self.submissions.values()
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
            - The return data dictionary always uses a named key ("attendance") to support consistent response unpacking and future extensibility.
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

    def get_total_absences_for_student(self, student: Student) -> Response:
        """
        Tallies the number of unexcused absences for the given student across all scheduled class dates.

        Args:
            student (Student): The student for whom the absence summary is generated.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the total absences was calculated successfully.
                    - False if the student is not in the roster.
                - detail (str | None):
                    - On failure, a human-readable description of the problem.
                    - On success, None.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if the student is not found.
                - status_code (int | None):
                    - 200 on success
                    - 404 if the student is not found
                - data (dict | None):
                    - On success:
                        - "total_absences" (int): The number of dates where the student has an `AttendanceStatus` of `ABSENT`. Excused absences are not included in the total.
                    - On failure:
                        - None

        Notes:
            - This method is read-only and does not raise.
            - The method returns a total number of absences, but does not indicate on which dates the student was absent.
        """
        if student.id not in self.students:
            return Response.fail(
                detail=f"The selected student is not in the class roster: {student.full_name}.",
                error=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        total_absences = sum(
            1 for date in self.class_dates if student.was_absent_on(date)
        )

        return Response.succeed(
            data={
                "total_absences": total_absences,
            },
        )

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
                - success (bool):
                    - True if the record was found.
                    - False if no match is found or the lookup failed.
                - detail (str | None):
                    - On failure, a human-readable explanation of the problem.
                    - On success, None.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if no match is found.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 404 if not found
                    - 400 for other failures (e.g., unexpected errors)
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

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            return Response.succeed(
                data={
                    "record": record,
                },
            )

    def find_student_by_uuid(self, uuid: str) -> Response:
        """
        Finds a `Student` object by UUID within `gradebook.students`.

        Args:
            uuid (str): The unique ID of the `Student` object.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the `Student` object was found.
                    - False if no match is found or the lookup failed.
                - detail (str | None):
                    - On failure, a human-readable explanation of the problem.
                    - On success, None.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if no match is found.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 404 if no match is found
                    - 400 for other failures (e.g., unexpected errors)
                - data (dict): Payload with the following keys:
                    - On success:
                        - "record" (Student): The matched `Student` object. Included only if found.
                    - On failure:
                        - None

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
                - success (bool):
                    - True if the `Category` object was found.
                    - False if no match is found or the lookup failed.
                - detail (str | None):
                    - On failure, a human-readable explanation of the problem.
                    - On success, None.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if no match is found.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 404 if no match is found
                    - 400 for other failures (e.g., unexpected errors)
                - data (dict): Payload with the following keys:
                    - On success:
                        - "record" (Category): The matched `Category` object. Included only if found.
                    - On failure:
                        - None
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
                - success (bool):
                    - True if the `Assignment` object was found.
                    - False if no match is found or the lookup failed.
                - detail (str | None):
                    - On failure, a human-readable explanation of the problem.
                    - On success, None.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if no match is found.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 404 if no match is found
                    - 400 for other failures (e.g., unexpected errors)
                - data (dict): Payload with the following keys:
                    - On success:
                        - "record" (Assignment): The matched `Assignment` object. Included only if found.
                    - On failure:
                        - None

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
                - success (bool):
                    - True if the `Submission` object was found.
                    - False if no match is found or the lookup failed.
                - detail (str | None):
                    - On failure, a human-readable explanation of the problem.
                    - On success, None.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if no match is found.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 404 if no match is found
                    - 400 for other failures (e.g., unexpected errors)
                - data (dict): Payload with the following keys:
                    - On success:
                        - "record" (Submission): The matched `Submission` object. Included only if found.
                    - On failure:
                        - None

        Notes:
            - This method is read-only and does not raise.
            - The "record" key is only included in the response on success.
            - The caller is responsible for extracting and casting the `Submission` object from `response.data["record"]`.
        """
        return self.find_record_by_uuid(uuid, self.submissions)

    def find_submission_by_assignment_and_student(
        self, assignment_id: str, student_id: str
    ) -> Response:
        """
        Finds a `Submission` object matching a given assignment id and student id.

        Args:
            assignment_id (str): The unique ID of an `Assignment` object.
            student_id (str): The unique ID of a `Student` object.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if a matching `Submission` was found.
                    - False if no match is found.
                - detail (str | None):
                    - On failure, a human-readable explanation of the problem.
                    - On success, None.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if no matching record is found.
                - status_code (int | None):
                    - 200 on success
                    - 404 if no match is found
                - data (dict): Payload with the following keys:
                    - On success:
                        - "record" (Submission): The matched `Submission` object.
                    - On failure:
                        - None

        Notes:
            - This method is read-only and does not raise.
            - The "submission" key is only included in the response on success.
            - The caller is responsible for extracting and casting the `Submission` object from `response.data["submission"]`.
        """
        for submission in self.submissions.values():
            if (
                submission.assignment_id == assignment_id
                and submission.student_id == student_id
            ):
                return Response.succeed(
                    data={
                        "record": submission,
                    },
                )

        return Response.fail(
            detail=f"No matching submission could be found: assignment id {assignment_id}, student id {student_id}.",
            error=ErrorCode.NOT_FOUND,
            status_code=404,
        )

    # --- find record by query ---

    def find_student_by_query(self, query: str) -> Response:
        """
        Generates a list of `Student` objects whose name or email contains the search query.

        Args:
            query (str): A search key to compare against student names and emails.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if at least one matching `Student` was found.
                    - False if no matches were found.
                - detail (str | None):
                    - On failure, a human-readable explanation of the problem.
                    - On success, None.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if no matching record is found.
                - status_code (int | None):
                    - 200 on success
                    - 404 if no match is found
                - data (dict): Payload with the following keys:
                    - On success:
                        - "records" (list[Student]): Students whose full name or email contains the search query.
                    - On failure:
                        - None.

        Notes:
            - This method is read-only and does not raise.
            - The search query is normalized (leading and trailing whitespace stripped and lowercase) before searching.
        """
        query = self._normalize(query)

        matching_students = [
            student
            for student in self.students.values()
            if query in student.full_name.lower() or query in student.email.lower()
        ]

        if not matching_students:
            return Response.fail(
                detail=f"No students found with names or emails matching '{query}'.",
                error=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        return Response.succeed(
            data={
                "records": matching_students,
            },
        )

    def find_category_by_query(self, query: str) -> Response:
        """
        Generates a list of `Category` objects whose name contains the search query.

        Args:
            query (str): A search key to compare against category names.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if at least one matching `Category` was found.
                    - False if no matches were found.
                - detail (str | None):
                    - On failure, a human-readable explanation of the problem.
                    - On success, None.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if no matching record is found.
                - status_code (int | None):
                    - 200 on success
                    - 404 if no match is found
                - data (dict): Payload with the following keys:
                    - On success:
                        - "records" (list[Category]): Categories whose name contains the search query.
                    - On failure:
                        - None

        Notes:
            - This method is read-only and does not raise.
            - The search query is normalized (lowercased, stripped of leading/trailing whitespace) before searching.
        """
        query = self._normalize(query)

        matching_categories = [
            category
            for category in self.categories.values()
            if query in category.name.lower()
        ]

        if not matching_categories:
            return Response.fail(
                detail=f"No categories found with names matching '{query}'.",
                error=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        return Response.succeed(
            data={
                "records": matching_categories,
            },
        )

    def find_assignment_by_query(self, query: str) -> Response:
        """
        Generates a list of `Assignment` objects whose name contains the search query.

        Args:
            query (str): A search key to compare against assignment names.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if at least one matching `Assignment` was found.
                    - False if no matches were found.
                - detail (str | None):
                    - On failure, a human-readable explanation of the problem.
                    - On success, None.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if no matching record is found.
                - status_code (int | None):
                    - 200 on success
                    - 404 if no match is found
                - data (dict): Payload with the following keys:
                    - On success:
                        - "records" (list[Assignment]): Assignments whose name contains the search query.
                    - On failure:
                        - None

        Notes:
            - This method is read-only and does not raise.
            - The search query is normalized (lowercased, stripped of leading/trailing whitespace) before searching.
        """
        query = self._normalize(query)

        matching_assignments = [
            assignment
            for assignment in self.assignments.values()
            if query in assignment.name.lower()
        ]

        if not matching_assignments:
            return Response.fail(
                detail=f"No assignments found with names matching '{query}'.",
                error=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        return Response.succeed(
            data={
                "records": matching_assignments,
            },
        )

    # === data manipulators ===

    def _mark_dirty(self) -> None:
        """
        Marks the gradebook as having unsaved changes.
        """
        self._unsaved_changes = True

    def _mark_dirty_if_tracked(self, record: RecordType) -> None:
        """
        Marks the gradebook dirty if the provided record is currently tracked.

        Args:
            record (RecordType): A possibly untracked object that was mutated.
        """
        if record.id in self._get_tracking_dict(record):
            self._mark_dirty()

    def _get_tracking_dict(self, record: RecordType) -> dict[str, RecordType]:
        """
        Return the internal tracking dictionary corresponding to the given record type.

        Args:
            record (RecordType): The object being checked.

        Returns:
            dict[str, RecordType]: The dictionary (e.g., `self.students`, `self.assignments`) that tracks the given record type.

        Raises:
            TypeError: If the record type is not recognized.
        """
        try:
            attr_name = self._tracking_maps[type(record)]

            return getattr(self, attr_name)

        except KeyError:
            raise TypeError(f"Unrecognized record type: {type(record)}")

    # --- generalized record operations ---

    def _add_record(self, record: RecordType, dictionary: dict) -> Response:
        """
        Adds a `RecordType` object to a given `Gradebook` attribute dictionary.

        Args:
            record (RecordType): The object to be added to the gradebook.
            dictionary (dict): The dictionary in which to store the record.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the object was successfully added.
                    - False if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message.
                - error (ErrorCode | str | None):
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors
                - status_code (int | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None): Payload with the following keys:
                    - On success:
                        - "record" (RecordType): The successfully added record.
                    - On failure:
                        - None

        Notes:
            - This method mutates `Gradebook` state and does not call `_mark_dirty()`; callers must handle that manually.
            - This method is private and should only be called by `Gradebook`-level wrappers.
        """
        try:
            dictionary[record.id] = record

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            return Response.succeed(
                detail="Record successfully added to dictionary.",
                data={
                    "record": record,
                },
            )

    def _remove_record(self, record: RecordType, dictionary: dict) -> Response:
        """
        Removes a `RecordType` object from a given `Gradebook` attribute dictionary.

        Args:
            record (RecordType): The object to be removed from the gradebook.
            dictionary (dict): The dictionary from which to remove the record.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the object was successfully removed.
                    - False if the record cannot be found in the dictionary or if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if the record cannot be found in the dictionary.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int |None):
                    - 200 on success
                    - 404 if the record cannot be found
                    - 400 for other failures (e.g., unexpected errors)
                - data (dict | None):
                    - Always None, this method does not return any payload.

        Notes:
            - This method mutates `Gradebook` state and does not call `_mark_dirty()`; callers must handle that manually.
            - This method is private and should only be called by `Gradebook`-level wrappers.
        """
        try:
            del dictionary[record.id]

        except KeyError:
            return Response.fail(
                detail=f"No matching record could be found for deletion: {record}.",
                error=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            return Response.succeed(
                detail="Record successfully removed from the gradebook.",
            )

    # --- student manipulation ---

    def add_student(self, student: Student) -> Response:
        """
        Adds a `Student` object to the `gradebook.students` dictionary.

        Args:
            student (Student): The `Student` object to be added to the gradebook.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the `Student` object was successfully added.
                    - False if another student with the same email already exists in the gradebook or if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message.
                - error (ErrorCode | str | None):
                    - `ErrorCode.VALIDATION_FAILED` if the email is not unique.
                    - `ErrorCode.INTERNAL_ERROR` if `_add_record()` fails or for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None): Payload with the following keys:
                    - On success:
                        - "record" (Student): The added `Student` object.
                    - On failure:
                        - None

        Notes:
            - This method mutates `Gradebook` state and calls `_mark_dirty()` if successful.
        """
        try:
            self.require_unique_student_email(student.email)

            add_response = self._add_record(student, self.students)

            if not add_response.success:
                return Response.fail(
                    detail=f"Failed to add student: {add_response.detail}",
                    error=add_response.error,
                    status_code=add_response.status_code,
                )

        except ValueError as e:
            return Response.fail(
                detail=f"Unique record validation failed: {e}",
                error=ErrorCode.VALIDATION_FAILED,
            )

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty()

            return Response.succeed(
                detail="Student successfully added to the gradebook.",
                data=add_response.data,
            )

    def remove_student(self, student: Student) -> Response:
        """
        Removes a `Student` object and all linked `Submission` objects from the gradebook.

        Args:
            student (Student): The `Student` object to be removed from the gradebook.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the `Student` object and all linked `Submission` objects were successfully removed.
                    - False if the student cannot be found, if any linked submissions cannot be removed, or if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if the student or any submission cannot be found in the gradebook.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 404 if a record cannot be found
                    - 400 for other failures (e.g., unexpected errors)
                - data (dict | None):
                    - Always None, this method does not return any payload.
        Notes:
            - This method mutates `Gradebook` state by removing the specified student and all their associated submissions.
            - Linked submissions are removed first to maintain referential integrity.
            - If any submission cannot be removed, the operation is aborted and the student remains in the gradebook.
            - This method calls `_mark_dirty()` if and only if the operation succeeds.
        """
        try:
            submissions_response = self.get_records(
                self.submissions, lambda x: x.student_id == student.id
            )

            if not submissions_response.success:
                return Response.fail(
                    detail=f"Could not populate the list of linked submissions: {submissions_response.detail}",
                    error=submissions_response.error,
                    status_code=submissions_response.status_code,
                )

            linked_submissions = submissions_response.data["records"]

            for submission in linked_submissions:
                remove_response = self.remove_submission(submission)

                if not remove_response.success:
                    return remove_response

            remove_response = self._remove_record(student, self.students)

            if not remove_response.success:
                return Response.fail(
                    detail=f"Failed to remove student: {remove_response.detail}",
                    error=remove_response.error,
                    status_code=remove_response.status_code,
                )

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty()

            return Response.succeed(
                detail="Student successfully removed from the gradebook."
            )

    def update_student_first_name(self, student: Student, first_name: str) -> Response:
        """
        Updates the `first_name` attribute of a given `Student` object.

        Args:
            student (Student): The student whose attribute is updated.
            first_name (str): The new first name to be assigned.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the first name attribute was successfully updated or no-op.
                    - False if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message with the updated value.
                - error (ErrorCode | str | None):
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None):
                    - On success:
                        - "record" (Student): The updated `Student` object.
                    - On failure:
                        - None

        Notes:
            - This method mutates `Gradebook` state and calls `_mark_dirty_if_tracked()` if successful.
            - If the input first_name matches the current value, the method returns early with a success response indicating no changes were made.
        """
        if student.first_name == first_name:
            return Response.succeed(
                detail="The first name provided matches the current one. No changes made.",
                data={
                    "record": student,
                },
            )

        try:
            student.first_name = first_name

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty_if_tracked(student)

            return Response.succeed(
                detail=f"Student name successfully updated to: {student.full_name}.",
                data={
                    "record": student,
                },
            )

    def update_student_last_name(self, student: Student, last_name: str) -> Response:
        """
        Updates the `last_name` attribute of a given `Student` object.

        Args:
            student (Student): The student whose attribute is updated.
            last_name (str): The new last name to be assigned.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the last name attribute was successfully updated or no-op.
                    - False if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message with the updated value.
                - error (ErrorCode | str | None):
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None):
                    - On success:
                        - "record" (Student): The updated `Student` object.
                    - On failure:
                        - None

        Notes:
            - This method mutates `Gradebook` state and calls `_mark_dirty_if_tracked()` if successful.
            - If the input last_name matches the current value, the method returns early with a success response indicating no changes were made.
        """
        if student.last_name == last_name:
            return Response.succeed(
                detail="The last name provided matches the current one. No changes made.",
                data={
                    "record": student,
                },
            )

        try:
            student.last_name = last_name

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty_if_tracked(student)

            return Response.succeed(
                detail=f"Student name successfully updated to: {student.full_name}.",
                data={
                    "record": student,
                },
            )

    def update_student_email(self, student: Student, email: str) -> Response:
        """
        Updates the `email` attribute of a given `Student` object, enforcing uniqueness and normalization.

        Args:
            student (Student): The student whose attribute is updated.
            email (str): The new email to be assigned.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the email attribute was successfully updated or no-op.
                    - False if validation fails or if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message with the updated value.
                - error (ErrorCode | str | None):
                    - `ErrorCode.VALIDATION_FAILED` if another record exists with the same email.
                    - `ErrorCode.INVALID_FIELD_VALUE` if the input is malformed.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None);
                    - 200 on success
                    - 400 on failure
                - data (dict | None):
                    - On success:
                        - "record" (Student): The updated `Student` object.
                    - On failure:
                        - None

        Notes:
            - This method mutates `Gradebook` state and calls `_mark_dirty_if_tracked()` if successful.
            - If the normalized input email matches the current value, the method returns early with a success response indicating no changes were made.
        """
        if self._normalize(student.email) == self._normalize(email):
            return Response.succeed(
                detail="The email address provided matches the current one. No changes made.",
                data={
                    "record": student,
                },
            )

        try:
            self.require_unique_student_email(email)

        except ValueError as e:
            return Response.fail(
                detail=f"Unique record validation failed: {e}",
                error=ErrorCode.VALIDATION_FAILED,
            )

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        try:
            student.email = email

        except ValueError as e:
            return Response.fail(
                detail=f"Input validation failed: {e}",
                error=ErrorCode.INVALID_FIELD_VALUE,
            )

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty_if_tracked(student)

            return Response.succeed(
                detail=f"Student email successfully updated to: {student.email}.",
                data={
                    "record": student,
                },
            )

    def toggle_student_active_status(self, student: Student) -> Response:
        """
        Toggles the `is_active` attribute of a given `Student` object.

        Args:
            student (Student): The student whose attribute is updated.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the active status was successfully toggled.
                    - False if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message reflecting the new status.
                - error (ErrorCode | str | None):
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None):
                    - On success:
                        - "record" (Student): The updated `Student` object.
                    - On failure:
                        - None

        Notes:
            - This method mutates `Gradebook` state and calls `_mark_dirty_if_tracked()` if successful.
        """
        try:
            student.toggle_archived_status()

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty_if_tracked(student)

            return Response.succeed(
                detail=f"Student status successfully updated to: {student.status}.",
                data={
                    "record": student,
                },
            )

    # --- category manipulation ---

    def add_category(self, category: Category) -> Response:
        """
        Adds a `Category` object to the `gradebook.categories` dictionary.

        Args:
            category (Category): The `Category` object to be added to the gradebook.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the `Category` object was successfully added.
                    - False if another category with the same name already exists in the gradebook or if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message.
                - error (ErrorCode | str | None):
                    - `ErrorCode.VALIDATION_FAILED` if the name is not unique.
                    - `ErrorCode.INTERNAL_ERROR` if `_add_record()` fails or for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None): Payload with the following keys:
                    - On success:
                        - "record" (Category): The added `Category` object.
                    - On failure:
                        - None

        Notes:
            - This method mutates `Gradebook` state and calls `_mark_dirty()` if successful.
        """
        try:
            self.require_unique_category_name(category.name)

            add_response = self._add_record(category, self.categories)

            if not add_response.success:
                return Response.fail(
                    detail=f"Failed to add category: {add_response.detail}",
                    error=add_response.error,
                    status_code=add_response.status_code,
                )

        except ValueError as e:
            return Response.fail(
                detail=f"Unique record validation failed: {e}",
                error=ErrorCode.VALIDATION_FAILED,
            )

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty()

            return Response.succeed(
                detail="Category successfully added to the gradebook.",
                data=add_response.data,
            )

    def remove_category(self, category: Category) -> Response:
        """
        Removes a `Category` object and all linked `Assignment` objects from the gradebook.

        Args:
            category (Category): The `Category` object to be removed from the gradebook.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the `Category` object and all linked `Assignment` objects were successfully removed.
                    - False if the category cannot be found, if any linked assignments cannot be removed, or if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if the category or any assignment cannot be found in the gradebook.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 404 if a record cannot be found
                    - 400 for other failures (e.g., unexpected errors)
                - data (dict | None):
                    - Always None, this method does not return any payload.

        Notes:
            - This method mutates `Gradebook` state by removing the specified category and all its associated assignments.
            - Linked assignments are removed first to maintain referential integrity.
            - In any linked assignment cannot be removed, the operation is aborted and the category remains in the gradebook.
            - This method calls `_mark_dirty()` if and only if the operation succeeds.
        """
        try:
            assignments_response = self.get_records(
                self.assignments, lambda x: x.category_id == category.id
            )

            if not assignments_response.success:
                return Response.fail(
                    detail=f"Could not populate the list of linked assignments: {assignments_response.detail}",
                    error=assignments_response.error,
                    status_code=assignments_response.status_code,
                )

            linked_assignments = assignments_response.data["records"]

            for assignment in linked_assignments:
                remove_response = self.remove_assignment(assignment)

                if not remove_response.success:
                    return remove_response

            remove_response = self._remove_record(category, self.categories)

            if not remove_response.success:
                return Response.fail(
                    detail=f"Failed to remove category: {remove_response.detail}",
                    error=remove_response.error,
                    status_code=remove_response.status_code,
                )

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty()

            return Response.succeed(
                detail="Category successfully removed from the gradebook."
            )

    def update_category_name(self, category: Category, name: str) -> Response:
        """
        Updates the `name` attribute of a given `Category` object.

        Args:
            category (Category): The category whose attribute is updated.
            name (str): The new name to be assigned.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the name attribute was successfully updated or no-op.
                    - False if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message with the updated value.
                - error (ErrorCode | str | None):
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None):
                    - On success:
                        - "record" (Category): The updated `Category` object.
                    - On failure:
                        - None

        Notes:
            - This method mutates `Gradebook` stats and calls `_mark_dirty_if_tracked()` if successful.
            - If the input name matches the current value, the method returns early with a success response indicating no changes were made.
        """
        if category.name == name:
            return Response.succeed(
                detail="The name provided matches the current one. No changes made.",
                data={
                    "record": category,
                },
            )

        try:
            category.name = name

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty_if_tracked(category)

            return Response.succeed(
                detail=f"Category name successfully updated to: {category.name}.",
                data={
                    "record": category,
                },
            )

    def toggle_category_active_status(self, category: Category) -> Response:
        """
        Toggles the `is_active` attribute of a given `Category` object.

        Args:
            category (Category): The category whose attribute is updated.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the active status was successfully toggled.
                    - False if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message reflecting the new status.
                - error (ErrorCode | str | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None):
                    - On success:
                        - "record" (Category): The updated `Category` object.
                    - On failure:
                        - None

        Notes:
            - This method mutates `Gradebook` state and calls `_mark_dirty_if_tracked()` if successful.
        """
        try:
            category.toggle_archived_status()

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty_if_tracked(category)

            return Response.succeed(
                detail=f"Category status successfully updated to: {category.status}.",
                data={
                    "record": category,
                },
            )

    def update_category_weight(
        self, category: Category, weight: float | str | None
    ) -> Response:
        """
        Updates the `weight` attribute of a given `Category` object.

        Args:
            category (Category): The category whose attribute is updated.
            weight (float | None): The new weight value to be assigned.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the weight attribute was successfully updated or no-op.
                    - False if the new weight value is invalid or if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message with the updated value.
                - error (ErrorCode | str | None):
                    - `ErrorCode.INVALID_FIELD_VALUE` if weight validation fails.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 400 on failed weight validation or logic errors
                - data (dict | None): Payload with the following keys:
                    - On success:
                        - "record" (Category): The updated `Category` object.
                    - On failure:
                        - None

        Notes:
            - This method mutates `Gradebook` state and calls `_mark_dirty_if_tracked()` if successful.
            - The `weight` value must be a finite float between 0 and 100 (inclusive), or None for unweighted. Validation failures raise `TypeError` or `ValueError`.
            - If the input weight matches the current value, the method returns early with a success response indicating no changes were made.
        """
        if category.weight == weight:
            return Response.succeed(
                detail="The weight provided matches the current one. No changes made.",
                data={
                    "record": category,
                },
            )

        try:
            category.weight = weight

        except (TypeError, ValueError) as e:
            return Response.fail(
                detail=f"Weight validation failed: {e}",
                error=ErrorCode.INVALID_FIELD_VALUE,
            )

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty_if_tracked(category)

            return Response.succeed(
                detail=f"Category weight successfully updated to: {category.weight if category.weight is not None else '[UNWEIGHTED]'}.",
                data={
                    "record": category,
                },
            )

    # --- assignment manipulation ---

    def add_assignment(self, assignment: Assignment) -> Response:
        """
        Adds an `Assignment` object to the `gradebook.assignments` dictionary.

        Args:
            assignment (Assignment): The `Assignment` object to be added to the gradebook.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the `Assignment` object was successfully added.
                    - False if another assignment with the same name already exists in the gradebook.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message.
                - error (ErrorCode | str | None):
                    - `ErrorCode.VALIDATION_FAILED` if the name is not unique.
                    - `ErrorCode.INTERNAL_ERROR` if `_add_record()` fails or for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None): Payload with the following keys:
                    - On success:
                        - "record" (Assignment): The added `Assignment` object.
                    - On failure:
                        - None

        Notes:
            - This method mutates `Gradebook` state and calls `_mark_dirty()` if successful.
        """
        try:
            self.require_unique_assignment_name(assignment.name)

            add_response = self._add_record(assignment, self.assignments)

            if not add_response.success:
                return Response.fail(
                    detail=f"Failed to add assignment: {add_response.detail}",
                    error=add_response.error,
                    status_code=add_response.status_code,
                )

        except ValueError as e:
            return Response.fail(
                detail=f"Unique record validation failed: {e}",
                error=ErrorCode.VALIDATION_FAILED,
            )

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected response: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty()

            return Response.succeed(
                detail="Assignment successfully added to the gradebook.",
                data=add_response.data,
            )

    def remove_assignment(self, assignment: Assignment) -> Response:
        """
        Removes an `Assignment` object and all linked `Submission` objects from the gradebook.

        Args:
            assignment (Assignment): The `Assignment` object to be removed from the gradebook.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the `Assignment` object and all linked `Submission` objects were successfully removed.
                    - False if the assignment cannot be found, if any linked submissions cannot be removed, or if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if the assignment or any submission cannot be found in the gradebook.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 404 if a record cannot be found
                    - 400 for other failures (e.g., unexpected errors)
                - data (dict | None):
                    - Always None, this method does not return any payload.
        Notes:
            - This method mutates `Gradebook` state by removing the specified assignment and all its associated submissions.
            - Linked submissions are removed first to maintain referential integrity.
            - If any linked submission cannot be removed, the operation is aborted and the assignment remains in the gradebook.
            - This method calls `_mark_dirty()` if and only if the operation succeeds.
        """
        try:
            submissions_response = self.get_records(
                self.submissions, lambda x: x.assignment_id == assignment.id
            )

            if not submissions_response.success:
                return Response.fail(
                    detail=f"Could not populate the list of linked submissions: {submissions_response.detail}",
                    error=submissions_response.error,
                    status_code=submissions_response.status_code,
                )

            linked_submissions = submissions_response.data["records"]

            for submission in linked_submissions:
                remove_response = self.remove_submission(submission)

                if not remove_response.success:
                    return remove_response

            remove_response = self._remove_record(assignment, self.assignments)

            if not remove_response.success:
                return Response.fail(
                    detail=f"Failed to remove assignment: {remove_response.detail}",
                    error=remove_response.error,
                    status_code=remove_response.status_code,
                )

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty()

            return Response.succeed(
                detail="Assignment successfully removed from the gradebook."
            )

    def update_assignment_name(self, assignment: Assignment, name: str) -> Response:
        """
        Updates the `name` attribute of a given `Assignment` object.

        Args:
            assignment (Assignment): The assignment whose attribute is updated.
            name (str): The new name to be assigned.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the name attribute was successfully updated or no-op.
                    - False if validation fails or unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message with the updated value.
                - error (ErrorCode | str | None):
                    - `ErrorCode.VALIDATION_FAILED` if another category with the same name already exists.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None):
                    - On success:
                        - "record" (Assignment): The updated `Assignment` object.
                    - On failure:
                        - None

        Notes:
            - This method mutates `Gradebook` state and calls `_mark_dirty_if_tracked()` if successful.
            - If the input name matches the current value, the method returns early with a success response indicating no changes were made.
        """
        if assignment.name == name:
            return Response.succeed(
                detail="The name provided matches the current one. No changes made.",
                data={
                    "record": assignment,
                },
            )

        try:
            self.require_unique_assignment_name(name)

            assignment.name = name

        except ValueError as e:
            return Response.fail(
                detail=f"Name validation failed: {e}",
                error=ErrorCode.VALIDATION_FAILED,
            )

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty_if_tracked(assignment)

            return Response.succeed(
                detail=f"Assignment name successfully updated to: {assignment.name}.",
                data={
                    "record": assignment,
                },
            )

    def update_assignment_linked_category(
        self, assignment: Assignment, category: Category | None
    ) -> Response:
        """
        Updates the `category_id` attribute of a given `Assignment` object.

        Args:
            assignment (Assignment): The assignment whose attribute is updated.
            category (Category | None): The new category whose id is to be assigned, or None if the assignment is being marked 'uncategorized.'

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the name attribute was successfully updated or no-op.
                    - False if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confrimation message with the updated value.
                - error (ErrorCode | str | None):
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None):
                    - On success:
                        "record" (Assignment): The updated `Assignment` object.
                    - On failure:
                        - None

        Notes:
            - This method mutates `Gradebook` state and calls `_mark_dirty_if_tracked()` if successful.
            - If the input category matches the currently linked category, the method returns early with a success response indicating no changes were made.
        """
        category_id = category.id if category else None

        if assignment.category_id == category_id:
            return Response.succeed(
                detail="The category provided matches the current linked category. No changes made.",
                data={
                    "record": assignment,
                },
            )

        try:
            assignment.category_id = category_id

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty_if_tracked(assignment)

            return Response.succeed(
                detail=f"Assignment linked category successfully updated to: {category.name if category else '[UNCATEGORIZED]'}.",
                data={
                    "record": assignment,
                },
            )

    def update_assignment_due_date(
        self, assignment: Assignment, due_date_dt: datetime.datetime | None
    ) -> Response:
        """
        Updates the `due_date_dt` attribute of a given `Assignment` object.

        Args:
            assignment (Assignment): The assignment whose attribute is updated.
            due_date_dt (datetime.datetime | None): The new due date to be assigned, or None if the the assignment has no due date.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the due_date_dt attribute was successfully updated or no-op.
                    - False if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message with the updated value.
                - error (ErrorCode | str | None):
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None):
                    - On success:
                        - "record" (Assignment): The updated `Assignment` object.
                    - On failure:
                        - None

        Notes:
            - This method mutates `Gradebook` state and call `_mark_dirty_if_tracked()` if successful.
            - If the input due date matches the current due date, the method returns early with a success response indicating no changes were made.
        """
        if assignment.due_date_dt == due_date_dt:
            return Response.succeed(
                detail="The due date provided matches the current due date. No changes made.",
                data={
                    "record": assignment,
                },
            )

        try:
            assignment.due_date_dt = due_date_dt

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty_if_tracked(assignment)

            return Response.succeed(
                detail=f"Assignment due date successfully updated to: {formatters.format_due_date_from_datetime(assignment.due_date_dt)}.",
                data={
                    "record": assignment,
                },
            )

    def update_assignment_points_possible(
        self, assignment: Assignment, points_possible: float
    ) -> Response:
        """
        Updates the `point_possible` attribute of a given `Assignment` object.

        Args:
            assignment (Assignment): The assignment whose attribute is updated.
            points_possilble (float): The new points_possible value to be assigned.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the points_possible value was successfully updated or no-op.
                    - False if validation fails or if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message with the updated value.
                - error (ErrorCode | str | None):
                    - `ErrorCode.INVALID_FIELD_VALUE` if the input fails to pass validation.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None):
                    - On success:
                        - "record" (Assignment): The updated `Assignment` object.
                    - On failure:
                        - None

        Notes:
            - This method mutates `Gradebook` state and calls `_mark_dirty_if_tracked()` if successful.
            - If the points_possible input value matches the current value, the method returns early with a success response indicating no changes were made.
        """
        if assignment.points_possible == points_possible:
            return Response.succeed(
                detail="The points possible value provided matches the current points possible. No changes made.",
                data={
                    "record": assignment,
                },
            )

        try:
            assignment.points_possible = points_possible

        except (TypeError, ValueError) as e:
            return Response.fail(
                detail=f"Input validation failed: {e}",
                error=ErrorCode.INVALID_FIELD_VALUE,
            )

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty_if_tracked(assignment)

            return Response.succeed(
                detail=f"Assignment points possible successfully updated to: {assignment.points_possible}.",
                data={
                    "record": assignment,
                },
            )

    def toggle_assignment_active_status(self, assignment: Assignment) -> Response:
        """
        Toggles the `is_active` attribute of a given `Assignment` object.

        Args:
            assignment (Assignment): The assignment whose attribute is updated.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the active status was successfully toggled.
                    - False if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message reflecting the new status.
                - error (ErrorCode | str | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None):
                    - On success:
                        - "record" (Assignment): The updated `Assignment` object.
                    - On failure:
                        - None

        Notes:
            - This method mutates `Gradebook` state and calls `_mark_dirty_if_tracked()` if successful.
        """
        try:
            assignment.toggle_archived_status()

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty_if_tracked(assignment)

            return Response.succeed(
                detail=f"Assignment status successfully updated to: {assignment.status}.",
                data={
                    "record": assignment,
                },
            )

    # --- submission manipulation ---

    def add_submission(self, submission: Submission) -> Response:
        """
        Adds a `Submission` object to the `gradebook.submissions` dictionary.

        Args:
            submission (Submission): The `Submission` object to be added to the gradebook.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the `Submission` object was successfully added.
                    - False if another submission with the same linked assignment and student already exists in the gradebook.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if either the linked assignment or student cannot be found in the gradebook.
                    - `ErrorCode.VALIDATION_FIELD` if the student/assignment pair is not unique.
                    - `ErrorCode.INTERNAL_ERROR` if `_add_record()` fails or for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 404 if either the linked assignment or student cannot be found
                    - 400 on failure
                - data (dict | None): Payload with the following keys:
                    - On success:
                        - "record" (Submission): The added `Submission` object.
                    - On failure:
                        - None

        Notes:
            - This method mutates `Gradebook` state and calls `_mark_dirty()` if successful.
        """
        assignment_response = self.find_assignment_by_uuid(submission.assignment_id)

        if not assignment_response.success:
            return Response.fail(
                detail=f"Could not resolve assignment for submission: {assignment_response.detail}",
                error=assignment_response.error,
                status_code=assignment_response.status_code,
            )

        assignment = assignment_response.data["record"]

        student_response = self.find_student_by_uuid(submission.student_id)

        if not student_response.success:
            return Response.fail(
                detail=f"Could not resolve student for submission: {student_response.detail}",
                error=student_response.error,
                status_code=student_response.status_code,
            )

        student = student_response.data["record"]

        try:
            self.require_unique_submission(
                submission.assignment_id, submission.student_id
            )

            add_response = self._add_record(submission, self.submissions)

            if not add_response.success:
                return Response.fail(
                    detail=f"Failed to add submission: {add_response.detail}",
                    error=add_response.error,
                    status_code=add_response.status_code,
                )

        except ValueError as e:
            return Response.fail(
                detail=f"Unique record validation failed: {e}",
                error=ErrorCode.VALIDATION_FAILED,
            )

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected response: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty()

            return Response.succeed(
                detail=f"Submission from {student.full_name} to {assignment.name} successfully added to the gradebook.",
                data=add_response.data,
            )

    def batch_add_submissions(self, submissions: list[Submission]) -> Response:
        """
        Add multiples submissions to the gradebook.

        Attemps to add each submission individually with `add_submission()`. Tracks which submissions were successfully added and which were skipped due to validation errors (e.g., duplicates). This method is not transactional; some submissions may be added even if others fail.

        Args:
            submissions (list[Submission]): A list of `Submission` objects to add to the gradebook.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if all submissions were successfully added.
                    - False if one or more submissions could not be added.
                - detail (str | None):
                    - Indication of complete or partial success.
                    - On fast-failure, a human-readable description of the error.
                - error (ErrorCode | str | None):
                    - `ErrorCode.VALIDATION_FAILED` if one or more submissions were skipped due to duplicates or validation issues.
                    - `ErrorCode.INTERNAL_ERROER` if an unexpected error interrupts the batch process.
                - status_code (int | None):
                    - 200 if all submissions were added successfully
                    - 400 on failure
                - data (dict | None):
                    - "added" (list[Submission]): Submissions that were successfully added.
                    - "skipped" (list[Submission]): Submissions that were not added due to validation failure.

        Notes:
            - Each call to `add_submission()` will invoke `_mark_dirty()` if the addition succeeds.
            - This method does not attempt to roll back or rety failed additions.
        """
        added = []
        skipped = []

        try:
            for submission in submissions:
                add_response = self.add_submission(submission)

                if add_response.success:
                    added.append(submission)

                elif add_response.error is ErrorCode.VALIDATION_FAILED:
                    skipped.append(submission)

                else:
                    return add_response

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
                data={
                    "added": added,
                    "skipped": skipped,
                },
            )

        else:
            if len(added) == len(submissions):
                return Response.succeed(
                    detail="All submissions successfully added to the gradebook.",
                    data={
                        "added": added,
                        "skipped": skipped,
                    },
                )

            else:
                return Response.fail(
                    detail="Not all submissions could be successfully added to the gradebook.",
                    error=ErrorCode.VALIDATION_FAILED,
                    data={
                        "added": added,
                        "skipped": skipped,
                    },
                )

    def remove_submission(self, submission: Submission) -> Response:
        """
        Removes a `Submission` object from the `gradebook.submissions` dictionary.

        Args:
            submission (Submission): The `Submission` object to be removed from the gradebook.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the `Submission` object was successfully removed.
                    - False if the submission cannot be found or unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if the submission cannot be found in the gradebook.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 404 if the submission cannot be found
                    - 400 for other failures (e.g., unexpected errors)
                - data (dict | None):
                    - Always None, this method does not return any payload.

        Notes:
            - This method mutates `Gradebook` state and calls `_mark_dirty()` if successful.
        """
        try:
            remove_response = self._remove_record(submission, self.submissions)

            if not remove_response.success:
                return Response.fail(
                    detail=f"Failed to remove submission: {remove_response.detail}",
                    error=remove_response.error,
                    status_code=remove_response.status_code,
                )

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty()

            return Response.succeed(
                detail="Submission successfully removed from the gradebook."
            )

    def update_submission_points_earned(
        self, submission: Submission, points_earned: float
    ) -> Response:
        """
        Updates the `points_earned` attribute of a given `Submission` object.

        Args:
            submission (Submission): The submission whose attribute is updated.
            points_earned (float): The new points_earned value to be assigned.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the points_earned value was successfully updated or no-op.
                    - False if validation fails or if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message with the updated value.
                - error (ErrorCode | str | None):
                    - `ErrorCode.INVALID_FIELD_VALUE` if the input fails to pass validation.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None):
                    - On success:
                        - "record" (Submission): The updated `Submission` object.
                    - On failure:
                        - None

        Notes:
            - This method mutates `Gradebook` state and calls `_mark_dirty_if_tracked()` if successful.
            - If the points_earned input value matches the current value, the method returns early with a success response indicating no changes were made.
        """
        if submission.points_earned == points_earned:
            return Response.succeed(
                detail="The points earned value provided matches the current points earned. No changes made.",
                data={
                    "record": submission,
                },
            )

        try:
            submission.points_earned = points_earned

        except (TypeError, ValueError) as e:
            return Response.fail(
                detail=f"Input validation failed: {e}",
                error=ErrorCode.INVALID_FIELD_VALUE,
            )

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty_if_tracked(submission)

            assignment_response = self.find_assignment_by_uuid(submission.assignment_id)
            assignment = (
                assignment_response.data["record"]
                if assignment_response.success
                else None
            )
            points_possible = f"/ {assignment.points_possible}" if assignment else ""

            return Response.succeed(
                detail=f"Submission points earned successfully updated to: {submission.points_earned}{points_possible}.",
                data={
                    "record": submission,
                },
            )

    def toggle_submission_late_status(self, submission: Submission) -> Response:
        """
        Toggles the `is_late` attribute of a given `Submission` object.

        Args:
            submission (Submission): The submission whose attribute is updated.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the late status was successfully toggled.
                    - False if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message reflecting the new status.
                - error (ErrorCode | str | None):
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None):
                    - On success:
                        - "record" (Submission): The updated `Submission` object.
                    - On failure:
                        - None

        Notes:
            - This method mutates `Gradebook` state and calls `_mark_dirty_if_tracked()` if successful.
        """
        try:
            submission.toggle_late_status()

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty_if_tracked(submission)

            return Response.succeed(
                detail=f"Submission late status sucessfully updated to: {submission.late_status}.",
                data={
                    "record": submission,
                },
            )

    def toggle_submission_exempt_status(self, submission: Submission) -> Response:
        """
        Toggles the `is_exempt` attribute of a given `Submission` object.

        Args:
            submission (Submission): The submission whose attribute is updated.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the exempt status was successfully toggled.
                    - False if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message reflecting the new status.
                - error (ErrorCode | str | None):
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None):
                    - On success:
                        - "record" (Submission): The updated `Submission` object.
                    - On failure:
                        - None

        Notes:
            - This method mutates `Gradebook` state and calls `_mark_dirty_if_tracked()` if successful.
        """
        try:
            submission.toggle_exempt_status()

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty_if_tracked(submission)

            return Response.succeed(
                detail=f"Submission exempt status successfully updated to: {submission.exempt_status}.",
                data={
                    "record": submission,
                },
            )

    # --- category weighting methods ---

    def toggle_is_weighted(self) -> Response:
        """
        Toggles the boolean value of `uses_weighting` in the gradebook metadata.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the weighting status is successfully changed.
                    - False if the weighting status does not change as expected, if category weights cannot reset when disabling weighting, or if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a confirmation message displaying the current weighting status.
                - error (ErrorCode | str | None):
                    - `ErrorCode.INVALID_FIELD_VALUE` if weight validation fails during `reset_category_weights()`
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors
                - status_code (int | None):
                    - 200 on success
                    - 400 on logic or validation failure
                - data (dict | None): Payload with the following keys:
                    - On success:
                        - "uses_weighting" (bool): The state of `uses_weighting` after the operation.
                    - On failure:
                        - None

        Notes:
            - This method mutates `Gradebook` state and calls `_mark_dirty()` if successful.
            - This method does not validate category weights when enabling weighting. Callers are responsible for pre-validating before use.
        """
        try:
            prev_status = self.uses_weighting

            if self.uses_weighting:
                self._metadata["uses_weighting"] = False

                reset_response = self.reset_category_weights()

                if not reset_response.success:
                    return Response.fail(
                        detail=f"Failed to reset category weights: {reset_response.detail}",
                        error=reset_response.error,
                        status_code=reset_response.status_code,
                    )

            else:
                # TODO: supply a require_validated_weights() check

                self._metadata["uses_weighting"] = True

            if prev_status == self.uses_weighting:
                raise RuntimeError("Weighting toggle did not succeed as expected.")

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty()

            return Response.succeed(
                detail=f"Gradebook successfully updated. Weighted categories are now: {self.weighting_status}.",
                data={
                    "uses_weighting": self.uses_weighting,
                },
            )

    def reset_category_weights(self) -> Response:
        """
        Resets the `weight` attribute of all active `Category` objects to None.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if all category weights are reset to None
                    - False if active categories cannot be retrieved, or if any weight fails to reset
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message.
                - error (ErrorCode | str | None):
                    - `ErrorCode.INVALID_FIELD_VALUE` if weight validation fails.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 400 on failed weight validation or logic errors
                - data (dict | None):
                    - Always None. This method performs a batch mutation and does not return additional data.

        Notes:
            - This method mutates `Gradebook` and `Category` states and calls `_mark_dirty()` if successful.
        """
        try:
            categories_response = self.get_records(
                self.categories,
                lambda x: x.is_active,
            )

            if not categories_response.success:
                return Response.fail(
                    detail=f"Could not populate the list of active categories: {categories_response.detail}",
                    error=categories_response.error,
                    status_code=categories_response.status_code,
                )

            active_categories = categories_response.data["records"]

            for category in active_categories:
                response = self.update_category_weight(category, None)

                if not response.success:
                    return Response.fail(
                        detail=f"Could not reset category weight to None: {category.name} - {response.detail}",
                        error=response.error,
                        status_code=response.status_code,
                    )

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty()

            return Response.succeed(
                detail="All active category weights successfully reset to None."
            )

    # --- attendance methods ---

    def add_class_date(self, class_date: datetime.date) -> Response:
        """
        Adds a new date to the `gradebook.class_dates` attribute set.

        Args:
            class_date (datetime.date): The class date to be added to the gradebook.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the date was successfully added.
                    - False if the date already exists in the schedule or if unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message.
                - error (ErrorCode | str | None):
                    - `ErrorCode.VALIDATION_FAILED` if the class date already exists in the schedule.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None): Payload with the following keys:
                    - On success:
                        - "record" (datetime.date): The raw date object as added to the schedule.
                    - On failure:
                        - None
        Notes:
            - This method mutates `Gradebook` state and calls `_mark_dirty()` if successful.
        """
        try:
            self.require_unique_class_date(class_date)

            self.class_dates.add(class_date)

        except ValueError as e:
            return Response.fail(
                detail=f"Unique record validation failed: {e}",
                error=ErrorCode.VALIDATION_FAILED,
            )

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty()

            return Response.succeed(
                detail="Class date successfully added to the gradebook.",
                data={
                    "record": class_date,
                },
            )

    def batch_add_class_dates(self, class_dates: list[datetime.date]) -> Response:
        """
        Adds multiple class dates to the gradebook schedule.

        Attempts to add each date individually using `add_class_date()`. Tracks which dates were successfully added and which were skipped due to validation errors (e.g., duplicates). This method is not transactional; some dates may be added even if others fail.

        Args:
            class_dates (list[datetime.date]): A list of class dates to add to the gradebook.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if all class dates were successfully added.
                    - False if one or more dates could not be added.
                - detail (str | None):
                    - Indication of complete or partial success.
                    - On fast-failure, a human-readable description of the error.
                - error (ErrorCode | str | None):
                    - `ErrorCode.VALIDATION_FAILED` if one or more dates were skipped due to duplicates or validation issues.
                    - `ErrorCode.INTERNAL_ERROR` if an unexpected error interrupts the batch process.
                - status_code (int | None):
                    - 200 if all dates were added successfully
                    - 400 on failure
                - data (dict | None): A payload describing the operation result:
                    - "added" (list[datetime.date]): Dates that were successfully added.
                    - "skipped" (list[datetime.date]): Dates that were not added due to validation failure.

        Notes:
            - Each call to `add_class_date()` will invoke `_mark_dirty()` if the addition succeeds.
            - This method does not attempt to roll back or retry failed additions.
        """
        added = []
        skipped = []

        try:
            for class_date in class_dates:
                add_response = self.add_class_date(class_date)

                if add_response.success:
                    added.append(class_date)

                elif add_response.error is ErrorCode.VALIDATION_FAILED:
                    skipped.append(class_date)

                else:
                    return add_response

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
                data={
                    "added": added,
                    "skipped": skipped,
                },
            )

        else:
            if len(added) == len(class_dates):
                return Response.succeed(
                    detail="All class dates successfully added to the gradebook.",
                    data={
                        "added": added,
                        "skipped": skipped,
                    },
                )

            else:
                return Response.fail(
                    detail="Not all class dates could be sucessfully added to the gradebook.",
                    error=ErrorCode.VALIDATION_FAILED,
                    data={
                        "added": added,
                        "skipped": skipped,
                    },
                )

    def remove_class_date(self, class_date: datetime.date) -> Response:
        """
        Removes a class date from the gradebook schedule and deletes associated attendance records from each student.

        Args:
            class_date (datetime.date): The date of the class session to remove. Must already exist in the gradebook's schedule.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if the class date was successfully removed.
                    - False if it wasn't found or unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message.
                - error (ErrorCode | str | None):
                    - `ErrorCode.NOT_FOUND` if the date is not in `gradebook.class_dates`.
                    - `ErrorCode.INTERNAL_ERROR` for unexpected errors.
                - status_code (int | None):
                    - 200 on success
                    - 404 if the class date does not exist
                    - 400 for other failures (e.g., unexpected errors)
                - data (dict | None):
                    - Always None, this method does not return any payload.

        Notes:
            - This method mutates `Gradebook` and `Student` states, and calls `_mark_dirty()` if successful.
            - Attendance cleanup uses `student.clear_attendance` which does not raise on missing entries.
        """
        try:
            if class_date not in self.class_dates:
                return Response.fail(
                    detail=f"No matching date could be found in the course schedule: {class_date.isoformat()}",
                    error=ErrorCode.NOT_FOUND,
                    status_code=404,
                )

            for student in self.students.values():
                student.clear_attendance(class_date)

            self.class_dates.discard(class_date)

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            self._mark_dirty()

            return Response.succeed(
                detail="Class date and attendance records successfully removed from the gradebook."
            )

    def remove_all_class_dates(self) -> Response:
        """
        Wrapper method to remove all class dates and associated attendance records from each student.

        Returns:
            Response: A structured response with the following contract:
                - success (bool):
                    - True if all class dates were successfully removed or if none were scheduled.
                    - False if any class dates remain after the operation or unexpected errors occur.
                - detail (str | None):
                    - On failure, a human-readable description of the error.
                    - On success, a simple confirmation message.
                - error (ErrorCode | str | None):
                    - `ErrorCode.INTERNAL_ERROR` if `class_dates` wasn't fully cleared
                - status_code (int | None):
                    - 200 on success
                    - 400 on failure
                - data (dict | None):
                    - Always None, this method does not return any payload.

        Notes:
            - Each call to `remove_class_date()` will invoke `_mark_dirty()` if the addition succeeds.
        """
        try:
            if not self.class_dates:
                return Response.succeed(detail="The course schedule is already empty.")

            for class_date in list(self.class_dates):
                self.remove_class_date(class_date)

            if len(self.class_dates) != 0:
                return Response.fail(
                    detail="Failed to clear all class dates.",
                    error=ErrorCode.INTERNAL_ERROR,
                )

        except Exception as e:
            return Response.fail(
                detail=f"Unexpected error: {e}",
                error=ErrorCode.INTERNAL_ERROR,
            )

        else:
            return Response.succeed(
                detail="All class dates and attendance records successfully removed from the gradebook."
            )

    # TODO: reconsider with the new AttendanceReport

    # def mark_student_absent(self, student: Student, class_date: datetime.date) -> bool:
    #     if student.id not in self.students:
    #         raise ValueError(
    #             f"Cannot mark absence: {student.full_name} is not enrolled in this course."
    #         )
    #
    #     if class_date not in self.class_dates:
    #         raise ValueError(
    #             f"Cannot mark absence: {class_date.strftime('%Y-%m-%d')} is not in the class schedule."
    #         )
    #
    #     if student.mark_absent(class_date):
    #         self.mark_dirty()
    #         return True
    #
    #     return False

    # TODO: reconsider with the new AttendanceReport

    # def unmark_student_absent(
    #     self, student: Student, class_date: datetime.date
    # ) -> bool:
    #     if student.id not in self.students:
    #         raise ValueError(
    #             f"Cannot unmark absence: {student.full_name} is not enrolled in this course."
    #         )
    #
    #     if class_date not in self.class_dates:
    #         raise ValueError(
    #             f"Cannot unmark absence: {class_date.strftime('%Y-%m-%d')} is not in the class schedule."
    #         )
    #
    #     if student.remove_absence(class_date):
    #         self.mark_dirty()
    #         return True
    #
    #     return False

    # === data validators ===

    def require_unique_student_email(self, email: str) -> None:
        """
        Validates that no existing student shares the given email address.

        Args:
            email (str): The email address to validate for uniqueness.

        Raises:
            ValueError: If a student with the same normalized email already exists.
        """
        normalized = self._normalize(email)
        if any(self._normalize(s.email) == normalized for s in self.students.values()):
            raise ValueError(f"A student with the email '{email}' already exists.")

    def require_unique_category_name(self, name: str) -> None:
        """
        Validates that no existing category shares the given name.

        Args:
            name (str): The category name to validate for uniqueness.

        Raises:
            ValueError: If a category with the same normalized name already exists.
        """
        normalized = self._normalize(name)
        if any(self._normalize(c.name) == normalized for c in self.categories.values()):
            raise ValueError(f"A category with the name '{name}' already exists.")

    def require_unique_assignment_name(self, name: str) -> None:
        """
        Validates that no existing assignment shares the given name.

        Args:
            name (str): The assignment name to validate for uniqueness.

        Raises:
            ValueError: If an assignment with the same normalized name already exists.
        """
        normalized = self._normalize(name)
        if any(
            self._normalize(a.name) == normalized for a in self.assignments.values()
        ):
            raise ValueError(f"An assignment with the name '{name}' already exists.")

    def require_unique_submission(self, assignment_id: str, student_id: str) -> None:
        """
        Validates that no submission already exists for the given student and assignment.

        Args:
            assignment_id (str): The unique ID of the assignment.
            student_id (str): The unique ID of the student.

        Raises:
            ValueError: If a submission already exists for the given student-assignment pair.
        """
        if any(
            (s.assignment_id == assignment_id and s.student_id == student_id)
            for s in self.submissions.values()
        ):
            raise ValueError(
                f"A submission the same linked student and assignment already exists."
            )

    def require_unique_class_date(self, class_date: datetime.date) -> None:
        """
        Validates that the given class date is not already scheduled.

        Args:
            class_date (datetime.date): The date to validate for uniqueness.

        Raises:
            ValueError: If the date already exists in the gradebook schedule.
        """
        if class_date in self.class_dates:
            raise ValueError(
                f"This class date is already found in the course schedule."
            )

    # TODO: create secondary submissions index with (s_id, a_id) tuple as key

    # === helper methods ===

    def _normalize(self, input: str) -> str:
        return input.strip().lower()

    # === dunder methods ===


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
