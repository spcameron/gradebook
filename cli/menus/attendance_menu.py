# cli/attendance_menu.py

"""
Manage Attendance menu for the Gradebook CLI.

Provides functions for entering & editing the class schedule; recording & editing attendance;
displaying attendance by date or by student; and resetting attendance data.
"""
import calendar
import datetime
from typing import cast

import cli.formatters as formatters
import cli.menu_helpers as helpers
from cli.menu_helpers import MenuSignal
from models.gradebook import Gradebook
from models.student import Student


def run(gradebook: Gradebook) -> None:
    """
    Top-level loop with dispatch for the Manage Attendance menu.

    Args:
        gradebook: The active Gradebook.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        The finally block guarantees a check for unsaved changes before returning.
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
    helpers.sort_and_display_course_dates(gradebook.class_dates, "Course Schedule")


def add_class_date(gradebook: Gradebook) -> None:
    while True:
        new_date = prompt_class_date_or_cancel()

        if new_date is MenuSignal.CANCEL:
            break
        else:
            new_date = cast(datetime.date, new_date)

        if preview_and_confirm_class_date(new_date):
            success = gradebook.add_class_date(new_date)
            if success:
                print(
                    f"\n{formatters.format_class_date_short(new_date)} successfully added."
                )
            else:
                print(f"\nError: Could not add date to course schedule ...")

        if not helpers.confirm_action(
            "Would you like to continue adding dates to the course schedule?"
        ):
            break

    helpers.returning_to("Manage Class Schedule menu")


def preview_and_confirm_class_date(class_date: datetime.date) -> bool:
    print("\nYou are about to add the following date to the course schedule:")
    print(formatters.format_class_date_long(class_date))

    if helpers.confirm_action("Would you like to add this date?"):
        return True
    else:
        helpers.returning_without_changes()
        return False


def remove_class_date(gradebook: Gradebook) -> None:
    while True:
        target_date = prompt_class_date_or_cancel()

        if target_date is MenuSignal.CANCEL:
            break
        else:
            target_date = cast(datetime.date, target_date)

        if confirm_and_remove_class_date(target_date, gradebook):
            success = gradebook.remove_class_date(target_date)
            if success:
                print(
                    f"\n{formatters.format_class_date_short(target_date)} successfully removed."
                )
            else:
                print(f"\nError: Could not remove date from course schedule ...")

        if not helpers.confirm_action(
            "Would you like to continue removing dates from the course schedule?"
        ):
            break

    helpers.returning_to("Manage Class Schedule menu")


def confirm_and_remove_class_date(
    class_date: datetime.date, gradebook: Gradebook
) -> bool:
    if class_date not in gradebook.class_dates:
        print(
            f"\n{formatters.format_class_date_long(class_date)} is not in the course schedule."
        )
        return False

    helpers.caution_banner()
    print("You are about to remove the following date from the course schedule:")
    print(formatters.format_class_date_long(class_date))
    print(
        "\nIf any students were previously marked absent on this date, that absence will also be deleted from their records."
    )

    if helpers.confirm_action(
        "Would you like to remove this date? This action cannot be undone."
    ):
        return True
    else:
        helpers.returning_without_changes()
        return False


def confirm_and_clear_schedule(gradebook: Gradebook) -> None:
    helpers.caution_banner()
    print("You are about to remove all dates from the course schedule.")
    print("This will also remove these dates from all student attendance records.")

    if helpers.confirm_action(
        "Are you sure you want to erase all dates from the course schedule? This action cannot be undone."
    ):
        success = gradebook.remove_all_class_dates()
        if success:
            print("\nAll dates successfully removed from the course schedule.")
        else:
            print(
                "\nError: Could not completely reset the course schedule, some dates remain ..."
            )
    else:
        helpers.returning_without_changes()

    helpers.returning_to("Manage Class Schedule menu")


# TODO: update operation result messaging to match submissions_menu.batch_add_submissions_by_assignment
def generate_recurring_schedule(gradebook: Gradebook) -> None:
    while True:
        start_date = prompt_class_date_or_cancel()

        if start_date is MenuSignal.CANCEL:
            return None
        else:
            start_date = cast(datetime.date, start_date)

        end_date = prompt_class_date_or_cancel()

        if end_date is MenuSignal.CANCEL:
            return None
        else:
            end_date = cast(datetime.date, end_date)

        if end_date < start_date:
            start_date_str = formatters.format_class_date_long(start_date)
            end_date_str = formatters.format_class_date_long(end_date)
            print(
                f"\nInvalid entry. The end date {end_date_str} comes before the start date {start_date_str}."
            )
            print("Please try again. The end date must come after the start date.")
        else:
            break

    weekdays = prompt_weekdays_or_cancel()

    if weekdays is MenuSignal.CANCEL or weekdays == []:
        return None
    else:
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
        success = gradebook.batch_add_class_dates(candidate_schedule)
        if success:
            print("\nAll dates successfully added to the course schedule.")
        else:
            print("\nError: Not all dates could be added to the course schedule ...")
    else:
        helpers.returning_without_changes()


def populate_candidate_schedule(
    start_date: datetime.date, end_date: datetime.date, weekdays: list[int]
) -> list[datetime.date]:
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
    print("\nYou have generated the following recurring course schedule:")
    helpers.sort_and_display_course_dates(course_schedule)

    if off_days:
        print("\nThe following dates have been marked as 'No Classes':")
        helpers.sort_and_display_course_dates(off_days)

    if helpers.confirm_action("Would you like to add any dates to this schedule?"):
        while True:
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
        print("\nThe following dates have been marked as 'No Classes':")
        helpers.sort_and_display_course_dates(off_days)

    if helpers.confirm_action(
        "Would you like to add these dates to the course schedule?"
    ):
        return True
    else:
        print("Discarding schedule.")
        return False


# === record attendance ===


# TODO:
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


# === data input helpers ===


def prompt_class_date_or_cancel() -> datetime.date | MenuSignal:
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
                "\nError: Invalid input. Please enter the date as YYYY-MM-DD or leave blank to cancel."
            )
        except Exception as e:
            print(f"\nError: prompt_class_date_or_cancel() ... {e}")


def prompt_weekdays_or_cancel() -> list[int] | MenuSignal:
    title = "\nSelect which days of the week you meet for class:"
    options = [
        ("Monday", lambda: 0),
        ("Tuesday", lambda: 1),
        ("Wednesday", lambda: 2),
        ("Thursday", lambda: 3),
        ("Friday", lambda: 4),
        ("Saturday", lambda: 5),
        ("Sunday", lambda: 6),
    ]
    zero_option = "Return and cancel"

    while True:
        weekdays = set()

        while True:
            if weekdays:
                print("\nYou have already selected the following days:")
                for day in sorted(weekdays):
                    print(f" - {calendar.day_name[day]}")

            menu_response = helpers.display_menu(title, options, zero_option)

            if menu_response is MenuSignal.EXIT:
                return MenuSignal.CANCEL
            elif callable(menu_response):
                weekdays.add(menu_response())
            else:
                raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

            if not helpers.confirm_action("Would you like to add another day?"):
                break

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
            return MenuSignal.CANCEL


def prompt_no_classes_dates() -> list[datetime.date]:
    print(
        "\nIf there are any days in your regular schedule where class is not scheduled,"
    )
    print("(e.g. holidays, in-service days) you may indicate those days here.")
    print(
        "\nYou can always remove specific dates from the Manage Course Schedule menu at any time."
    )

    while True:
        no_classes_dates = set()

        while True:
            new_off_day = prompt_class_date_or_cancel()

            if new_off_day is MenuSignal.CANCEL:
                break

            no_classes_dates.add(new_off_day)

            if not helpers.confirm_action(
                "Would you like to add another 'No Class' date?"
            ):
                break

        print(f"\nYou have marked the following dates as 'No Class' dates:")
        if no_classes_dates:
            helpers.sort_and_display_course_dates(no_classes_dates, "'No Class' Dates")
        else:
            print("You have not chosen any dates.")

        if no_classes_dates and helpers.confirm_action(
            "Would you like to exclude these days from your recurring schedule?"
        ):
            return list(sorted(no_classes_dates))
        elif helpers.confirm_action(
            "Would you like to start over and try choosing 'No Class' days again?"
        ):
            continue
        else:
            return []


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
