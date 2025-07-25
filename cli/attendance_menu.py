# cli/attendance_menu.py

"""
Manage Attendance menu for the Gradebook CLI.

Provides functions for entering & editing the class schedule; recording & editing attendance;
displaying attendance by date or by student; and resetting attendance data.
"""

import cli.formatters as formatters
import cli.menu_helpers as helpers
from cli.menu_helpers import MenuSignal
from models.gradebook import Gradebook
from models.student import Student


def run(gradebook: Gradebook) -> None:
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


# TODO:
def manage_class_schedule(gradebook: Gradebook):
    pass


# TODO:
def record_attendance(gradebook: Gradebook):
    pass


# TODO:
def edit_attendance(gradebook: Gradebook):
    pass


# TODO:
def view_attendance_by_date(gradebook: Gradebook):
    pass


# TODO:
def view_attendance_by_student(gradebook: Gradebook):
    pass


# TODO:
def reset_attendance_data(gradebook: Gradebook):
    pass
