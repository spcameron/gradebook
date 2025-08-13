# cli/attendance_menu.py

"""
Manage Attendance menu for the Gradebook CLI.

Summary:
- Provides interactive workflows to record, edit, view, and reset attendance for a selected class date.
- Includes a schedule manager to view, add, remove, clear, and generate recurring class dates.
- Separates UI/staging from persistence: gradebook writes occur only in explicit commit paths.

Key concepts:
- AttendanceStager: in-memory diff layer for per-student status changes prior to commit.
- GatewayState: immutable snapshot of the active roster, gradebook map, staged map, preview map, counts, and flags.
- Gateway loop: rebuild state → render options → dispatch action → repeat until exit.

Main entry points:
- run(gradebook): top-level Manage Attendance loop; always prompts to save on exit.
- record_attendance(gradebook): orchestrates the gateway for a single date with staging and apply/clear/edit flows.
- manage_class_schedule(gradebook): submenu to view and mutate the course schedule, including a recurring schedule generator.

Record Attendance actions (GatewayResponse):
- START_UNMARKED: walk unmarked students, stage Present/Absent/Excused/Late (skip and cancel supported).
- STAGE_REMAINING_PRESENT / STAGE_REMAINING_ABSENT: bulk-stage remaining unmarked students.
- EDIT_EXISTING: resolve any staging, then enter immediate-write edit flow for existing marks.
- APPLY_NOW: compute diff-only payload and commit via batch API with retry/keep/discard for failures.
- CLEAR_DATE: clear all gradebook marks for the date (active and inactive); staging can be preserved or discarded; optional apply-now.
- CANCEL: resolve staged work (apply/discard/cancel) and exit the gateway.

Schedule tools:
- view_current_schedule: read-only monthly view of class dates.
- add_class_date / remove_class_date / confirm_and_clear_schedule: single-date and bulk destructive operations with confirmations.
- generate_recurring_schedule: wizard to build dates over a start–end range by weekdays, with optional “No Class” exceptions and preview.
- populate_candidate_schedule: inclusive range generator using ISO weekday numbers (0=Mon … 6=Sun).
- preview_and_confirm_course_schedule: interactive add/remove adjustments before batch add.

Input helpers:
- resolve_class_date: choose a date by manual entry or from the schedule; can add missing dates with confirmation.
- prompt_class_date_or_cancel: strict YYYY-MM-DD input parsed via date.fromisoformat; blank cancels.
- prompt_class_date_from_schedule: pick from scheduled dates with an optional “[ATTENDANCE TAKEN]” badge (all active students marked).
- prompt_start_and_end_dates / prompt_weekdays_or_cancel / prompt_no_class_dates: data entry steps used by the recurring generator.

Guarantees and policies:
- Gradebook mutations occur only in APPLY_NOW, edit-by-date (via EDIT_EXISTING), schedule add/remove/clear, and recurring batch add.
- Destructive actions are confirmation-gated; staging is never implicitly committed or discarded.
- Staged changes persist across gateway passes until explicitly applied or cleared.
- Counts, badges, and option gating derive from GatewayState; inactive students are excluded from maps and counts.

Cancellation and errors:
- User cancel paths return cleanly to the prior menu; staged changes are preserved unless explicitly discarded.
- Response failures from gradebook queries/commands display feedback and abort the current operation without partial, silent writes.
- KeyboardInterrupt/EOFError bubble to the caller by design; the parent menu handles unsaved-change prompts.

Side effects:
- Writes prompts and summaries to stdout; adheres to a consistent “returning to …” messaging pattern on exits.
- The top-level Manage Attendance loop enforces a save-check on exit; some flows may prompt to save immediately after batch operations.

Module dependencies:
- Uses `helpers` for menus, prompts, display, and standard banners; uses `formatters` for date labels.
- Relies on Gradebook batch/single operations and Response contracts for success/failure signaling.
"""

from __future__ import annotations

import calendar
import datetime
from collections import Counter
from collections.abc import Callable
from enum import Enum
from textwrap import dedent
from typing import cast

import cli.menu_helpers as helpers
import cli.model_formatters as model_formatters
import core.formatters as formatters
from cli.menu_helpers import MenuSignal
from core.attendance_stager import AttendanceStager
from core.response import ErrorCode
from models.gradebook import Gradebook
from models.student import AttendanceStatus, Student


class GatewayResponse(str, Enum):
    START_UNMARKED = "START_UNMARKED"
    STAGE_REMAINING_PRESENT = "STAGE_REMAINING_PRESENT"
    STAGE_REMAINING_ABSENT = "STAGE_REMAINING_ABSENT"
    EDIT_EXISTING = "EDIT_EXISTING"
    CLEAR_DATE = "CLEAR_DATE"
    APPLY_NOW = "APPLY_NOW"
    CANCEL = "CANCEL"


class GatewayState:
    """
    Immutable, read-only snapshot for the Record Attendance gateway screen.

    This object is built once per render and exposes a consistent view of:
    - the selected class date,
    - the active roster (order: last name, first name),
    - the gradebook's current statuses for that date (active students only),
    - the session's staged changes (active students only, diffs vs. gradebook),
    - the effective preview after overlaying staged diffs on the gradebook view,
    - counts and convenience flags for menu gating.

    Args:
        class_date (datetime.date): The date being recorded.
        active_roster (list[Student]): Active students for the date. Used for names, sorting, and ID indexing.
        gradebook_status_map (dict[str, AttendanceStatus]): The gradebook’s truth for the date (may include non‑active IDs).
        staged_status_map (dict[str, AttendanceStatus]): Per‑session staging (may include non‑active IDs and no‑ops).

    Derived attributes (all filtered to active students):
        - gradebook_map (dict[str, AttendanceStatus]): Current gradebook statuses.
        - staged_map (dict[str, AttendanceStatus]): Only entries that differ from `gradebook_map`.
        - effective_map (dict[str, AttendanceStatus]): `gradebook_map` overlaid with `staged_map`.
            - Iteration order follows the sorted active roster (last name, first name).
        - gradebook_counts (dict[AttendanceStatus, int]): Counts by status in `gradebook_map`.
        - staged_counts (dict[AttendanceStatus, int]): Counts by status in `staged_map`.
        - effective_counts (dict[AttendanceStatus, int]): Counts by status in `effective_map`.
        - unmarked_ids (list[str]): Active student IDs whose effective status is `UNMARKED` (sorted by name).
        - unmarked_count (int): Length of `unmarked_ids`.

    Flags:
        - is_complete_preview (bool): True if no effective statuses are `UNMARKED`.
        - has_staging (bool): True if at least one staged diff exists.
        - can_apply_now (bool): Alias for `has_staging`.
        - can_start_unmarked (bool): True if any `UNMARKED` remain.
        - can_mark_remaining_present/absent (bool): True if any `UNMARKED` remain.
        - can_edit_existing (bool): True if any active student has a non‑`UNMARKED` status in the gradebook.

    Notes:
        - Missing entries in inputs are treated as `UNMARKED`.
        - Inactive students are excluded from maps, counts, and samples.
        - External immutability is enforced by returning defensive copies from accessors.
    """

    def __init__(
        self,
        class_date: datetime.date,
        active_roster: list[Student],
        gradebook_status_map: dict[str, AttendanceStatus],
        staged_status_map: dict[str, AttendanceStatus],
    ) -> None:
        # --- roster/indexes for this render ---
        self._active_roster: list[Student] = sorted(
            active_roster, key=lambda x: (x.last_name, x.first_name)
        )
        self._active_ids: set[str] = {s.id for s in self._active_roster}
        self._active_roster_count: int = len(self._active_roster)

        # --- generating preview overlay ---
        # missing entries are treated as UNMARKED
        default_status = AttendanceStatus.UNMARKED

        # gradebook_status_map with defensive filter to active IDs
        gradebook_map_filtered: dict[str, AttendanceStatus] = {
            student_id: status
            for student_id, status in gradebook_status_map.items()
            if student_id in self._active_ids
        }

        # only staged entries for active IDs that differ from gradebook
        staged_map_filtered: dict[str, AttendanceStatus] = {}

        for student_id, staged in staged_status_map.items():
            if student_id in self._active_ids:
                prev = gradebook_map_filtered.get(student_id, default_status)
                if staged != prev:
                    staged_map_filtered[student_id] = staged

        # effective (preview) map: gradebook overlaid with staged diffs
        effective_status_map: dict[str, AttendanceStatus] = {}

        for student in self._active_roster:
            student_id = student.id
            effective_status_map[student_id] = staged_map_filtered.get(
                student_id, gradebook_map_filtered.get(student_id, default_status)
            )

        # --- counts by enum for each mapping ---
        gradebook_counts = Counter(gradebook_map_filtered.values())
        staged_counts = Counter(staged_map_filtered.values())
        effective_counts = Counter(effective_status_map.values())

        for status in AttendanceStatus:
            gradebook_counts.setdefault(status, 0)
            staged_counts.setdefault(status, 0)
            effective_counts.setdefault(status, 0)

        # tiny unmarked sample, sorted Last, First for display nicety
        # (names are only for UI; IDs drive logic)
        roster_by_id = {student.id: student for student in self._active_roster}

        unmarked_ids = {
            student_id
            for student_id, status in effective_status_map.items()
            if status == AttendanceStatus.UNMARKED
        }

        # --- store frozen snapshot ---
        self._active_roster_by_id: dict[str, Student] = roster_by_id

        self._class_date: datetime.date = class_date
        self._date_label_short: str = formatters.format_class_date_short(class_date)
        self._date_label_long: str = formatters.format_class_date_long(class_date)

        self._gradebook_map: dict[str, AttendanceStatus] = gradebook_map_filtered
        self._staged_map: dict[str, AttendanceStatus] = staged_map_filtered
        self._effective_map: dict[str, AttendanceStatus] = effective_status_map

        self._gradebook_counts: dict[AttendanceStatus, int] = dict(gradebook_counts)
        self._staged_counts: dict[AttendanceStatus, int] = dict(staged_counts)
        self._effective_counts: dict[AttendanceStatus, int] = dict(effective_counts)

        self._unmarked_ids = sorted(
            unmarked_ids,
            key=lambda x: (roster_by_id[x].last_name, roster_by_id[x].first_name),
        )
        self._unmarked_count: int = len(unmarked_ids)

        self._is_complete_preview: bool = self._unmarked_count == 0
        self._has_staging: bool = bool(staged_map_filtered)

    # === properties (read-only) ===

    # --- date ---

    @property
    def class_date(self) -> datetime.date:
        return self._class_date

    @property
    def date_label_short(self) -> str:
        return self._date_label_short

    @property
    def date_label_long(self) -> str:
        return self._date_label_long

    # --- roster ---

    @property
    def active_roster(self) -> list[Student]:
        return self._active_roster.copy()

    @property
    def active_ids(self) -> set[str]:
        return self._active_ids.copy()

    @property
    def active_roster_by_id(self) -> dict[str, Student]:
        return self._active_roster_by_id.copy()

    @property
    def active_roster_count(self) -> int:
        return self._active_roster_count

    # --- mappings ---
    # exposes the preview map (IDs -> status) if UI wants to show badges

    @property
    def gradebook_map(self) -> dict[str, AttendanceStatus]:
        """
        Gradebook status map filtered by active students.

        Returns:
            - dict[str, AttendanceStatus]: Mapping student IDs to `AttendanceStatus`.
        """
        return self._gradebook_map.copy()

    @property
    def staged_map(self) -> dict[str, AttendanceStatus]:
        """
        Staged status map filtered by active students and differ-only entries from current Gradebook status.

        Returns:
            - dict[str, AttendanceStatus]: Mapping student IDs to `AttendanceStatus`.
        """
        return self._staged_map.copy()

    @property
    def effective_map(self) -> dict[str, AttendanceStatus]:
        """
        Status map result of overlaying `gradebook_map` with `staged_map`. In other words, what the Gradebook would look like as a result of applying changes right now.

        Returns:
            - dict[str, AttendanceStatus]: Mapping student IDs to `AttendanceStatus`.

        Notes:
            - This is what the `Gradebook` would look like as a result of applying changes.
            - Records are ordered by student (last name, first name).
        """
        return self._effective_map.copy()

    # --- counts ---

    @property
    def gradebook_counts(self) -> dict[AttendanceStatus, int]:
        return self._gradebook_counts.copy()

    @property
    def staged_counts(self) -> dict[AttendanceStatus, int]:
        return self._staged_counts.copy()

    @property
    def effective_counts(self) -> dict[AttendanceStatus, int]:
        return self._effective_counts.copy()

    # --- unmarked students ---

    @property
    def unmarked_ids(self) -> list[str]:
        return self._unmarked_ids.copy()

    @property
    def unmarked_count(self) -> int:
        return self._unmarked_count

    # --- statuses ---

    @property
    def is_complete_preview(self) -> bool:
        return self._is_complete_preview

    @property
    def has_staging(self) -> bool:
        return self._has_staging

    # === convenience flags for menu gating ===

    @property
    def can_apply_now(self) -> bool:
        return self._has_staging

    @property
    def can_start_unmarked(self) -> bool:
        return self._unmarked_count > 0

    @property
    def can_mark_remaining_present(self) -> bool:
        return self._unmarked_count > 0

    @property
    def can_mark_remaining_absent(self) -> bool:
        return self._unmarked_count > 0

    @property
    def can_edit_existing(self) -> bool:
        return any(
            count
            for status, count in self._gradebook_counts.items()
            if status != AttendanceStatus.UNMARKED
        )


def run(gradebook: Gradebook) -> None:
    """
    Top-level loop with dispatch for the Manage Attendance menu.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        - The finally block guarantees a check for unsaved changes before returning.
    """
    title = formatters.format_banner_text("Manage Attendance")
    options = [
        ("Manage Class Schedule", manage_class_schedule),
        ("Record Attendance", record_attendance),
        ("Edit Attendance", edit_attendance),
        ("View Attendance by Date", view_attendance_by_date),
        ("View Attendance by Student", view_attendance_by_student),
        ("Reset Attendance Data", reset_attendance_data),
    ]
    zero_option = "Return to Course Manager menu"

    try:
        while True:
            menu_response = helpers.display_menu(title, options, zero_option)

            if menu_response is MenuSignal.EXIT:
                break
            elif callable(menu_response):
                menu_response(gradebook)
            else:
                raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

    finally:
        helpers.prompt_if_dirty(gradebook)

    helpers.returning_to("Course Manager menu")


# === manage class schedule ===


def manage_class_schedule(gradebook: Gradebook):
    """
    Interactive sub-menu for managing the course's class schedule.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        - Allows viewing, modifying, clearing, and generating the class schedule.
        - Returns control to the Manage Attendance menu when complete.
    """
    title = formatters.format_banner_text("Manage Class Schedule")
    options = [
        ("View Current Schedule", view_current_schedule),
        ("Add a Class Date", add_class_date),
        ("Clear Entire Schedule", confirm_and_clear_schedule),
        ("Generate a Recurring Schedule", generate_recurring_schedule),
    ]
    zero_option = "Return to Manage Attendance menu"

    while True:
        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response is MenuSignal.EXIT:
            break
        elif callable(menu_response):
            menu_response(gradebook)
        else:
            raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

    helpers.returning_to("Manage Attendance menu")


def view_current_schedule(gradebook: Gradebook) -> None:
    """
    Displays the current course schedule in a read-only, month-grouped view.

    This is a thin pass-through to `helpers.sort_and_display_course_dates`, which:
        - Prints a banner heading.
        - Groups dates by month/year and sorts them ascending.
        - Shows a "No dates to display" message if the schedule is empty.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Writes the formatted schedule (or empty message) to stdout.
    """
    helpers.sort_and_display_course_dates(gradebook.class_dates, "Course Schedule")


def add_class_date(gradebook: Gradebook) -> None:
    """
    Prompts the user to add one or more class dates to the course schedule.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - For each date, the user is shown a preview and asked to confirm before it is added.
        - Invalid or duplicate dates are rejected, with the reason displayed.
        - After each addition, the user is prompted to continue or return to the Manage Class Schedule menu.
    """
    while True:
        date_input = prompt_class_date_or_cancel()

        if date_input is MenuSignal.CANCEL:
            break

        new_date = cast(datetime.date, date_input)

        if preview_and_confirm_class_date(new_date):
            add_response = gradebook.add_class_date(new_date)

            if not add_response.success:
                helpers.display_response_failure(add_response)
                print("\nClass date was not added.")
            else:
                print(f"\n{add_response.detail}")

        if not helpers.confirm_action(
            "Would you like to continue adding dates to the course schedule?"
        ):
            break

    helpers.returning_to("Manage Class Schedule menu")


def preview_and_confirm_class_date(class_date: datetime.date) -> bool:
    """
    Displays a preview of a class date and prompts the user to confirm its addition.

    Args:
        class_date (datetime.date): The proposed class date.

    Returns:
        - True if the user confirms the addition.
        - False if the user declines, with a message indicating the date was discarded.

    Notes:
        - Uses long-format date strings for clarity during preview.
        - Uses short-format strings when discarding to visually distinguish the messages.
    """
    print("\nYou are about to add the following date to the course schedule:")
    print(formatters.format_class_date_long(class_date))

    if helpers.confirm_action("Would you like to add this date?"):
        return True
    else:
        print(
            f"\nDiscarding class date: {formatters.format_class_date_short(class_date)}"
        )
        return False


def remove_class_date(gradebook: Gradebook) -> None:
    """
    Prompts the user to remove one or more class dates from the course schedule.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - If the schedule is empty, the method exits early.
        - Each removal requires explicit user confirmation.
        - If a date is not found in the schedule, an error message is shown.
        - The user is prompted after each attempt to continue or return to the Manage Class Schedule menu.
    """
    if not gradebook.class_dates:
        print("\nThere are no scheduled class dates to remove.")
        helpers.returning_to("Manage Class Schedule menu")
        return

    while True:
        date_input = prompt_class_date_or_cancel()

        if date_input is MenuSignal.CANCEL:
            break

        target_date = cast(datetime.date, date_input)

        if confirm_and_remove_class_date(target_date, gradebook):
            gradebook_response = gradebook.remove_class_date(target_date)

            if not gradebook_response.success:
                helpers.display_response_failure(gradebook_response)
                print("\nClass date was not removed.")
            else:
                print(f"\n{gradebook_response.detail}")

        if not helpers.confirm_action(
            "Would you like to continue removing dates from the course schedule?"
        ):
            break

    helpers.returning_to("Manage Class Schedule menu")


def confirm_and_remove_class_date(
    class_date: datetime.date, gradebook: Gradebook
) -> bool:
    """
    Displays a confirmation prompt before removing a class date from the course schedule.

    Args:
        class_date (datetime.date): The target date to remove.
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        - True if the user confirms the removal.
        - False if the date is not in the schedule or the user cancels.

    Notes:
        - A warning is displayed if the date has attendance records linked to it.
        - The user is clearly informed that this action is destructive and cannot be undone.
        - No action is taken unless explicitly confirmed.
    """
    if class_date not in gradebook.class_dates:
        print(
            f"\n{formatters.format_class_date_long(class_date)} is not in the course schedule."
        )
        return False

    helpers.caution_banner()
    print("You are about to remove the following date from the course schedule:")
    print(formatters.format_class_date_long(class_date))
    print(
        "\nIf attendance has already been record for this date, that information will also be deleted from the gradebook."
    )

    if helpers.confirm_action(
        "Would you like to remove this date? This action cannot be undone."
    ):
        return True
    else:
        helpers.returning_without_changes()
        return False


def confirm_and_clear_schedule(gradebook: Gradebook) -> None:
    """
    Clears all scheduled class dates from the course, along with associated attendance records.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - This is a global destructive action; there is no undo.
        - If the schedule is empty, the method exits early.
        - Displays a warning and confirmation prompt before proceeding.
        - If the user cancels or the operation fails, no changes are made.
        - If successful, the class schedule and related attendance data are fully erased.
        - Returns to the Manage Class Schedule menu after completion.
    """
    if not gradebook.class_dates:
        print("\nThere are no scheduled class dates to remove.")
        helpers.returning_to("Manage Class Schedule menu")
        return

    helpers.caution_banner()
    print("You are about to remove all dates from the course schedule.")
    print("The attendance records for each date will also be deleted.")

    if helpers.confirm_action(
        "Are you sure you want to erase all dates from the course schedule? This action cannot be undone."
    ):
        gradebook_response = gradebook.remove_all_class_dates()

        if not gradebook_response.success:
            helpers.display_response_failure(gradebook_response)
            print("\nCould not clear the course schedule.")
        else:
            print(f"\n{gradebook_response.detail}")

    else:
        helpers.returning_without_changes()

    helpers.returning_to("Manage Class Schedule menu")


def generate_recurring_schedule(gradebook: Gradebook) -> None:
    """
    Guides the user through creating a recurring class schedule within a specified date range.

    Workflow:
        - Prompt for a start/end date (inclusive).
        - Prompt for weekday to include (e.g., Mon/Wed/Fri).
        - Generate candidate dates across the range matching those weekdays.
        - Optionally mark exceptions ("No Class" days), removing them from candidates.
        - Preview the resulting schedule; allow manual add/remove adjustments.
        - On confirmation, persist via `gradebook.batch_add_class_dates()` and report results.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - If the user cancels at any step or declines the final confirmation, no changes are made.
        - A prompt to save is shown at the end if changes were made.
    """
    banner = formatters.format_banner_text("Recurring Schedule Generator")
    print(f"\n{banner}\n")

    dates_input = prompt_start_and_end_dates()

    if dates_input is MenuSignal.CANCEL:
        return

    start_date, end_date = cast(tuple[datetime.date, datetime.date], dates_input)

    weekdays_input = prompt_weekdays_or_cancel()

    if weekdays_input is MenuSignal.CANCEL:
        return

    weekdays = cast(list[int], weekdays_input)

    candidate_schedule = populate_candidate_schedule(start_date, end_date, weekdays)

    no_classes_dates = []

    if helpers.confirm_action(
        "Would you like to mark some of these dates as 'No Class' dates (holidays, etc.)?"
    ):
        no_classes_dates = prompt_no_class_dates()

    if no_classes_dates:
        for off_day in no_classes_dates:
            candidate_schedule.remove(off_day)

    if preview_and_confirm_course_schedule(candidate_schedule, no_classes_dates):
        gradebook_response = gradebook.batch_add_class_dates(candidate_schedule)

        added_dates = gradebook_response.data["success"]
        skipped_dates = gradebook_response.data["failure"]

        if not gradebook_response.success:
            helpers.display_response_failure(gradebook_response)

            if gradebook_response.error is ErrorCode.VALIDATION_FAILED:
                print(
                    f"{len(added_dates)} of {len(candidate_schedule)} dates were added."
                )
                print(
                    f"{len(skipped_dates)} dates were skipped due to validation errors."
                )
            else:
                print(
                    f"Batch entry failed after adding {len(added_dates)} of {len(skipped_dates)} dates."
                )

        else:
            print(f"\n{gradebook_response.detail}")

    else:
        print(f"\nDiscarding {len(candidate_schedule)} dates. No changes made.")

    helpers.prompt_if_dirty(gradebook)
    helpers.returning_to("Manage Class Schedule menu")


def populate_candidate_schedule(
    start_date: datetime.date, end_date: datetime.date, weekdays: list[int]
) -> list[datetime.date]:
    """
    Generates a list of class dates based on a start/end range and selected weekdays.

    Args:
        start_date (datetime.date): The first date in the schedule range.
        end_date (datetime.date): The last date in the schedule range.
        weekdays (list[int]): A list of integers representing weekdays (0=Monday to 6=Sunday).

    Returns:
        A list of `datetime.date` objects that fall within the given range and match one of the specified weekdays.

    Notes:
        - Dates are returned in ascending order.
        - If no matches are found, the returned list will be empty.
    """
    candidate_schedule = []
    pointer_date = start_date

    while pointer_date <= end_date:
        if pointer_date.weekday() in weekdays:
            candidate_schedule.append(pointer_date)
        pointer_date += datetime.timedelta(days=1)

    return candidate_schedule


def preview_and_confirm_course_schedule(
    course_schedule: list[datetime.date], off_days: list[datetime.date]
) -> bool:
    """
    Previews the generated recurring schedule and allows the user to make manual adjustments.

    Args:
        course_schedule (list[datetime.date]): A list of class dates initially generated based on user input.
        off_days (list[datetime.date]): A list of dates excluded from the schedule (e.g., holidays).

    Returns:
        - True if the user confirms the schedule and wants to proceed.
        - False if the user cancels or declines final confirmation.

    Notes:
        - Users may optionally add new dates not in the recurring pattern.
        - Users may remove dates from the schedule, which are added to the off-days list.
        - A final confirmation prompt is shown with a preview of both included and excluded dates.
    """
    print("\nYou have generated the following recurring course schedule:")
    helpers.sort_and_display_course_dates(course_schedule)

    if off_days:
        print("\nThe following dates have been marked as 'No Class' dates:")
        helpers.sort_and_display_course_dates(set(off_days))

    if helpers.confirm_action("Would you like to add any dates to this schedule?"):
        while True:
            print("\nSelect a new date to add to the schedule:")
            class_date_input = prompt_class_date_or_cancel()

            if class_date_input is MenuSignal.CANCEL:
                break
            elif class_date_input not in course_schedule:
                course_schedule.append(cast(datetime.date, class_date_input))

            if not helpers.confirm_action(
                "Would you like to continue adding dates to the schedule?"
            ):
                break

    if helpers.confirm_action("Would you like to remove any dates from this schedule?"):
        while True:
            print("\nSelect an existing date to remove from the schedule:")
            off_day_input = prompt_class_date_or_cancel()

            if off_day_input is MenuSignal.CANCEL:
                break
            elif off_day_input in course_schedule:
                course_schedule.remove(cast(datetime.date, off_day_input))
                off_days.append(cast(datetime.date, off_day_input))

            if not helpers.confirm_action(
                "Would you like to continue removing dates from the schedule?"
            ):
                break

    print("\nYou are about to add the following dates to the course schedule")
    helpers.sort_and_display_course_dates(course_schedule)

    if off_days:
        print("\nThe following dates have been marked as 'No Class' dates:")
        helpers.sort_and_display_course_dates(set(off_days))

    return helpers.confirm_action(
        "Would you like to add these dates to the course schedule?"
    )


# === data input helpers ===


def prompt_class_date_or_cancel() -> datetime.date | MenuSignal:
    """
    Prompts the user to enter a class date in YYYY-MM-DD format or cancel the operation.

    Returns:
        - A `datetime.date` object if the input is valid.
        - `MenuSignal.CANCEL` if the user leaves the input blank or issues a cancel command.

    Notes:
        - Invalid formats trigger a validation message and re-prompt.
        - The prompt message includes formatting instructions and cancel guidance.
    """
    while True:
        date_input = helpers.prompt_user_input_or_cancel(
            "Enter the class date (YYYY-MM-DD, leave blank to cancel):"
        )

        if isinstance(date_input, MenuSignal):
            return date_input

        try:
            return datetime.date.fromisoformat(date_input)

        except (ValueError, TypeError):
            print(
                "\nInvalid input. Enter the date as YYYY-MM-DD or leave blank to cancel."
            )
            print("Please try again.")


def prompt_class_date_from_schedule(gradebook: Gradebook) -> datetime.date | MenuSignal:
    """
    Let the user pick an existing class date from the schedule, with a completion badge.

    The menu lists scheduled dates in ascending order. Each line shows the long-form date and, when applicable, the “[ATTENDANCE TAKEN]” badge indicating that all active students have a non-UNMARKED attendance status for that date.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        datetime.date: The selected class date.
        MenuSignal.CANCEL: If the schedule is empty or the user cancels.

    Notes:
        - If no dates exist, prints guidance and returns CANCEL immediately.
        - Displays a numbered list of dates; “0” cancels.
        - Invalid selections re-prompt without mutation.
        - Badge computation considers only active students; if active-roster lookup fails, the badge is omitted (conservative default).
        - Prints to stdout only; does not modify gradebook state.
    """

    def build_formatter(badges_enabled: bool, completed_dates: set[datetime.date]):
        def format(date: datetime.date) -> str:
            label = formatters.format_class_date_long(date)
            return (
                f"{label:<20} [ATTENDANCE TAKEN]"
                if badges_enabled and date in completed_dates
                else f"{label:<20}"
            )

        return format

    class_dates = sorted(gradebook.class_dates)

    if not class_dates:
        print("\nThere are no class dates in the course schedule to choose from.")
        print(
            "Please enter a date manually and add it to the gradebook before proceeding."
        )
        return MenuSignal.CANCEL

    completed_dates = set()
    badges_enabled = False

    gradebook_response = gradebook.get_records(
        gradebook.students,
        lambda x: x.is_active,
    )

    active_students = (
        gradebook_response.data["records"] if gradebook_response.success else None
    )

    if active_students:
        badges_enabled = True
        for class_date in class_dates:
            all_marked = True
            for student in active_students:
                if student.attendance_on(class_date) == AttendanceStatus.UNMARKED:
                    all_marked = False
                    break
            if all_marked:
                completed_dates.add(class_date)

    formatter = build_formatter(badges_enabled, completed_dates)

    while True:
        print(f"\n{formatters.format_banner_text('Course Schedule')}")
        helpers.display_results(class_dates, True, formatter)

        choice = helpers.prompt_user_input("Select an option (0 to cancel):")

        if choice == "0":
            return MenuSignal.CANCEL

        try:
            index = int(choice) - 1
            return class_dates[index]

        except (ValueError, IndexError):
            print("\nInvalid selection. Please try again.")


def prompt_start_and_end_dates() -> tuple[datetime.date, datetime.date] | MenuSignal:
    """
    Prompts the user to define a start and end date for the recurring schedule.

    Returns:
        - A tuple of (`start_date`, `end_date`) as `datetime.date` objects if confirmed.
        - `MenuSignal.CANCEL` if the user cancels during input or confirmation.

    Notes:
        - Both dates must be valid and follow the YYYY-MM-DD format.
        - The end date must come after the start date.
        - The user is shown a preview of their selections and asked to confirm or restart.
        - Canceling at any step discards input and exits the schedule generator.
    """
    while True:
        print("\nSelect the beginning and ending dates of the course schedule:")

        print("\nWhat is the first class date?")

        start_date_input = prompt_class_date_or_cancel()

        if start_date_input is MenuSignal.CANCEL:
            print("\nDiscarding dates and canceling schedule creator.")
            return MenuSignal.CANCEL

        start_date = cast(datetime.date, start_date_input)

        print("\nWhat is the last class date?")

        end_date_input = prompt_class_date_or_cancel()

        if end_date_input is MenuSignal.CANCEL:
            print("\nDiscarding dates and canceling schedule creator.")
            return MenuSignal.CANCEL

        end_date = cast(datetime.date, end_date_input)

        if not start_date < end_date:
            print("\nInvalid entry. The end date must come after the start date.")
            print("Please try again.")
            continue

        start_date_str = formatters.format_class_date_long(start_date)
        end_date_str = formatters.format_class_date_long(end_date)

        print("\nYou have entered the following dates for your course schedule:")
        print(f"... Beginning on {start_date_str}")
        print(f"... Ending on {end_date_str}")

        if helpers.confirm_action("Would you like to proceed using this date range?"):
            return (start_date, end_date)
        elif helpers.confirm_action(
            "Would you like to start over and try choosing dates again?"
        ):
            continue
        else:
            print("\nDiscarding dates and canceling schedule generator.")
            return MenuSignal.CANCEL


def prompt_weekdays_or_cancel() -> list[int] | MenuSignal:
    """
    Prompts the user to select one or more weekdays for the recurring class schedule.

    Returns:
        - A sorted, de-duplicated list of integers representing weekdays (0=Monday to 6=Sunday) if confirmed.
        - `MenuSignal.CANCEL` if the user cancels during input or confirmation.

    Notes:
        - The user may add days interactively, one at a time.
        - Selected days are previewed before confirmation.
        - If no days are selected, the user is prompted to retry or cancel.
        - Uses `calendar.day_name` to display human-readable day names.
    """
    title = "\nChoose a day of the week to add to your schedule:"
    options = [
        ("Monday", lambda: 0),
        ("Tuesday", lambda: 1),
        ("Wednesday", lambda: 2),
        ("Thursday", lambda: 3),
        ("Friday", lambda: 4),
        ("Saturday", lambda: 5),
        ("Sunday", lambda: 6),
    ]
    zero_option = "Cancel without adding a new day"

    while True:
        weekdays = set()
        print("\nSelect which days of the week you meet for class:")

        while True:
            if weekdays:
                print("\nYou have already selected the following days:")
                for day in sorted(weekdays):
                    print(f" - {calendar.day_name[day]}")

            menu_response = helpers.display_menu(title, options, zero_option)

            if menu_response is MenuSignal.EXIT:
                break
            elif callable(menu_response):
                weekdays.add(menu_response())
            else:
                raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

            if not helpers.confirm_action(
                "Would you like to add another day of the week?"
            ):
                break

        if not weekdays:
            print("\nYou have not selected any weekdays.")

            if helpers.confirm_action("Would you like to start over and try again?"):
                continue
            else:
                print("\nDiscarding days and canceling schedule generator.")
                return MenuSignal.CANCEL

        else:
            print(
                f"\nYou have selected {formatters.format_list_with_and([calendar.day_name[day] for day in sorted(weekdays)])}"
            )

        if helpers.confirm_action(
            "Would you like to use these days for your recurring schedule?"
        ):
            return list(sorted(weekdays))
        elif helpers.confirm_action(
            "Would you like to start over and try choosing days again?"
        ):
            continue
        else:
            print("\nDiscarding days and canceling schedule generator.")
            return MenuSignal.CANCEL


def prompt_no_class_dates() -> list[datetime.date]:
    """
    Prompts the user to mark specific dates as 'No Class' days to exclude from the recurring schedule.

    Returns:
        A sorted, de-duplicated list of `datetime.date` objects marked for omission.

    Notes:
        - Dates are entered one at a time using the standard date prompt.
        - Previously selected dates are shown before each new entry.
        - Duplicate entries are ignored.
        - If no dates are selected, the user may choose to retry or proceed with none.
        - Dates are not validated against the generated schedule in this prompt.
        - Cancel during selection returns to confirmation with the current selection; cancel at the final prompt returns an empty list.
    """
    print(
        dedent(
            """\
            If there are any dates in your recurring schedule where class is not held,
            (e.g., holidays, in-service days, etc.) you may indicate those days here.

            You can also add or remove specific dates from the schedule at any time 
            via the Manage Course Schedule menu.
            """
        )
    )

    while True:
        no_class_dates = set()
        print("\nSelect which dates to omit from the recurring schedule:")

        while True:
            if no_class_dates:
                print("\nYou have already selected the following 'No Class' dates:")
                helpers.sort_and_display_course_dates(
                    no_class_dates, "'No Class' Dates"
                )

            print("\nSelect a 'No Class' date:")
            new_off_day = prompt_class_date_or_cancel()

            if new_off_day is MenuSignal.CANCEL:
                break
            else:
                no_class_dates.add(new_off_day)

            if not helpers.confirm_action(
                "Would you like to add another 'No Class' date?"
            ):
                break

        if not no_class_dates:
            print("\nYou have not selected any 'No Class' dates.")

            if helpers.confirm_action("Would you like to start over and try again?"):
                continue
            else:
                print("\nReturning to schedule generator without any 'No Class' dates.")
                return []

        else:
            print("\nYou have marked the following dates as 'No Class' dates:")
            helpers.sort_and_display_course_dates(no_class_dates, "'No Class' Dates")

        if helpers.confirm_action(
            "Would you like to exclude these dates from your recurring schedule?"
        ):
            return list(sorted(no_class_dates))
        elif helpers.confirm_action(
            "Would you like to start over and try choosing 'No Class' dates again?"
        ):
            continue
        else:
            print("\nReturning to schedule generator without any 'No Class' dates.")
            return []


# === record attendance ===


def record_attendance(gradebook: Gradebook) -> None:
    """
    Orchestrate the “Record Attendance” workflow for a single class date.

    High-level flow:
        1) Resolve the target date via `resolve_class_date(gradebook)`. If canceled, exit.
        2) Initialize an `AttendanceStager` and enter the gateway loop.
        3) On each pass:
            - Build a fresh `GatewayState` with `refresh_state(date)`. If this fails, show failure details and exit without changes.
            - Show the gateway menu with `prompt_gateway_response(state)` and dispatch on the returned `GatewayResponse`:
                - START_UNMARKED
                    - Run `start_unmarked(state)` to walk unmarked students one-by-one, staging selections (Present/Absent/Excused/Late). Offers an apply/discard/keep guard if the user cancels mid-pass.
                - STAGE_REMAINING_PRESENT / STAGE_REMAINING_ABSENT
                    - Run `stage_remaining(status, state)` to bulk-stage the chosen status for all currently unmarked students, with an optional apply-now prompt.
                - EDIT_EXISTING
                    - Run `edit_existing(date)`, which first forces staged-change resolution (apply or discard) and then dispatches to the immediate-write edit flow (`edit_by_date`).
                - APPLY_NOW
                    - Run `apply_now(date, prompt_to_exit=True)` to commit all staged diffs (with retry/keep/discard handling for failures) and optionally exit the gateway on success.
                - CLEAR_DATE
                    - Run `clear_date(date)` to wipe all gradebook marks for the date (active and inactive students). If staging exists, the user chooses to preserve or discard it before the clear; optional apply-now prompt may follow.
                - CANCEL
                    - Run `exit_gateway(date)`, which resolves any staged changes (apply/discard/cancel) and, when staging is empty, terminates the gateway loop.
        4) After the loop ends, optionally offer to display the attendance summary for the date, then return to the Manage Attendance menu.

    Guarantees & responsibilities:
        - Gradebook mutations occur only through explicit branches:
            - `apply_now(...)`, `edit_by_date(...)` (via `edit_existing`), and `clear_date(...)`.
            - All other paths operate on the in-memory stager and UI only.
        - Destructive or persistent actions are gated behind confirmations.
        - Staged changes persist across gateway passes until applied or discarded.

    Side effects:
        Prints menus, prompts, and summaries to stdout; may mutate gradebook state depending on the chosen actions. `KeyboardInterrupt`/`EOFError` are not intercepted here and bubble to the caller by design.

    Raises:
        RuntimeError: If an unexpected menu response is encountered during dispatch.
    """

    def refresh_state(date: datetime.date) -> GatewayState | None:
        """
        Build a `GatewayState` snapshot for the given date, or bail with user feedback.

        Pulls:
            - Active students via `gradebook.get_records(..., is_active)`.
            - Gradebook attendance map for the date via `gradebook.get_attendance_for_date(active_only=True)`.
            - Current staged map from the outer `stager`.

        Returns:
            GatewayState: Frozen snapshot used to render the gateway.
            None: If prerequisites cannot be retrieved; prints failure details and a “returning without changes” message before exiting.

        Notes:
            - Prints error/diagnostic messages on failure. Does not mutate gradebook state.
        """
        gradebook_response = gradebook.get_records(
            dictionary=gradebook.students,
            predicate=lambda x: x.is_active,
        )

        if not gradebook_response.success:
            helpers.display_response_failure(gradebook_response)
            print("Unable to retrieve active students.")
            helpers.returning_without_changes()
            return

        active_students = gradebook_response.data["records"]

        gradebook_response = gradebook.get_attendance_for_date(
            class_date=date,
            active_only=True,
        )

        if not gradebook_response.success:
            helpers.display_response_failure(gradebook_response)
            print("\nUnable to retrieve attendance data.")
            helpers.returning_without_changes()
            return

        gradebook_status_map = gradebook_response.data["attendance"]

        return GatewayState(
            class_date=date,
            active_roster=active_students,
            gradebook_status_map=gradebook_status_map,
            staged_status_map=stager.status_map,
        )

    def start_unmarked(state: GatewayState) -> None:
        """
        Walk the unmarked roster for `state.class_date`, staging per-student choices.

        Behavior:
            - Iterates `state.unmarked_ids` in roster order and prompts: Present / Absent / Excused / Late / Skip.
            - On “Cancel” during the pass:
                - If nothing staged: prints “returning without changes” and exits.
                - If staged changes exist: offers a three-way choice:
                    - Apply now (commit and exit),
                    - Discard (revert to the entry snapshot and exit),
                    - Keep (retain staging and exit to gateway).
            - After finishing the pass:
                - If any changes were staged, prints a summary and optionally applies now.
                - Otherwise exits silently (no changes).

        Notes:
            - Uses an entry snapshot of the stager so “Discard” restores pre-loop staging.
            - This function does not write to the gradebook; only `apply_now(...)` commits.
            - `staged_count` reflects number of stage operations, not necessarily unique IDs.
        """
        snapshot = stager.status_map
        target_ids = state.unmarked_ids
        roster_by_id = state.active_roster_by_id

        if not target_ids:
            print("All students are marked. Nothing to record.")
            return

        staged_count = 0

        banner = f"Attendance for {state.date_label_short}"
        print(f"\n{formatters.format_banner_text(banner)}")

        for student_id in target_ids:
            student = roster_by_id[student_id]

            title = f"{student.full_name}:"
            options = [
                ("Present", lambda: AttendanceStatus.PRESENT),
                ("Absent", lambda: AttendanceStatus.ABSENT),
                ("Excused", lambda: AttendanceStatus.EXCUSED_ABSENCE),
                ("Late", lambda: AttendanceStatus.LATE),
                ("Skip this student", MenuSignal.SKIP),
            ]
            zero_option = "Cancel and stop recording attendance"

            while True:
                menu_response = helpers.display_menu(title, options, zero_option)

                if menu_response is MenuSignal.EXIT:
                    if staged_count == 0:
                        helpers.returning_without_changes()
                        return

                    print(
                        f"You have {staged_count} staged {'change' if staged_count == 1 else 'changes'} for {state.date_label_short}."
                    )

                    bail_title = "What would you like to do with these staged changes?"
                    bail_options = [
                        (
                            "Apply these changes now and return",
                            lambda: MenuSignal.APPLY,
                        ),
                        (
                            "Discard these changes and return",
                            lambda: MenuSignal.DISCARD,
                        ),
                        ("Keep these changes and return", lambda: MenuSignal.KEEP),
                    ]
                    bail_zero_option = "Continue recording attendance"

                    bail_response = helpers.display_menu(
                        bail_title, bail_options, bail_zero_option
                    )

                    if bail_response is MenuSignal.EXIT:
                        continue
                    elif callable(bail_response):
                        bail_signal = bail_response()
                        match bail_signal:
                            case MenuSignal.APPLY:
                                apply_now(state.class_date)
                                return

                            case MenuSignal.DISCARD:
                                stager.revert_to_snapshot(snapshot)
                                return

                            case MenuSignal.KEEP:
                                return

                elif menu_response is MenuSignal.SKIP:
                    break

                elif callable(menu_response):
                    status = menu_response()

                    gradebook_status = state.gradebook_map.get(
                        student_id, AttendanceStatus.UNMARKED
                    )
                    had_diff = (
                        stager.status_map.get(student_id, gradebook_status)
                        != gradebook_status
                    )
                    will_have_diff = status != gradebook_status
                    if not had_diff and will_have_diff:
                        staged_count += 1

                    stager.stage(student_id, status)
                    break

                else:
                    raise RuntimeError(
                        f"Unexpected MenuResponse received: {menu_response}"
                    )

        if staged_count > 0:
            print(
                f"\nStaged updates for {staged_count} {'student' if staged_count == 1 else 'students'} on {state.date_label_short}."
            )
            print("These changes are not immediately applied to the gradebook.")

            if helpers.confirm_action("Would you like to apply these changes now?"):
                apply_now(state.class_date)
                return
            else:
                print(
                    "You may apply these changes later by selecting 'Apply Staged Changes Now' from the Record Attendance menu."
                )
                return

    def stage_remaining(status: AttendanceStatus, state: GatewayState) -> None:
        """
        Bulk-stage the given `status` for all currently unmarked students.

        Args:
            status (AttendanceStatus): The status to stage (e.g., PRESENT or ABSENT).
            state (GatewayState): Snapshot providing `unmarked_ids` and date labels.

        Behavior:
            - Calls `stager.bulk_stage(state.unmarked_ids, status, overwrite=True)`.
            - Prints a summary of how many students were staged and reminds that staging is not persisted.
            - Offers to apply the changes immediately via `apply_now(state.class_date)`; otherwise returns to the gateway with staging intact.

        Notes:
            - No gradebook writes occur unless the user chooses to apply now.
            - Count is based on the current unmarked set; if `bulk_stage` filters or skips any IDs, prefer its return value (if available).
        """
        target_ids = state.unmarked_ids
        stager.bulk_stage(
            student_ids=target_ids,
            status=status,
            overwrite=True,
        )
        staged_count = len(target_ids)

        if staged_count > 0:
            print(
                f"\nStaged {staged_count} {'student' if staged_count == 1 else 'students'} as '{status.value}' on {state.date_label_short}."
            )
            print("These changes are not immediately applied to the gradebook.")

            if helpers.confirm_action("Would you like to apply these changes now?"):
                apply_now(state.class_date)
                return
            else:
                print(
                    "You may apply these changes later by selecting 'Apply Staged Changes Now' from the Record Attendance menu."
                )
                return

    def apply_now(date: datetime.date, prompt_to_exit: bool = False) -> None:
        """
        Attempt to commit all staged attendance changes for `date`, with retry-on-fail.

        Behavior:
            - Rebuilds a fresh `GatewayState` each attempt.
            - Computes `changes = stager.pending(active_ids, gradebook_map)` (diff-only).
            - If there are no staged changes, prints a notice and returns.
            - Calls `gradebook.batch_mark_student_attendance_for_date(date, changes)`.
                - On INTERNAL_ERROR: show failure, preserve staging, and return.
                - On partial success: print successes (and unstage them), print failures, and offer:
                      - Retry now (re-run with the remaining failures),
                      - Discard and return (clear remaining staged changes),
                      - Do nothing and return (preserve remaining staged changes).
                - On no progress across retries (failure count unchanged): clear remaining staged changes and return.
                - On full success (no failures): exit the retry loop.

            - If `prompt_to_exit` is True, optionally ask the user if they are finished recording for this date; on confirmation, flip the outer `should_display_gateway` flag to exit the gateway loop.

        Notes:
            - Writes to the gradebook; prints summaries; mutates the stager by un-staging successes and possibly clearing failures; may signal the outer loop to exit.
        """
        nonlocal should_display_gateway
        prev_failed_count = -1

        while True:
            state = refresh_state(date)

            if state is None:
                print("Failed to refresh the roster or gradebook state.")
                helpers.returning_without_changes()
                return

            changes = stager.pending(
                active_ids=state.active_ids,
                gradebook_status_map=state.gradebook_map,
            )

            if not changes:
                print(
                    f"There are no staged changes to apply for {state.date_label_short}."
                )
                helpers.returning_without_changes()
                return

            gradebook_response = gradebook.batch_mark_student_attendance_for_date(
                date, changes
            )

            if (
                not gradebook_response.success
                and gradebook_response.error == ErrorCode.INTERNAL_ERROR
            ):
                helpers.display_response_failure(gradebook_response)
                print(
                    "\nFailed to apply staged changes. Returning to Record Attendance menu with all staged changes."
                )
                return

            success = gradebook_response.data["success"]
            failure = gradebook_response.data["failure"]

            if len(failure) == prev_failed_count:
                print(
                    f"Unable to resolve any of the failed change attempts. Clearing {len(failure)} staged {'change' if len(failure) == 1 else 'changes'} and returning."
                )
                stager.clear()
                return

            if success:
                print("\nThe following changes were successfully applied:")
                helpers.display_attendance_buckets(success)

                for student_id, _ in success:
                    stager.unstage(student_id)

            if failure:
                prev_failed_count = len(failure)

                print("\nThe following changes could not be applied:")
                helpers.display_attendance_buckets(failure)

                if helpers.confirm_action(
                    "Would you like to view the failed changes individually?"
                ):
                    print(
                        "\nThe following staged changes could not be applied to the gradebook:"
                    )

                    for student_id, status in failure:
                        gradebook_response = gradebook.find_student_by_uuid(student_id)
                        student = (
                            gradebook_response.data["record"]
                            if gradebook_response.success
                            else None
                        )
                        student_name = (
                            student.full_name if student else "[MISSING STUDENT]"
                        )

                        print(f"... {student_name:<20} | {status.value}")

                title = "What would you like to do with these failed changes?"
                options = [
                    ("Retry now", lambda: MenuSignal.APPLY),
                    ("Discard and return", lambda: MenuSignal.DISCARD),
                ]
                zero_option = "Keep failed changes and return"

                menu_response = helpers.display_menu(title, options, zero_option)

                if menu_response is MenuSignal.EXIT:
                    print(
                        "\nPreserving failed staged changes and returning to Record Attendance menu."
                    )
                    return

                elif callable(menu_response):
                    match menu_response():
                        case MenuSignal.APPLY:
                            print("\nAttempting to resolve the failed staged changes.")
                            continue

                        case MenuSignal.DISCARD:
                            print(
                                "\nDiscarding failed staged changes and returning to Record Attendance menu."
                            )
                            stager.clear()
                            return

                        case _:
                            raise RuntimeError(
                                f"Unexpected MenuResponse received: {menu_response}"
                            )

                else:
                    raise RuntimeError(
                        f"Unexpected MenuResponse received: {menu_response}"
                    )

            break

        if prompt_to_exit and helpers.confirm_action(
            f"Are you finished recording attendance for {state.date_label_short}?"
        ):
            should_display_gateway = False

    def edit_existing(date: datetime.date) -> None:
        """
        Gate the scalpel flow (edit-by-date) behind staged-change resolution.

        Behavior:
            - If staging is non-empty, require the user to either:
                - Apply staged changes now (via `apply_now(date)`), or
                - Discard staged changes (after confirmation).
                - “Cancel and return” exits without entering edit.
            - Re-prompts until staging is empty or the user cancels.
            - When staging is empty, dispatches to `edit_by_date(date, gradebook)` which performs immediate gradebook writes.

        Notes:
            - `apply_now` may preserve failed changes (user choice or internal error). In that case, this loop will continue to prompt until staging is cleared.
            - This function itself does not mutate the gradebook except via `apply_now`; the actual edit flow is delegated to `edit_by_date`.
        """
        while not stager.is_empty():
            print(
                "\nYou have staged changes that have not been applied to the gradebook yet."
            )
            print(
                "In order to proceed to the edit attendance menu, it is necessary to either apply these changes now or discard them."
            )

            title = "How would you like to handle these staged changes?"
            options = [
                (
                    "Apply staged changes now and proceed to editing",
                    lambda: MenuSignal.APPLY,
                ),
                (
                    "Discard staged changes and proceed to editing",
                    lambda: MenuSignal.DISCARD,
                ),
            ]
            zero_option = "Cancel and return"

            menu_response = helpers.display_menu(title, options, zero_option)

            if menu_response is MenuSignal.EXIT:
                return

            elif callable(menu_response):
                match menu_response():
                    case MenuSignal.APPLY:
                        print("\nApplying staged changes ...")
                        apply_now(date)
                        continue

                    case MenuSignal.DISCARD:
                        if helpers.confirm_action(
                            "Are you sure you want to discard the staged changes? This action cannot be undone."
                        ):
                            print("\nDiscarding staged changes ...")
                            stager.clear()
                            continue

                    case _:
                        raise RuntimeError(
                            f"Unexpected MenuResponse received: {menu_response}"
                        )

            else:
                raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

        edit_by_date(date, gradebook)

    def clear_date(date: datetime.date) -> None:
        """
        Clear all gradebook attendance for `date`, coordinating with any staged changes.

        Behavior:
            - First, confirm the destructive action (clarifies that staged changes are not part of the clear).
            - If staging exists, require a choice:
                - Preserve staged changes and clear the gradebook.
                - Discard staged changes and clear the gradebook (with an extra confirmation).
                - Cancel and return (no changes).
            - Take a snapshot of the stager, then call `gradebook.clear_all_attendance_data_for_date(date)`.
                - On failure: show details and revert the stager to the snapshot.
                - On success: print the gradebook detail and, if staging remains,
                  optionally offer to `apply_now(date, True)`.

        Notes:
            - This function never writes staged changes to the gradebook; only `apply_now(...)` commits.
            - The stager snapshot must be independent (defensive copy) for `revert_to_snapshot` to be reliable.
            - “Discard” declined at the confirmation keeps staging and proceeds with the clear (same effect as “Preserve”).
        """
        if not helpers.confirm_action(
            f"Are you certain you want to clear all attendance data{' (not including staged changes)' if not stager.is_empty() else ''} for {formatters.format_class_date_long(date)} for all students (active and inactive)? This action cannot be undone."
        ):
            helpers.returning_without_changes()
            return

        if not stager.is_empty():
            print(
                "\nYou have staged changes that have not been applied to the gradebook yet."
            )

            title = "How would you like to handle these staged changes?"
            options = [
                (
                    "Preserve staged changes and clear gradebook",
                    lambda: MenuSignal.KEEP,
                ),
                (
                    "Discard staged changes and clear gradebook",
                    lambda: MenuSignal.DISCARD,
                ),
            ]
            zero_option = "Cancel and return"

            menu_response = helpers.display_menu(title, options, zero_option)

            if menu_response is MenuSignal.EXIT:
                return

            elif callable(menu_response):
                match menu_response():
                    case MenuSignal.KEEP:
                        print("\nPreserving staged changes ...")

                    case MenuSignal.DISCARD:
                        if helpers.confirm_action(
                            "Are you sure you want to discard the staged changes? This action cannot be undone."
                        ):
                            print("\nDiscarding staged changes ...")
                            stager.clear()

                    case _:
                        raise RuntimeError(
                            f"Unexpected MenuResponse received: {menu_response}"
                        )

            else:
                raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

        snapshot = stager.status_map
        gradebook_response = gradebook.clear_all_attendance_data_for_date(date)

        if not gradebook_response.success:
            helpers.display_response_failure(gradebook_response)
            print("\nRestoring staged changes to prior state.")
            stager.revert_to_snapshot(snapshot)
            return

        print(f"\n{gradebook_response.detail}")

        if not stager.is_empty() and helpers.confirm_action(
            "Would you like to apply the staged changes now?"
        ):
            apply_now(date, True)

    def exit_gateway(date: datetime.date) -> None:
        """
        Resolve any staged changes, then exit the Record Attendance gateway.

        Behavior:
            - If staging is non-empty, require a choice:
                - Apply changes now and exit (delegates to `apply_now(date)`).
                - Discard changes and exit (after confirmation).
                - Cancel and return (keep staging; return to the gateway).
            - Re-prompts until staging is empty or the user cancels.
            - Once staging is empty, sets the outer `should_display_gateway = False` to terminate the gateway loop.

        Notes:
            - `apply_now(date)` may leave failures staged; in that case the prompt repeats.
            - This function itself does not write to the gradebook except via `apply_now`.
        """
        nonlocal should_display_gateway

        while not stager.is_empty():
            print(
                "\nYou have staged changes that have not been applied to the gradebook yet."
            )

            title = "How would you like to handle these staged changes?"
            options = [
                ("Apply changes now and exit", lambda: MenuSignal.APPLY),
                ("Discard changes and exit", lambda: MenuSignal.DISCARD),
            ]
            zero_option = "Cancel and return"

            menu_response = helpers.display_menu(title, options, zero_option)

            if menu_response is MenuSignal.EXIT:
                return

            elif callable(menu_response):
                match menu_response():
                    case MenuSignal.APPLY:
                        print("\nApplying staged changes ...")
                        apply_now(date)
                        continue

                    case MenuSignal.DISCARD:
                        if helpers.confirm_action(
                            "Are you sure you want to discard the staged changes? This action cannot be undone."
                        ):
                            print("\nDiscarding staged changes ...")
                            stager.clear()
                            continue

                    case _:
                        raise RuntimeError(
                            f"Unexpected MenuResponse received: {menu_response}"
                        )

            else:
                raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

        should_display_gateway = False

    class_date_input = resolve_class_date(gradebook)

    if class_date_input is MenuSignal.CANCEL:
        print("\nDate selection canceled.")
        helpers.returning_without_changes()
        return

    class_date = cast(datetime.date, class_date_input)
    stager = AttendanceStager()
    should_display_gateway = True

    while should_display_gateway:
        gateway_state = refresh_state(class_date)

        if gateway_state is None:
            return

        gateway_response = prompt_gateway_response(gateway_state)

        match gateway_response:
            case GatewayResponse.START_UNMARKED:
                start_unmarked(gateway_state)
                continue

            case GatewayResponse.STAGE_REMAINING_PRESENT:
                stage_remaining(AttendanceStatus.PRESENT, gateway_state)
                continue

            case GatewayResponse.STAGE_REMAINING_ABSENT:
                stage_remaining(AttendanceStatus.ABSENT, gateway_state)
                continue

            case GatewayResponse.EDIT_EXISTING:
                pass
                edit_existing(class_date)
                continue

            case GatewayResponse.APPLY_NOW:
                apply_now(gateway_state.class_date, True)
                continue

            case GatewayResponse.CLEAR_DATE:
                clear_date(class_date)
                continue

            case GatewayResponse.CANCEL:
                exit_gateway(class_date)
                continue

            case _:
                raise RuntimeError(
                    f"Unexpected GatewayResponse received: {gateway_response}"
                )

    if helpers.confirm_action(
        f"Would you like to see the attendance summary for {formatters.format_class_date_short(class_date)} before exiting?"
    ):
        helpers.display_attendance_summary(class_date, gradebook)

    helpers.returning_to("Manage Attendance menu")


def resolve_class_date(gradebook: Gradebook) -> datetime.date | MenuSignal:
    """
    Select the date to record attendance for, via manual entry or by picking from the schedule.

    Presents:
      1) Enter a date manually (YYYY-MM-DD)
      2) Choose a date from the course schedule
      0) Return and cancel

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        datetime.date: The selected (or newly added) class date.
        MenuSignal.CANCEL: If the user exits or declines required confirmations.

    Notes:
        - Manual entry and schedule pick both funnel to a single `datetime.date` value.
        - If a sub-prompt is canceled, the user is offered a chance to try again; otherwise CANCEL is returned.
        - If the chosen date is not in the schedule, the user may add it and proceed; failures are shown and the user may retry.
        - On success (existing or newly added), the date is returned; no further mutation occurs here.
    """
    title = "\nSelect which date to record attendance for:"
    options = [
        ("Enter a date manually", lambda: prompt_class_date_or_cancel()),
        (
            "Choose a date from the course schedule",
            lambda: prompt_class_date_from_schedule(gradebook),
        ),
    ]
    zero_option = "Return and cancel"

    while True:
        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response is MenuSignal.EXIT:
            print("\nDate selection canceled.")
            return MenuSignal.CANCEL

        elif callable(menu_response):
            class_date = menu_response()

            if isinstance(class_date, MenuSignal):
                print("\nDate selection canceled.")

                if not helpers.confirm_action(
                    "Would you like to try selecting a date again?"
                ):
                    return MenuSignal.CANCEL
                else:
                    continue

            if class_date not in gradebook.class_dates:
                print(
                    f"\n{formatters.format_class_date_long(class_date)} is not in the course schedule."
                )

                if not helpers.confirm_action(
                    "Do you want to add it to the schedule and proceed with recording attendance?"
                ):
                    if not helpers.confirm_action(
                        "Would you like to try selecting a date again?"
                    ):
                        return MenuSignal.CANCEL
                    else:
                        continue

                gradebook_response = gradebook.add_class_date(class_date)

                if not gradebook_response.success:
                    helpers.display_response_failure(gradebook_response)
                    print("\nUnable to add this date to the gradebook.")

                    if not helpers.confirm_action(
                        "Would you like to try selecting a date again?"
                    ):
                        return MenuSignal.CANCEL
                    else:
                        continue

                print(f"\n{gradebook_response.detail}")

            return class_date

        else:
            raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")


def build_gateway_options(
    gateway_state: GatewayState,
) -> list[tuple[str, Callable[[], GatewayResponse]]]:
    """
    Build the gateway menu options from the current state.

    Inserts actions in a stable, intentional order:
      - Start recording unmarked (per-student loop), when any unmarked remain.
      - Bulk stage remaining as Present/Absent, when any unmarked remain.
      - Edit existing statuses, when the gradebook already has marks.
      - Apply staged changes, when staging is non-empty.
      - Clear all attendance for this date (always available; destructive).

    Args:
        gateway_state (GatewayState): Snapshot used to gate which actions are shown.

    Returns:
        list[tuple[str, Callable[[], GatewayResponse]]]: Label/action pairs. Each action is a no-arg callable that returns a `GatewayResponse` sentinel for dispatch.

    Notes:
        - No I/O or mutation here; this only decides which options are visible.
        - Relies on `GatewayState` convenience flags for gating semantics.
    """
    options = []

    if gateway_state.can_start_unmarked:
        options.append(
            ("Start recording unmarked", lambda: GatewayResponse.START_UNMARKED)
        )

    if gateway_state.can_mark_remaining_present:
        options.append(
            (
                "Mark remaining 'Present'",
                lambda: GatewayResponse.STAGE_REMAINING_PRESENT,
            )
        )

    if gateway_state.can_mark_remaining_absent:
        options.append(
            ("Mark remaining 'Absent'", lambda: GatewayResponse.STAGE_REMAINING_ABSENT)
        )

    if gateway_state.can_edit_existing:
        options.append(
            ("Edit existing statuses", lambda: GatewayResponse.EDIT_EXISTING)
        )

    if gateway_state.can_apply_now:
        options.append(("Apply staged changes now", lambda: GatewayResponse.APPLY_NOW))

    options.append(
        ("Clear all attendance data for this date", lambda: GatewayResponse.CLEAR_DATE)
    )

    return options


def prompt_gateway_response(
    gateway_state: GatewayState,
) -> GatewayResponse:
    """
    Display the gateway menu for a date and return the selected response.

    Behavior:
        - If there are no active students, prints a notice, calls `helpers.returning_without_changes()`, and returns `GatewayResponse.CANCEL`.
        - Otherwise, renders options from `build_gateway_options(state)` and a zero option to cancel.
        - Returns the chosen `GatewayResponse` sentinel; “0” yields `CANCEL`.

    Args:
        gateway_state (GatewayState): Snapshot providing date labels and gating flags.

    Returns:
        GatewayResponse: One of the dispatcher sentinels, or `CANCEL` on exit.

    Raises:
        RuntimeError: If the menu returns neither `MenuSignal.EXIT` nor a callable.
    """
    if gateway_state.active_roster_count == 0:
        print("There are no active students.")
        helpers.returning_without_changes()
        return GatewayResponse.CANCEL

    title = f"Attendance options for {gateway_state.date_label_long}:"
    options = build_gateway_options(gateway_state)
    zero_option = "Cancel and exit Record Attendance menu"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response is MenuSignal.EXIT:
        return GatewayResponse.CANCEL
    elif callable(menu_response):
        return menu_response()
    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")


# === edit attendance ===


def edit_attendance(gradebook: Gradebook) -> None:
    """
    Entry point for editing attendance records from the Manage Attendance menu.

    Presents the user with two editing workflows:
        1. Edit attendance by class date.
        2. Edit attendance by student.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Raises:
        RuntimeError: If the menu response type is unrecognized.

    Notes:
        - This function delegates to `edit_by_date()` or `edit_by_student()` depending on the user's selection.
        - The loop continues until the user selects the zero option ("Return and cancel"), at which point control returns to the Manage Attendance menu.
    """
    title = "Choose either a date or a student to begin editing attendance:"
    options = [
        (
            "Edit attendance by class date",
            lambda: edit_by_date(class_date=None, gradebook=gradebook),
        ),
        (
            "Edit attendance by student",
            lambda: edit_by_student(student=None, gradebook=gradebook),
        ),
    ]
    zero_option = "Return and cancel"

    while True:
        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response is MenuSignal.EXIT:
            break
        elif callable(menu_response):
            menu_response()
        else:
            raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

    helpers.returning_to("Manage Attendance menu")


def edit_by_date(class_date: datetime.date | None, gradebook: Gradebook) -> None:
    """
    Edit attendance for a single class date.

    If `class_date` is None, prompts the user to select a date (with support for off‑schedule dates per policy). Then repeatedly prompts for a `Student` and opens the edit flow for that student/date pair until the user cancels or declines to continue.

    Args:
        class_date (datetime.date | None): The class date to edit. When None, the user is prompted to choose a date first.
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Student selection uses `prompt_find_student()`; selecting the zero option returns to the caller.
        - Each student edit is delegated to `edit_attendance_record()`.
        - After each edit, the user is asked whether to continue editing for the same date.
    """
    if class_date is None:
        class_date_input = prompt_find_class_date(gradebook)

        if class_date_input is MenuSignal.CANCEL:
            return

        class_date = cast(datetime.date, class_date_input)

    print("\nYou are editing attendance records for the following date:")
    print(formatters.format_class_date_long(class_date))

    while True:
        student_input = prompt_find_student(gradebook)

        if student_input is MenuSignal.CANCEL:
            break

        student = cast(Student, student_input)

        edit_attendance_record(student, class_date, gradebook)

        if not helpers.confirm_action(
            f"Would you like to keep editing attendance records for {formatters.format_class_date_short(class_date)}?"
        ):
            break


def edit_by_student(student: Student | None, gradebook: Gradebook) -> None:
    """
    Edit attendance for a single student.

    If student is None, prompts the user to select a `Student`. Then repeatedly prompts for a class date (allowing off‑schedule dates per policy) and opens the edit flow for that student/date pair until the user cancels or declines to continue.

    Args:
        student (Student | None): The target `Student`. When None, the user is prompted to choose a student first.
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Date selection uses `prompt_find_class_date()`; selecting the zero option returns to the caller.
        - Each edit is delegated to `edit_attendance_record()`.
        - After each edit, the user is asked whether to continue editing for the same student.
    """
    if student is None:
        student_input = prompt_find_student(gradebook)

        if student_input is MenuSignal.CANCEL:
            return

        student = cast(Student, student_input)

    print("\nYou are editing attendance records for the following student:")
    print(model_formatters.format_student_oneline(student))

    while True:
        class_date_input = prompt_find_class_date(gradebook)

        if class_date_input is MenuSignal.CANCEL:
            break

        class_date = cast(datetime.date, class_date_input)

        edit_attendance_record(student, class_date, gradebook)

        if not helpers.confirm_action(
            f"Would you like to keep editing attendance records for {student.full_name}?"
        ):
            break


def edit_attendance_record(
    student: Student, class_date: datetime.date, gradebook: Gradebook
) -> None:
    """
    Edit a single attendance record for a given student and class date.

    Shows the current status, then prompts the user to mark Present, Absent, Excused, Late, or clear the record. Delegates the write to the `Gradebook`, displays the resulting message, and returns to the caller.

    Args:
        student (Student): The target `Student`.
        class_date (datetime.date): The class date being edited.
        gradebook (Gradebook): The active `Gradebook`.

    Raises:
        RuntimeError: If the menu response type is unrecognized.

    Notes:
        - The underlying Gradebook methods are expected to enforce policy (e.g., recording on off‑schedule dates is not allowed; clearing is allowed).
        - On failure, a formatted error is displayed and no changes are made.
        - No retry loop is performed here; the caller controls whether to continue editing.
    """
    print(
        f"\n{student.full_name} is currently recorded as '{student.attendance_on(class_date).value}' on {formatters.format_class_date_long(class_date)}."
    )

    title = "How would you like to mark this student now?"
    options = [
        (
            "Present",
            lambda: gradebook.mark_student_attendance_for_date(
                class_date, student, AttendanceStatus.PRESENT
            ),
        ),
        (
            "Absent",
            lambda: gradebook.mark_student_attendance_for_date(
                class_date, student, AttendanceStatus.ABSENT
            ),
        ),
        (
            "Excused",
            lambda: gradebook.mark_student_attendance_for_date(
                class_date, student, AttendanceStatus.EXCUSED_ABSENCE
            ),
        ),
        (
            "Late",
            lambda: gradebook.mark_student_attendance_for_date(
                class_date, student, AttendanceStatus.LATE
            ),
        ),
        (
            "Clear attendance record",
            lambda: gradebook.clear_student_attendance_for_date(class_date, student),
        ),
    ]
    zero_option = "Cancel editing and return"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response is MenuSignal.EXIT:
        helpers.returning_without_changes()
        return

    elif callable(menu_response):
        gradebook_response = menu_response()

        if not gradebook_response.success:
            helpers.display_response_failure(gradebook_response)
            print(
                f"\nCould not update the attendance record for {student.full_name} on {formatters.format_class_date_short(class_date)}. No changes made."
            )
            return

        print(f"\n{gradebook_response.detail}")

    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")


# === view attendance ===


def view_attendance_by_date(gradebook: Gradebook) -> None:
    """
    Display a single-date attendance report.

    Prompts the user to choose a class date, fetches attendance recorded for that date, and prints a status summary followed by a per-student list.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Only dates explicitly selected by the user are queried.
        - If no attendance has been recorded for the date, an empty-state message is shown and the function returns.
        - Missing student records (e.g., orphaned IDs) are skipped without raising.
        - Report ordering:
            - Bucket summary is determined by `helpers.display_attendance_buckets()`.
            - The per-student list is printed in the order provided by the gradebook (may be sorted upstream).
    """
    class_date_input = prompt_find_class_date(gradebook)

    if class_date_input is MenuSignal.CANCEL:
        return

    class_date = cast(datetime.date, class_date_input)

    gradebook_response = gradebook.get_attendance_for_date(class_date)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print(
            f"\nCould not generate the attendance report for {formatters.format_class_date_long(class_date)}."
        )
        return

    attendance_report = gradebook_response.data["attendance"]

    print(f"\nAttendance report for {formatters.format_class_date_long(class_date)}:")

    if attendance_report == {}:
        print("Attendance has not been recorded yet for this date.")
        return

    helpers.display_attendance_buckets(attendance_report.items())

    for student_id, attendance in attendance_report.items():
        gradebook_response = gradebook.find_student_by_uuid(student_id)

        student = (
            gradebook_response.data["record"] if gradebook_response.success else None
        )
        status = attendance.value

        if student is not None:
            print(f"... {student.full_name:<20} | {status}")


def view_attendance_by_student(gradebook: Gradebook) -> None:
    """
    Display a per-student attendance report across dates.

    Prompts the user to choose a student, fetches that student's recorded attendance, and prints each class date with the corresponding status.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Only dates with recorded attendance are shown. If none exist, an empty-state message is shown.
        - Date ordering reflects the underlying mapping.
    """
    student_input = prompt_find_student(gradebook)

    if student_input is MenuSignal.CANCEL:
        return

    student = cast(Student, student_input)

    gradebook_response = gradebook.get_attendance_for_student(student)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print(f"\nCould not generate the attendance report for {student.full_name}.")
        return

    attendance_report = gradebook_response.data["attendance"]

    print(f"\nAttendance report for {student.full_name}:")

    if attendance_report == {}:
        print("No attendance has been recorded yet for this student.")
        return

    for class_date, attendance in attendance_report.items():
        date = formatters.format_class_date_long(class_date)
        status = attendance.value
        print(f"... {date:<20} | {status}")


# === reset attendance ===


def reset_attendance_data(gradebook: Gradebook) -> None:
    """
    Presents destructive attendance reset options to the user.

    Displays a menu to choose one of three actions:
        1. Clear all attendance data for a single student.
        2. Clear all attendance data for a single date.
        3. Clear all attendance data in the gradebook.

    After each action, the user is prompted whether to continue performing resets.
    The loop ends when the user cancels or declines to continue.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Each sub-option handles its own confirmation and reporting.
        - All changes are routed through the `Gradebook` API.
        - Empty-state operations (no records to clear) are skipped with a message.
        - The course schedule remains unchanged; only attendance data is affected.
    """
    title = "Reset Attendance Data"
    options = [
        (
            "Clear all attendance data for a single student",
            lambda: reset_attendance_data_by_student(student=None, gradebook=gradebook),
        ),
        (
            "Clear all attendance data for a single date",
            lambda: reset_attendance_data_by_date(class_date=None, gradebook=gradebook),
        ),
        (
            "Delete all attendance data (entire gradebook)",
            lambda: reset_all_attendance_data(gradebook=gradebook),
        ),
    ]
    zero_option = "Cancel and return"

    while True:
        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response is MenuSignal.EXIT:
            break
        elif callable(menu_response):
            menu_response()
        else:
            raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

        if not helpers.confirm_action(
            "Would you like to continue resetting attendance data?"
        ):
            break

    helpers.returning_to("Manage Attendance menu")


def reset_attendance_data_by_student(
    student: Student | None, gradebook: Gradebook
) -> None:
    """
    Clears all recorded attendance data for a single student.

    If `Student` is None, prompts the user to select one. Displays a count of affected dates before requiring confirmation. Skips the operation if no attendance data exists for the student.

    Args:
        student (Student | None): The target `Student` record, or None to prompt selection.
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Includes records for inactive students and dates not currently in the course schedule.
        - Treats "nothing to clear" as a successful no-op with explicit messaging.
        - This action cannot be undone.
    """
    if student is None:
        student_input = prompt_find_student(gradebook)

        if student_input is MenuSignal.CANCEL:
            return

        student = cast(Student, student_input)

    gradebook_response = gradebook.get_attendance_for_student(student)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print(f"\nCould not retrieve the attendance data for {student.full_name}.")
        return

    attendance_report = gradebook_response.data["attendance"]

    if len(attendance_report) == 0:
        print("\nThere is no attendance data to remove.")
        return

    print(
        f"You are about to remove the attendance data for {student.full_name} across {len(attendance_report)} {'date' if len(attendance_report) == 1 else 'dates'}."
    )

    if not helpers.confirm_action(
        "Are you sure you want to erase this data? This action cannot be undone."
    ):
        helpers.returning_without_changes()
        return

    gradebook_response = gradebook.clear_all_attendance_data_for_student(student)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print(f"\nCould not clear all attendance data for {student.full_name}.")
        return

    print(f"\n{gradebook_response.detail}")


def reset_attendance_data_by_date(
    class_date: datetime.date | None, gradebook: Gradebook
) -> None:
    """
    Clears all recorded attendance data for a single class date.

    If `class_date` is None, prompts the user to select one. Displays a count of affected students before requiring confirmation. Skips the operation if no attendance data exists for the date.

    Args:
        class_date (datetime.date | None): The target class date, or None to prompt selection.
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Includes records for inactive students and dates not currently in the course schedule.
        - Treats "nothing to clear" as a successful no-op with explicit messaging.
        - This action cannot be undone.
    """
    if class_date is None:
        class_date_input = prompt_find_class_date(gradebook)

        if class_date_input is MenuSignal.CANCEL:
            return

        class_date = cast(datetime.date, class_date_input)

    gradebook_response = gradebook.get_attendance_for_date(class_date, False)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print(
            f"\nCould not retrieve the attendance data for {formatters.format_class_date_long(class_date)}."
        )
        return

    attendance_report = gradebook_response.data["attendance"]

    if len(attendance_report) == 0:
        print("\nThere is no attendance data to remove.")
        return

    print(
        f"You are about to remove the attendance data for {formatters.format_class_date_long(class_date)} across {len(attendance_report)} {'student' if len(attendance_report) == 1 else 'students'}."
    )

    if not helpers.confirm_action(
        "Are you sure you want to erase this data? This action cannot be undone."
    ):
        helpers.returning_without_changes()
        return

    gradebook_response = gradebook.clear_all_attendance_data_for_date(class_date)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print(
            f"\nCould not clear all attendance data for {formatters.format_class_date_long(class_date)}."
        )
        return

    print(f"\n{gradebook_response.detail}")


def reset_all_attendance_data(gradebook: Gradebook) -> None:
    """
    Clears all attendance data in the gradebook.

    Displays a warning with the scope of the operation, requires an initial yes/no confirmation, and then requires the user to type the word "DELETE" to proceed. Skips the operation if either confirmation is declined.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Deletes all attendance records for all students and all dates.
        - The course schedule and other gradebook data remain intact.
        - Treats "nothing to clear" as a successful no-op with explicit messaging.
        - This action cannot be undone.
    """
    print(
        "\nYou are about to delete all attendance data in the gradebook, erasing attendance records for all dates in the course schedule and all students in the class roster."
    )

    if not helpers.confirm_action(
        "Are you sure you want to erase this data? This action cannot be undone."
    ):
        return

    while True:
        user_confirmation = helpers.prompt_user_input_or_cancel(
            "Please type 'DELETE' to confirm this action."
        )

        if user_confirmation is MenuSignal.CANCEL:
            print("Confirmation canceled. Returning without changes.")
            return
        elif user_confirmation == "DELETE":
            break

    gradebook_response = gradebook.clear_all_attendance_data_for_gradebook()

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print("\nCould not completely clear all attendance data in the gradebook.")
        return

    print(f"\n{gradebook_response.detail}")


# === finder methods ===


def prompt_find_class_date(gradebook: Gradebook) -> datetime.date | MenuSignal:
    """
    Prompts the user to select a class date by manual entry or from the course schedule, with a retry loop.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        datetime.date | MenuSignal:
            - A selected class date on success.
            - `MenuSignal.CANCEL` if the user cancels or declines to retry after a failed attempt.

    Raises:
        RuntimeError: If an unexpected menu response type is returned.

    Notes:
        - Dates not in the course schedule are permitted for erase-only operations. The user is warned and can choose to continue or retry.
        - This function enforces a single escape hatch (CANCEL) and a consistent retry pattern.
    """
    title = formatters.format_banner_text("Class Date Selection")
    options = [
        ("Enter a date manually", lambda: prompt_class_date_or_cancel()),
        (
            "Choose a date from the course schedule",
            lambda: prompt_class_date_from_schedule(gradebook),
        ),
    ]
    zero_option = "Return and cancel"

    while True:
        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response is MenuSignal.EXIT:
            return MenuSignal.CANCEL

        elif callable(menu_response):
            class_date = menu_response()

            if class_date is MenuSignal.CANCEL:
                print("\nClass date selection canceled.")

                if not helpers.confirm_action("Would you like to try again?"):
                    return MenuSignal.CANCEL
                else:
                    continue

            if class_date not in gradebook.class_dates:
                print("\nYou have selected a date not found in the course schedule.")
                print(
                    "You will be able to erase attendance data for this date, but you cannot record attendance data until it has been added to the course schedule."
                )

                if not helpers.confirm_action(
                    "Would you like to continue with this off-schedule date?"
                ):
                    if not helpers.confirm_action(
                        "Date discarded. Would you like to try choosing a date again?"
                    ):
                        return MenuSignal.CANCEL
                    else:
                        continue

            return class_date

        else:
            raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")


def prompt_find_student(gradebook: Gradebook) -> Student | MenuSignal:
    """
    Prompts the user to locate a `Student` record by search or list selection, with a retry loop.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        Student | MenuSignal:
            - The selected `Student` on success.
            - `MenuSignal.CANCEL` if the user cancels or declines to retry after a failed attempt.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        - Offers search, active list, and inactive list as selection methods.
        - Assumes each helper return either a `Student` or `MenuSignal.CANCEL`.
        - Returns early if the user chooses to cancel or no selection is made.
    """
    title = formatters.format_banner_text("Student Selection")
    options = [
        ("Search for a student", helpers.find_student_by_search),
        ("Select from active students", helpers.find_active_student_from_list),
        ("Select from inactive students", helpers.find_inactive_student_from_list),
    ]
    zero_option = "Return and cancel"

    while True:
        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response is MenuSignal.EXIT:
            return MenuSignal.CANCEL

        elif callable(menu_response):
            student = menu_response(gradebook)

            if student is MenuSignal.CANCEL:
                print("\nStudent selection canceled.")

                if not helpers.confirm_action("Would you like to try again?"):
                    return MenuSignal.CANCEL
                else:
                    continue

            return student

        else:
            raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")
