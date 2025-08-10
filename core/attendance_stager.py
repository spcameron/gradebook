# core/attendance_stager.py

"""
Utility class for staging attendance changes before committing them to the Gradebook.

`AttendanceStager` provides a temporary in-memory store for proposed attendance changes
(e.g., marking a student Present or Absent) that have not yet been written to the database.

This enables workflows such as:
    - Recording multiple attendance entries in one batch and committing them at once
    - Previewing attendance changes before saving
    - Clearing or overwriting staged changes without affecting the Gradebook

The stager supports:
    - Staging single or multiple changes
    - Overwriting or preserving existing staged values during bulk operations
    - Diff-only and active-student-only views for summaries and pending change lists
    - Calculating an overlay of staged + Gradebook values for preview purposes
"""

from collections import Counter
from collections.abc import Collection

from models.student import AttendanceStatus


class AttendanceStager:
    """
    A temporary store for proposed attendance changes, keyed by student ID.

    The stager is intended for short-lived use during attendance recording or editing flows.
    It does not persist data between runs and is discarded after committing or clearing.

    Notes:
        - Staged values are stored in a simple `dict[str, AttendanceStatus]`.
        - No validation is performed on student IDs — the caller is responsible for passing valid and relevant IDs.
    """

    def __init__(self):
        self._staged: dict[str, AttendanceStatus] = {}

    def stage(self, student_id: str, status: AttendanceStatus) -> None:
        """
        Stage or replace a single attendance change.

        Args:
            student_id (str): The unique ID of the student.
            status (AttendanceStatus): The proposed attendance status.
        """
        self._staged[student_id] = status

    def unstage(self, student_id: str) -> None:
        """
        Remove a staged change for the given student ID, if present.

        Args:
            student_id (str): The unique ID of the student to unstage.
        """
        self._staged.pop(student_id, None)

    def bulk_stage(
        self,
        student_ids: Collection[str],
        status: AttendanceStatus,
        overwrite: bool = True,
    ) -> None:
        """
        Stage the same attendance status for multiple students.

        Args:
            student_ids (Collection[str]): A collection of student IDs to stage.
            status (AttendanceStatus): The status to apply to all given IDs.
            overwrite (bool): If False, preserves existing staged values for students already staged.
        """
        student_ids = set(student_ids)

        for student_id in student_ids:
            if student_id in self._staged and not overwrite:
                continue

            self.stage(student_id, status)

    def clear(self) -> None:
        """Remove all staged changes."""
        self._staged.clear()

    def is_empty(self) -> bool:
        """
        Check whether the stager contains any staged changes.

        Returns:
            bool: True if no staged changes exist, False otherwise.
        """
        return not self._staged

    def status_map(self) -> dict[str, AttendanceStatus]:
        """
        Get a shallow copy of the staged changes.

        Returns:
            dict[str, AttendanceStatus]: A copy of the staging dictionary.
        """
        return self._staged.copy()

    def pending(
        self,
        active_ids: Collection[str] | None = None,
        gradebook_status_map: dict[str, AttendanceStatus] | None = None,
    ) -> list[tuple[str, AttendanceStatus]]:
        """
        Get a list of staged changes to apply.

        Optionally filters to active students only and/or returns only differences from current Gradebook data.

        Args:
            active_ids (Collection[str] | None): If provided, only include these student IDs.
            gradebook_status_map (dict[str, AttendanceStatus] | None): If provided, exclude changes where the staged value equals the Gradebook value.

        Returns:
            list[tuple[str, AttendanceStatus]]: A list of (student_id, status) tuples.

        Notes:
            - The `gradebook_status_map` comparison allows this method to act in "diff-only" mode, excluding any staged entries that would not actually change the Gradebook.
            - If `active_ids` is provided, it is converted to a set for O(1) lookups.
        """
        active_ids = set(active_ids) if active_ids else None

        pending = []

        for student_id, status in self._staged.items():
            if active_ids is not None and student_id not in active_ids:
                continue

            if (
                gradebook_status_map is not None
                and gradebook_status_map.get(student_id, AttendanceStatus.UNMARKED)
                == status
            ):
                continue

            pending.append((student_id, status))

        return pending
