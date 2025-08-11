# cli/course_menu.py

"""
Course Manager menu for the Gradebook CLI.

Provides calls to the top-level menus for managing Students, Categories, Assignments, and Submissions,
as well as the Generate Reports menu and an option to save the gradebook.
"""

import cli.menu_helpers as helpers
import cli.model_formatters as model_formatters
import core.formatters as formatters
from cli.menu_helpers import MenuSignal
from cli.menus import (
    assignments_menu,
    attendance_menu,
    categories_menu,
    students_menu,
    submissions_menu,
)
from models.gradebook import Gradebook


# TODO: update menu when generate reports is ready
def run(gradebook: Gradebook) -> None:
    """
    Top-level loop with dispatch for the Course Manager menu.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        - The finally block guarantees a check for unsaved changes before returning.
    """
    title = formatters.format_banner_text(f"{gradebook.name} - {gradebook.term}")
    options = [
        ("Manage Students", lambda: students_menu.run(gradebook)),
        ("Manage Attendance", lambda: attendance_menu.run(gradebook)),
        ("Manage Categories", lambda: categories_menu.run(gradebook)),
        ("Manage Assignments", lambda: assignments_menu.run(gradebook)),
        ("Record Submissions", lambda: submissions_menu.run(gradebook)),
        ("Generate Reports", lambda: print("STUB: Generate Reports")),
        ("Save Gradebook", lambda: gradebook.save()),
    ]
    zero_option = "Return to Start Menu"

    try:
        while True:
            menu_response = helpers.display_menu(title, options, zero_option)

            if menu_response is MenuSignal.EXIT:
                break

            elif callable(menu_response):
                menu_response()

            else:
                raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

    finally:
        helpers.prompt_if_dirty(gradebook)

    helpers.returning_to("Start Menu")
