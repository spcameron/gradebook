# cli/assignments_menu.py

from cli.menu_helpers import (
    confirm_action,
    display_menu,
    format_banner_text,
    prompt_record_selection,
    prompt_user_input,
    MenuSignal,
)
from models.assignment import Assignment
from models.gradebook import Gradebook
from typing import Optional


def run(gradebook: Gradebook) -> None:
    title = format_banner_text(f"Manage Assignments")
    options = [
        ("Add Assignment", add_assignment),
        ("Edit Assignment", edit_assignment),
        ("Remove Assignment", remove_assignment),
        ("View Individual Assignment", view_individual_assignment),
        ("List Assignments", view_multiple_assignments),
    ]
    zero_option = "Return to Course Manager menu"

    while True:
        menu_response = display_menu(title, options, zero_option)

        if menu_response == MenuSignal.EXIT:
            if confirm_action("Would you like to save before returning?"):
                gradebook.save(gradebook.path)
            return None

        if callable(menu_response):
            menu_response(gradebook)


# TODO:
def add_assignment(gradebook: Gradebook) -> None:
    while True:
        new_assignment = prompt_new_assignment()

        if new_assignment is not None:
            gradebook.add_assignment(new_assignment)
            print(f"\n{new_assignment.name} successfully added to {gradebook.name}.")

        if not confirm_action("Would you like to continue adding new assignments?"):
            print(f"\nReturning to Manage Assignments menu.")
            return None


# TODO:
def prompt_new_assignment() -> Optional[Assignment]:
    pass


# TODO:
def edit_assignment() -> None:
    pass


# TODO:
def remove_assignment() -> None:
    pass


# TODO:
def view_individual_assignment() -> None:
    pass


# TODO:
def view_multiple_assignments() -> None:
    pass


def search_assignments(gradebook: Gradebook) -> list[Assignment]:
    query = prompt_user_input("Search for an assignment by name:").lower()
    return gradebook.find_assignment_by_query(query)


def prompt_assignment_selection(
    search_results: list[Assignment],
) -> Optional[Assignment]:
    # prompt_record_selection()
    return prompt_record_selection(
        search_results,
        lambda x: x.name,
        # formatter
    )
