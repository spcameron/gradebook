# cli/course_menu.py

from cli.menu_helpers import display_menu, confirm_action
from models.gradebook import Gradebook


def run(gradebook: Gradebook) -> None:
    course_name = gradebook.metadata["name"]
    course_term = gradebook.metadata["term"]

    title = f"=== {course_name} - {course_term} ==="
    options = {
        "Manage Students": lambda: print("STUB: Manage Students"),
        "Manage Categories": lambda: print("STUB: Manage Categories"),
        "Manage Assignments": lambda: print("STUB: Manage Assignments"),
        "Record Submissions": lambda: print("STUB: Record Submissions"),
        "Generate Reports": lambda: print("STUB: Generate Reports"),
        "Save Gradebook": lambda: gradebook.save(gradebook.path),
    }
    zero_option = "Return to Start Menu"

    display_menu(title, options, zero_option)
