# cli/course_menu.py

from cli.menu_helpers import display_menu, format_banner_text, MenuSignal
from cli import students_menu
from models.gradebook import Gradebook
from typing import Callable


def run(gradebook: Gradebook) -> None:
    course_name = gradebook.metadata["name"]
    course_term = gradebook.metadata["term"]

    title = format_banner_text(f"{course_name} - {course_term}")
    options = [
        ("Manage Students", lambda: students_menu.run(gradebook)),
        ("Manage Categories", lambda: print("STUB: Manage Categories")),
        ("Manage Assignments", lambda: print("STUB: Manage Assignments")),
        ("Record Submissions", lambda: print("STUB: Record Submissions")),
        ("Generate Reports", lambda: print("STUB: Generate Reports")),
        ("Save Gradebook", lambda: gradebook.save(gradebook.path)),
    ]
    zero_option = "Return to Start Menu"

    while True:
        menu_response = display_menu(title, options, zero_option)

        if menu_response == MenuSignal.EXIT:
            break

        if isinstance(menu_response, Callable):
            menu_response()
