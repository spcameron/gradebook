# cli/attendance_menu.py

# TODO: update file docstring
"""
Manage Attendance menu for the Gradebook CLI.

Provides functions for entering & editing the class schedule; recording & editing attendance;
displaying attendance by date or by student; and resetting attendance data.
"""

from __future__ import annotations

import calendar
import datetime
from collections import Counter
from collections.abc import Callable
from enum import Enum
from textwrap import dedent
from typing import Any, cast

import cli.formatters as formatters
import cli.menu_helpers as helpers
from cli.menu_helpers import MenuSignal
from core.attendance_stager import AttendanceStager
from core.response import ErrorCode
from models.gradebook import Gradebook
from models.student import AttendanceStatus, Student


class GatewayResponse(str, Enum):
    START_UNMARKED = "START_UNMARKED"
    # STAGE_ALL_PRESENT = "STAGE_ALL_PRESENT"
    STAGE_REMAINING_PRESENT = "STAGE_REMAINING_PRESENT"
    STAGE_REMAINING_ABSENT = "STAGE_REMAINING_ABSENT"
    EDIT_EXISTING = "EDIT_EXISTING"
    CLEAR_DATE = "CLEAR_DATE"
    APPLY_NOW = "APPLY_NOW"
    CANCEL = "CANCEL"


class GatewayState:
    """
    Immutable snapshot for the Record Attendance gateway screen.

    Build from:
    - class_date (datetime.date): date being recorded
    - active_roster (list[Student]): today's active students (objects for names/sorting)
    - gradebook_status_map (dict[str, AttendanceStatus]): Gradebook truth for the given date
    - staged_status_map (dict[str, AttendanceStatus]): Session staging

    All derived fields (preview counts, flags, samples) are computed once at init.
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

        # sample_names = []
        #
        # for student_id in sorted(
        #     unmarked_ids,
        #     key=lambda x: (roster_by_id[x].last_name, roster_by_id[x].first_name),
        # ):
        #     sample_names.append(
        #         f"{roster_by_id[student_id].last_name}, {roster_by_id[student_id].first_name}"
        #     )
        #
        #     if len(sample_names) >= 10:
        #         break
        #
        # sample_remaining = max(0, len(unmarked_ids) - len(sample_names))

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
        # self._unmarked_sample_names: list[str] = sample_names
        # self._unmarked_sample_remaining: int = sample_remaining

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

    # @property
    # def unmarked_sample_names(self) -> list[str]:
    #     return self._unmarked_sample_names
    #
    # @property
    # def unmarked_sample_remaining(self) -> int:
    #     return self._unmarked_sample_remaining

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
    Interactive submenu for managing the course's class schedule.

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
        ("Remove a Class Date", remove_class_date),
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
    Displays the current class schedule, sorted and grouped by month.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Delegates to `sort_and_display_course_dates()` to render the schedule.
        - If no class dates exist, a message will be shown instead.
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
        new_date = prompt_class_date_or_cancel()

        if new_date is MenuSignal.CANCEL:
            break
        new_date = cast(datetime.date, new_date)

        if preview_and_confirm_class_date(new_date):
            gradebook_response = gradebook.add_class_date(new_date)

            if not gradebook_response.success:
                helpers.display_response_failure(gradebook_response)
                print("\nClass date was not added.")

            else:
                print(f"\n{gradebook_response.detail}")

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
        target_date = prompt_class_date_or_cancel()

        if target_date is MenuSignal.CANCEL:
            break
        target_date = cast(datetime.date, target_date)

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

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - The user first selects a start and end date, then chooses which weekdays to include.
        - A list of candidate class dates is generated based on the recurring weekday pattern.
        - The user is optionally prompted to mark individual dates as "No Class" days (e.g., holidays).
        - The resulting schedule is previewed, and the user may manually add or remove dates.
        - Upon confirmation, the finalized dates are added to the gradebook using a batch operation.
        - Partial success is reported if some dates fail validation (e.g., due to duplicates).
        - If the user cancels at any step or declines the final confirmation, no changes are made.
        - A prompt to save is shown at the end if changes were made.
    """
    banner = formatters.format_banner_text("Recurring Schedule Generator")
    print(f"\n{banner}\n")

    range_response = prompt_start_and_end_dates()

    if range_response is MenuSignal.CANCEL:
        return
    range_response = cast(tuple[datetime.date, datetime.date], range_response)

    start_date, end_date = range_response

    weekdays = prompt_weekdays_or_cancel()

    if weekdays is MenuSignal.CANCEL:
        return
    weekdays = cast(list[int], weekdays)

    candidate_schedule = populate_candidate_schedule(start_date, end_date, weekdays)

    no_classes_dates = []

    if helpers.confirm_action(
        "Would you like to mark some of these dates as 'No Class' dates (holidays, etc.)?"
    ):
        no_classes_dates = prompt_no_classes_dates()

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
        helpers.sort_and_display_course_dates(off_days)

    if helpers.confirm_action("Would you like to add any dates to this schedule?"):
        while True:
            print("\nSelect a new date to add to the schedule:")
            new_date = prompt_class_date_or_cancel()

            if new_date is MenuSignal.CANCEL:
                break

            elif new_date not in course_schedule:
                course_schedule.append(cast(datetime.date, new_date))

            if not helpers.confirm_action(
                "Would you like to continue adding dates to the schedule?"
            ):
                break

    if helpers.confirm_action("Would you like to remove any dates from this schedule?"):
        while True:
            print("\nSelect an existing date to remove from the schedule:")
            remove_date = prompt_class_date_or_cancel()

            if remove_date is MenuSignal.CANCEL:
                break

            elif remove_date in course_schedule:
                course_schedule.remove(cast(datetime.date, remove_date))
                off_days.append(cast(datetime.date, remove_date))

            if not helpers.confirm_action(
                "Would you like to continue removing dates from the schedule?"
            ):
                break

    print("\nYou are about to add the following dates to the course schedule")
    helpers.sort_and_display_course_dates(course_schedule)

    if off_days:
        print("\nThe following dates have been marked as 'No Class' dates:")
        helpers.sort_and_display_course_dates(off_days)

    if helpers.confirm_action(
        "Would you like to add these dates to the course schedule?"
    ):
        return True

    else:
        return False


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
        user_input = helpers.prompt_user_input_or_cancel(
            "Enter the class date (YYYY-MM-DD, leave blank to cancel):"
        )

        if isinstance(user_input, MenuSignal):
            return user_input

        try:
            return datetime.datetime.strptime(user_input, "%Y-%m-%d").date()

        except (ValueError, TypeError):
            print(
                "\nInvalid input. Enter the date as YYYY-MM-DD or leave blank to cancel."
            )
            print("Please try again.")


# TODO: review and docstring
def prompt_class_date_from_schedule(gradebook: Gradebook) -> datetime.date | MenuSignal:
    def format_class_dates_with_completed_status(class_date: datetime.date) -> str:
        formatted_date = formatters.format_class_date_long(class_date)

        students_response = gradebook.get_records(
            gradebook.students,
            lambda x: x.is_active,
        )

        active_students = (
            students_response.data["records"] if students_response.success else None
        )

        has_unmarked = (
            any(
                student.attendance_on(class_date) == AttendanceStatus.UNMARKED
                for student in active_students
            )
            if active_students
            else True
        )

        return f"{formatted_date:<20}{'[ATTENDANCE TAKEN]' if not has_unmarked else ''}"

    def sort_date_by_iso_format(class_date: datetime.date) -> str:
        return class_date.isoformat()

    class_dates = sorted(gradebook.class_dates, key=sort_date_by_iso_format)

    if not class_dates:
        print("\nThere are no class dates in the course schedule to choose from.")
        print(
            "Please enter a date manually and add it to the gradebook before proceeding."
        )
        return MenuSignal.CANCEL

    formatter = format_class_dates_with_completed_status

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

        start_date = prompt_class_date_or_cancel()

        if start_date is MenuSignal.CANCEL:
            print("\nDiscarding dates and canceling schedule creator.")
            return MenuSignal.CANCEL
        start_date = cast(datetime.date, start_date)

        print("\nWhat is the last class date?")

        end_date = prompt_class_date_or_cancel()

        if end_date is MenuSignal.CANCEL:
            print("\nDiscarding dates and canceling schedule creator.")
            return MenuSignal.CANCEL
        end_date = cast(datetime.date, end_date)

        start_date_str = formatters.format_class_date_long(start_date)
        end_date_str = formatters.format_class_date_long(end_date)

        print("\nYou have entered the following dates for your course schedule:")
        print(f"... Beginning on {start_date_str}")
        print(f"... Ending on {end_date_str}")

        if not start_date < end_date:
            print("\nInvalid entry. The end date must come after the start date.")
            print("Please try again.")
            continue

        if helpers.confirm_action("Would you like to proceed using this date range?"):
            return (start_date, end_date)

        elif helpers.confirm_action(
            "Would you like to start over and try choosing dates again?"
        ):
            continue

        else:
            print("\nDiscarding dates and canceling schedule creator.")
            return MenuSignal.CANCEL


def prompt_weekdays_or_cancel() -> list[int] | MenuSignal:
    """
    Prompts the user to select one or more weekdays for the recurring class schedule.

    Returns:
        - A sorted list of integers representing weekdays (0=Monday to 6=Sunday) if confirmed.
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
        print("\nSelect which days of the week you meet for class:")

        weekdays = set()

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
                print("\nDiscarding days and canceling schedule creator.")
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
            print("\nDiscarding days and canceling schedule creator.")
            return MenuSignal.CANCEL


def prompt_no_classes_dates() -> list[datetime.date]:
    """
    Prompts the user to mark specific dates as 'No Class' days to exclude from the recurring schedule.

    Returns:
        A sorted list of `datetime.date` objects marked for omission.

    Notes:
        - Dates are entered one at a time using the standard date prompt.
        - Previously selected dates are shown before each new entry.
        - Duplicate entries are ignored.
        - If no dates are selected, the user may choose to retry or proceed with none.
        - Dates are not validated against the generated schedule in this prompt.
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
        print("\nSelect which dates to omit from the recurring schedule:")

        no_class_dates = set()

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
            print(f"\nYou have marked the following dates as 'No Class' dates:")
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


# TODO: checkpoint
def record_attendance(gradebook: Gradebook) -> None:
    # TODO: docstring
    def refresh_state(date: datetime.date) -> GatewayState | None:
        students_response = gradebook.get_records(
            dictionary=gradebook.students,
            predicate=lambda x: x.is_active,
        )

        if not students_response.success:
            helpers.display_response_failure(students_response)
            print("Unable to retrieve active students.")
            helpers.returning_without_changes()
            return

        active_students = students_response.data["records"]

        attendance_response = gradebook.get_attendance_for_date(
            class_date=date,
            active_only=True,
        )

        if not attendance_response.success:
            helpers.display_response_failure(attendance_response)
            print(f"\nUnable to retrieve attendance data.")
            helpers.returning_without_changes()
            return

        gradebook_status_map = attendance_response.data["attendance"]

        return GatewayState(
            class_date=date,
            active_roster=active_students,
            gradebook_status_map=gradebook_status_map,
            staged_status_map=stager.status_map,
        )

    # TODO: docstring
    def start_unmarked(state: GatewayState) -> None:
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
                ("Skip This Student", MenuSignal.SKIP),
            ]
            zero_option = "Cancel and Stop Recording Attendance"

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
                            "Apply These Changes Now and Return",
                            lambda: MenuSignal.APPLY,
                        ),
                        (
                            "Discard These Changes and Return",
                            lambda: MenuSignal.DISCARD,
                        ),
                        ("Keep These Changes and Return", lambda: MenuSignal.KEEP),
                    ]
                    bail_zero_option = "Continue Recording Attendance"

                    bail_response = helpers.display_menu(
                        bail_title, bail_options, bail_zero_option
                    )

                    if bail_response is MenuSignal.EXIT:
                        continue

                    elif callable(bail_response):
                        bail_signal = bail_response()

                        match bail_signal:
                            case MenuSignal.APPLY:
                                apply_now()
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
                    stager.stage(student_id, status)
                    staged_count += 1
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
                apply_now()
                return

            else:
                print(
                    "You may apply these changes later by selecting 'Apply Staged Changes Now' from the Record Attendance menu."
                )
                return

    # TODO:
    def apply_now() -> None:
        pass

    # resolve class date
    class_date = resolve_class_date(gradebook)

    if class_date is MenuSignal.CANCEL:
        print("\nDate selection canceled.")
        helpers.returning_without_changes()
        return

    class_date = cast(datetime.date, class_date)

    # initiate stager object
    stager = AttendanceStager()

    # main loop

    """
    1. build gateway state
        - pull DB truth for the date
        - compute preview with stager overlay
        - produce a simple GatewayStager object

    2. show gateway
        - render the menu from the state
        - return a GatewayChoice

    3. dispatch on choice
        - START_UNMARKED -> run the unmarked loop (updates stager) then return to step 1
        - STAGE_ALL_PRESENT/STAGE_REMAINING_ABSENT -> update stager, toast, return to step 1
        - EDIT_EXISTING -> warn and clear stager, run edit flow, then return to step 1
            - Edit prompts guardrail apply/discard/return
        - CLEAR_DATE -> confirm, clear DB marks for the date, return to step 1
        - APPLY_NOW -> apply batch with stager.pending(), show results, then exit
        - CANCEL -> if no staging, returning_without_changes() and exit; if staging, offer the three-way Apply now (apply & exit) / Discard (clear stager & exit) / Return (back to step 1)
    """

    while True:
        gateway_state = refresh_state(class_date)

        if gateway_state is None:
            return

        gateway_response = prompt_gateway_response(gateway_state)

        match gateway_response:
            case GatewayResponse.START_UNMARKED:
                """
                goal: one-by-one pass over the unmarked students

                1. compute target_ids = gateway_state.unmarked_ids
                2. enter the per-student loop
                    - present/absent/excused/late -> stager.stage(id, status)
                    - skip -> no staging
                    - cancel -> three-way: apply now / discard staged / return to loop
                3. on exhausting the list: show a small toast
                    - ("staged updates for N students")
                    - view buckets?

                continue
                """
                start_unmarked(gateway_state)
                continue

            # TODO: review, docstring, probably extract generalized version
            case GatewayResponse.STAGE_REMAINING_PRESENT:
                """
                goal: bulk stage Present for unmarked students

                1. compute target_ids = gateway_state.unmarked_ids
                2. stager.bulk_stage(target_ids, PRESENT, overwrite=True)
                3. toast: "Staged Present for {len(target_ids)} students."

                continue
                """
                target_ids = gateway_state.unmarked_ids

                stager.bulk_stage(
                    student_ids=target_ids,
                    status=AttendanceStatus.PRESENT,
                    overwrite=True,
                )

                count = len(target_ids)

                print(
                    f"\nStaged {count} {'student' if count == 1 else 'students'} as 'Present'."
                )

                # helpers.staged_changes_warning()

                continue

            # TODO: review, docstring, probably extract generalized version
            case GatewayResponse.STAGE_REMAINING_ABSENT:
                """
                Identical to above but ABSENT
                """
                target_ids = gateway_state.unmarked_ids

                stager.bulk_stage(
                    student_ids=target_ids,
                    status=AttendanceStatus.ABSENT,
                    overwrite=True,
                )

                count = len(target_ids)

                print(
                    f"\nStaged {count} {'student' if count == 1 else 'students'} as 'Absent'."
                )

                # helpers.staged_changes_warning()

                continue

            # TODO:
            case GatewayResponse.EDIT_EXISTING:
                """
                goal: scapel flow; gradebook writes happen immediately

                pre check:
                    - if stager.is_empty() -> go straight to edit
                    - else prompt:
                        - apply staged now -> do the apply_now branch (below) and exit after results, force user to explicitly re-enter Edit
                        - discard staged and enter edit -> stager.clear() then run Edit
                        - stay in Record -> skip Edit; return to gateway loop

                edit flow:
                    - run edit_attendance_flow(class_date). It writes immediately.
                    - on return, do nothing else here; the next loop rebuild picks up changes
                """
                pass

            # TODO:
            case GatewayResponse.APPLY_NOW:
                """
                goal: commit what's staged, then exit

                1. re-fetch fresh inputs for consistency:
                    - active roster
                    - active ids
                    - gradebook_status_map

                2. build apply payload:
                    - changes = stager.pending(active_ids, gradebook_status_map) (diff-only, active-only)
                    - if not changes: show "nothing to apply" and continue

                3. response = gradebook.batch_mark_attendance(class_date, changes)
                    - on failure, show failure detail, stay in the loop
                    - on success, show tallies
                        - if failed, list names & reasons, optionally offer retry failed only

                4. stager.clear()

                5. helpers.returning_to() and exit orchestrator
                """
                pass

            # TODO:
            case GatewayResponse.CLEAR_DATE:
                """
                goal: wipe gradebook marks for ALL students, leave staging as the user chooses

                1. if stager.is_empty():
                    - confirm "clear attendance for {date} for all students"
                    - if confirmed: gradebook.clear_attendance_for_date(class_date)
                        - on success: toast "cleared" -> continue (rebuilds)
                        - on failure: show error -> continue

                2. if staging exists:
                    - preserve staged and clear gradebook -> call clear; keep stager; continue
                    - discard staged and clear -> stager.clear(); then clear gb; continue
                    - cancel -> do nothing, continue

                3. prompt to apply changes now?
                """
                pass

            # TODO:
            case GatewayResponse.CANCEL:
                """
                goal: exit or resolve staged work

                1. if stager.is_empty() -> helpers.returning_without_changes() and exit

                2. if staging exists:
                    - apply now -> run apply_now branch and exit
                    - discard staged -> stager.clear(), helpers.returning_without_changes()
                    - return to gateway -> do nothing, continue
                """
                pass

            case _:
                raise RuntimeError(
                    f"Unexpected GatewayResponse recieved: {gateway_response}"
                )


# TODO: review and docstring
def resolve_class_date(gradebook: Gradebook) -> datetime.date | MenuSignal:
    title = "\nSelect which date to record attendance for:"
    options = [
        ("Enter the date manually", lambda: prompt_class_date_or_cancel()),
        (
            "Choose a date from the course schedule",
            lambda: prompt_class_date_from_schedule(gradebook),
        ),
    ]
    zero_option = "Return and cancel recording attendance"

    while True:
        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response is MenuSignal.EXIT:
            return MenuSignal.CANCEL

        elif callable(menu_response):
            class_date = menu_response()

            if isinstance(class_date, MenuSignal):
                print("\nDate selection canceled.")

                if not helpers.confirm_action("Would you like to try again?"):
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
                    return MenuSignal.CANCEL

                gradebook_response = gradebook.add_class_date(class_date)

                if not gradebook_response.success:
                    helpers.display_response_failure(gradebook_response)
                    print("\nUnable to record attendance for this date.")
                    return MenuSignal.CANCEL

                print(f"\n{gradebook_response.detail}")

            return class_date

        else:
            raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")


# TODO: docstring
def build_gateway_options(
    gateway_state: GatewayState,
) -> list[tuple[str, Callable[..., Any]]]:
    options = []

    if gateway_state.can_start_unmarked:
        options.append(
            ("Start Recording Unmarked", lambda: GatewayResponse.START_UNMARKED)
        )

    if gateway_state.can_mark_remaining_present:
        options.append(
            (
                "Mark Remaining 'Present'",
                lambda: GatewayResponse.STAGE_REMAINING_PRESENT,
            )
        )

    if gateway_state.can_mark_remaining_absent:
        options.append(
            ("Mark Remaining 'Absent'", lambda: GatewayResponse.STAGE_REMAINING_ABSENT)
        )

    if gateway_state.can_edit_existing:
        options.append(
            ("Edit Existing Statuses", lambda: GatewayResponse.EDIT_EXISTING)
        )

    if gateway_state.can_apply_now:
        options.append(("Apply Staged Changes Now", lambda: GatewayResponse.APPLY_NOW))

    options.append(
        ("Clear All Attendance Data For This Date", lambda: GatewayResponse.CLEAR_DATE)
    )

    return options


# TODO: docstring
def prompt_gateway_response(
    gateway_state: GatewayState,
) -> GatewayResponse:
    if gateway_state.active_roster_count == 0:
        print("There are no active students.")
        helpers.returning_without_changes()
        return GatewayResponse.CANCEL

    # TODO:
    # "There is/are 14 students remaining unmarked."
    # "(e.g., Potter, Weasley, Grainger and 4 more)"
    helpers.display_remaining_unmarked_preview(gateway_state)

    title = f"Attendance options for {gateway_state.date_label_long}:"
    options = build_gateway_options(gateway_state)
    zero_option = "Cancel"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response is MenuSignal.EXIT:
        return GatewayResponse.CANCEL

    elif callable(menu_response):
        return menu_response()

    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")


# def record_attendance_deprecated(gradebook: Gradebook) -> None:
#     # perhaps offer to select date from course schedule, or better yet,
#     # the next date in the course schedule that does not have attendance recorded
#
#     print("\nSelect which date to record attendance for:")
#
#     class_date = prompt_class_date_or_cancel()
#
#     if class_date is MenuSignal.CANCEL:
#         return
#     class_date = cast(datetime.date, class_date)
#
#     print(
#         f"\nYou are recording attendance for {formatters.format_class_date_long(class_date)}."
#     )
#
#     if class_date not in gradebook.class_dates:
#         print(
#             f"\n{formatters.format_class_date_short(class_date)} is not in the course schedule yet."
#         )
#
#         if not helpers.confirm_action(
#             "Do you want to add it to the schedule and proceed with recording attendance?"
#         ):
#             helpers.returning_without_changes()
#             return
#
#         add_response = gradebook.add_class_date(class_date)
#
#         if not add_response.success:
#             helpers.display_response_failure(add_response)
#             print("\nCould not record attendance.")
#             helpers.returning_without_changes()
#             return
#
#         print(f"\n{add_response.detail}")
#
#     students_response = gradebook.get_records(gradebook.students, lambda x: x.is_active)
#
#     if not students_response.success:
#         helpers.display_response_failure(students_response)
#         print("\nCould not retrieve active student roster.")
#         helpers.returning_without_changes()
#         return
#
#     active_students = students_response.data["records"]
#
#     if not active_students:
#         print("\nThere are no active students.")
#         helpers.returning_without_changes()
#         return
#
#     for student in sorted(active_students, key=lambda x: (x.last_name, x.first_name)):
#         # record attendance sequence here
#         pass
#
#     helpers.display_attendance_summary(class_date, gradebook)


# === edit attendance ===


# TODO:
def edit_attendance(gradebook: Gradebook):
    pass


# === view attendance ===


# TODO:
def view_attendance_by_date(gradebook: Gradebook):
    pass


# TODO:
def view_attendance_by_student(gradebook: Gradebook):
    pass


# === reset attendance ===


# TODO:
def reset_attendance_data(gradebook: Gradebook):
    pass


# === finder methods ===


# TODO: review and docstring
def prompt_find_student(gradebook: Gradebook) -> Student | MenuSignal:
    title = formatters.format_banner_text("Student Selection")
    options = [
        ("Search for a student", helpers.find_student_by_search),
        ("Select from active students", helpers.find_active_student_from_list),
    ]
    zero_option = "Return and cancel"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response is MenuSignal.EXIT:
        return MenuSignal.CANCEL
    elif callable(menu_response):
        return menu_response(gradebook)
    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")
