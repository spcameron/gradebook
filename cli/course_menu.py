# cli/course_menu.py

from cli import (
    assignments_menu,
    categories_menu,
    students_menu,
)
import cli.formatters as formatters
import cli.menu_helpers as helpers
from cli.menu_helpers import MenuSignal
from models.gradebook import Gradebook


def run(gradebook: Gradebook) -> None:
    title = formatters.format_banner_text(f"{gradebook.name} - {gradebook.term}")
    options = [
        ("Manage Students", lambda: students_menu.run(gradebook)),
        ("Manage Categories", lambda: categories_menu.run(gradebook)),
        ("Manage Assignments", lambda: assignments_menu.run(gradebook)),
        ("Record Submissions", lambda: print("STUB: Record Submissions")),
        ("Generate Reports", lambda: print("STUB: Generate Reports")),
        ("Save Gradebook", lambda: gradebook.save(gradebook.path)),
    ]
    zero_option = "Return to Start Menu"

    while True:
        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response == MenuSignal.EXIT:
            if helpers.confirm_action("Would you like save before returning?"):
                gradebook.save(gradebook.path)
            return None

        if callable(menu_response):
            menu_response()
