# cli/submissions_menu.py

import cli.formatters as formatters
import cli.menu_helpers as helpers
from cli.menu_helpers import MenuSignal
from models.assignment import Assignment
from models.gradebook import Gradebook
from models.student import Student
from typing import cast, Callable, Optional
from utils.utils import generate_uuid


def run(gradebook: Gradebook) -> None:
    title = formatters.format_banner_text("Manage Submissions")
    options = [
        ("Add Single Submission", add_single_submission),
        ("Batch Enter Submissions by Assignment", add_submissions_by_assignment),
        ("Edit Submission", edit_submission),
        ("Remove Submission", remove_submission),
        ("View Submissions", view_submissions_menu),
    ]
    zero_option = "Return to Course Manager menu"

    while True:
        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response == MenuSignal.EXIT:
            if helpers.confirm_action("Would you like to save before returning?"):
                gradebook.save(gradebook.path)
            return None

        if callable(menu_response):
            menu_response(gradebook)


# === add submission ===


def add_single_submission(gradebook: Gradebook) -> None:
    pass


def add_submissions_by_assignment(gradebook: Gradebook) -> None:
    pass


# === edit submission ===


# def get_editable_fields() -> (
#     list[tuple[str, Callable[[Submission, Gradebook], Optional[MenuSignal]]]]
# ):
#     pass


def edit_submission(gradebook: Gradebook) -> None:
    pass


# === remove submission ===


def remove_submission(gradebook: Gradebook) -> None:
    pass


# === view submission ===


def view_submissions_menu(gradebook: Gradebook) -> None:
    pass
