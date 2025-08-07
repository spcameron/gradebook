# cli/attendance_menu.py

# TODO: update file docstring
"""
Manage Attendance menu for the Gradebook CLI.

Provides functions for entering & editing the class schedule; recording & editing attendance;
displaying attendance by date or by student; and resetting attendance data.
"""

import calendar
import datetime
from textwrap import dedent
from typing import cast

import cli.formatters as formatters
import cli.menu_helpers as helpers
from cli.menu_helpers import MenuSignal
from core.response import ErrorCode
from models.gradebook import Gradebook
from models.student import Student


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

        added_dates = gradebook_response.data["added"]
        skipped_dates = gradebook_response.data["skipped"]

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
def record_attendance(gradebook: Gradebook):
    class_date = prompt_class_date_or_cancel()

    if class_date is MenuSignal.CANCEL:
        return None
    else:
        class_date = cast(datetime.date, class_date)

    print(
        f"\nYou are logging attendance for {formatters.format_class_date_short(class_date)}."
    )

    if class_date not in gradebook.class_dates:
        print(
            f"\n{formatters.format_class_date_long(class_date)} is not in the course schedule yet."
        )

        if not helpers.confirm_action(
            "Do you want to add it to the schedule and proceed with recording attendance?"
        ):
            helpers.returning_without_changes()
            return None

        success = gradebook.add_class_date(class_date)

        if success:
            print(
                f"\n{formatters.format_class_date_short(class_date)} successfully added."
            )
        else:
            print(f"\nError: Could not add date to course schedule ...")
            return None

    active_students = gradebook.get_records(gradebook.students, lambda x: x.is_active)

    for student in sorted(active_students, key=lambda x: (x.last_name, x.first_name)):
        if not helpers.confirm_action(
            f"{student.full_name}: 'y' for present, 'n' for absent:"
        ):
            gradebook.mark_student_absent(student, class_date)

    helpers.display_attendance_summary(class_date, gradebook)


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
