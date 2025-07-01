# cli/students_menu.py

from cli.menu_helpers import display_menu, MenuSignal
from models.gradebook import Gradebook


def run(gradebook: Gradebook) -> None:
    title = f"=== MANAGE STUDENTS ==="
    options = {
        "Add Student": lambda: print("STUB: Add Student"),
        "Edit Student": lambda: print("STUB: Edit Student"),
        "Remove Student": lambda: print("STUB: Remove Student"),
        "View All Students": lambda: print("STUB: View All Students"),
    }
    zero_option = "Return to Course Menu"

    while True:
        result = display_menu(title, options, zero_option)
        if result == MenuSignal.EXIT:
            break
