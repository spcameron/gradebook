# cli/attendance_menu.py

"""
Manage Attendance menu for the Gradebook CLI.

Provides functions for entering & editing the class schedule; recording & editing attendance;
displaying attendance by date or by student; and resetting attendance data.
"""
import datetime

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
        ("Generate Recurring Dates", generate_recurring_schedule),
        ("Remove a Class Date", remove_class_date),
        ("Clear Entire Schedule", confirm_and_clear_schedule),
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
    banner = formatters.format_banner_text("Course Schedule")
    print(f"\n{banner}")

    last_month_printed = (None, None)

    for class_date in sorted(gradebook.class_dates):
        current_month_and_year = (class_date.month, class_date.year)
        if current_month_and_year != last_month_printed:
            formatted_month = formatters.format_month_and_year(class_date)
            print(f"\n{formatted_month}\n")
            last_month_printed = current_month_and_year

        print(f"   {formatters.format_class_date(class_date)}")


# TODO:
def add_class_date(gradebook: Gradebook) -> None:
    pass


# TODO:
def generate_recurring_schedule(gradebook: Gradebook) -> None:
    pass


# TODO:
def remove_class_date(gradebook: Gradebook) -> None:
    pass


# TODO:
def confirm_and_clear_schedule(gradebook: Gradebook) -> None:
    pass


# === record attendance ===


# TODO:
def record_attendance(gradebook: Gradebook):
    pass


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
