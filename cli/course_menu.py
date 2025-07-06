# cli/course_menu.py

from cli import categories_menu, students_menu
from cli.menu_helpers import (
    confirm_action,
    display_menu,
    format_banner_text,
    MenuSignal,
)
from models.gradebook import Gradebook


def run(gradebook: Gradebook) -> None:
    course_name = gradebook.metadata["name"]
    course_term = gradebook.metadata["term"]

    title = format_banner_text(f"{course_name} - {course_term}")
    options = [
        ("Manage Students", lambda: students_menu.run(gradebook)),
        ("Manage Categories", lambda: categories_menu.run(gradebook)),
        ("Manage Assignments", lambda: print("STUB: Manage Assignments")),
        ("Record Submissions", lambda: print("STUB: Record Submissions")),
        ("Generate Reports", lambda: print("STUB: Generate Reports")),
        ("Save Gradebook", lambda: gradebook.save(gradebook.path)),
    ]
    zero_option = "Return to Start Menu"

    while True:
        menu_response = display_menu(title, options, zero_option)

        if menu_response == MenuSignal.EXIT:
            if confirm_action("Would you like save before returning?"):
                gradebook.save(gradebook.path)
            return None

        if callable(menu_response):
            menu_response()
