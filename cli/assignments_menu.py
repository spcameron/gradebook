# cli/assignments_menu.py

import cli.formatters as formatters
import cli.menu_helpers as helpers
from cli.menu_helpers import MenuSignal
from datetime import datetime
from models.assignment import Assignment
from models.category import Category
from models.gradebook import Gradebook
from typing import cast, Optional
from utils.utils import generate_uuid


def run(gradebook: Gradebook) -> None:
    title = formatters.format_banner_text(f"Manage Assignments")
    options = [
        ("Add Assignment", add_assignment),
        ("Edit Assignment", edit_assignment),
        ("Remove Assignment", remove_assignment),
        ("View Individual Assignment", view_individual_assignment),
        ("List Assignments", view_multiple_assignments),
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


# === add assignment ===


def add_assignment(gradebook: Gradebook) -> None:
    while True:
        new_assignment = prompt_new_assignment(gradebook)

        if new_assignment is not None:
            gradebook.add_assignment(new_assignment)
            print(f"\n{new_assignment.name} successfully added to {gradebook.name}.")

        if not helpers.confirm_action(
            "Would you like to continue adding new assignments?"
        ):
            print(f"\nReturning to Manage Assignments menu.")
            return None


def prompt_new_assignment(gradebook: Gradebook) -> Optional[Assignment]:
    # collect user input
    name = helpers.prompt_user_input_or_cancel("Enter name (leave blank to cancel):")
    if name == MenuSignal.CANCEL:
        return None
    else:
        name = cast(str, name)

    category = prompt_linked_category(gradebook)
    if category == MenuSignal.CANCEL:
        return None
    elif category is not None:
        category = cast(Category, category)

    points_possible_str = helpers.prompt_user_input_or_cancel(
        "Enter total points possible (leave blank to cancel):"
    )
    if points_possible_str == MenuSignal.CANCEL:
        return None
    else:
        points_possible_str = cast(str, points_possible_str)

    due_date_str = helpers.prompt_user_input_or_default(
        "Enter due date (YYYY-MM-DD, leave blank for no due date):"
    )
    if due_date_str == MenuSignal.DEFAULT:
        due_date_str = None
    else:
        due_date_str = cast(str, due_date_str)

    due_time_str = (
        helpers.prompt_user_input_or_default(
            "Enter due time (24-hour HH:MM, leave blank for 23:59)"
        )
        if due_date_str
        else None
    )
    if due_time_str == MenuSignal.DEFAULT:
        due_time_str = "23:59"
    elif due_time_str is not None:
        due_time_str = cast(str, due_time_str)

    # formatting for preview
    category_name = category.name if category else "Uncategorized"

    due_date_preview = formatters.format_assignment_due_date(due_date_str, due_time_str)

    # preview and confirm
    print("\nYou are about to create the following assignment:")
    print(f"... Name: {name}")
    print(f"... Category: {category_name}")
    print(f"... Due: {due_date_preview}")
    print(f"... Points: {points_possible_str}")

    if not helpers.confirm_action("\nConfirm creation?"):
        return None

    # attempt object instantiation
    try:
        assignment_id = generate_uuid()
        points_possible = float(points_possible_str)
        due_date_iso = (
            datetime.strptime(
                f"{due_date_str} {due_time_str}", "%Y-%m-%d %H:%M"
            ).isoformat()
            if due_date_str and due_time_str
            else None
        )
        category_id = category.id if category else None

        new_assignment = Assignment(
            id=assignment_id,
            name=name,
            category_id=category_id,
            points_possible=points_possible,
            due_date_iso=due_date_iso,
        )
    except Exception as e:
        print(f"\nError: Could not create assignment ... {e}")
        return None

    return new_assignment


def prompt_linked_category(gradebook: Gradebook) -> Optional[Category] | MenuSignal:
    title = formatters.format_banner_text("Category Selection")
    options = [
        ("Search for a category", link_category_by_search),
        ("Select from active categories", link_category_from_list),
        ("Mark as 'Uncategorized'", mark_as_uncategorized),
    ]
    zero_option = "Return and cancel assignment creation"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response == MenuSignal.EXIT:
        return MenuSignal.CANCEL

    if callable(menu_response):
        return menu_response(gradebook)


def link_category_by_search(gradebook: Gradebook) -> Optional[Category] | MenuSignal:
    search_results = helpers.search_categories(gradebook)
    category = helpers.prompt_category_selection(search_results)
    return MenuSignal.CANCEL if category is None else category


def link_category_from_list(gradebook: Gradebook) -> Optional[Category] | MenuSignal:
    active_categories = gradebook.get_records(
        gradebook.categories, lambda x: x.is_active
    )
    category = helpers.prompt_category_selection(active_categories)
    return MenuSignal.CANCEL if category is None else category


def mark_as_uncategorized(_: Gradebook) -> None:
    return None


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
