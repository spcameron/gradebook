# cli/assignments_menu.py

import cli.formatters as formatters
import cli.menu_helpers as helpers
from cli.menu_helpers import MenuSignal
from datetime import datetime
from models.assignment import Assignment
from models.category import Category
from models.gradebook import Gradebook
from typing import cast, Callable, Optional
from utils.utils import generate_uuid


def run(gradebook: Gradebook) -> None:
    title = formatters.format_banner_text(f"Manage Assignments")
    options = [
        ("Add Assignment", add_assignment),
        ("Edit Assignment", edit_assignment),
        ("Remove Assignment", remove_assignment),
        ("View Assignments", view_assignments_menu),
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
            print("\nReturning to Manage Assignments menu.")
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

    due_date_str, due_time_str = prompt_due_date()

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
        due_date = (
            datetime.strptime(f"{due_date_str} {due_time_str}", "%Y-%m-%d %H:%M")
            if due_date_str and due_time_str
            else None
        )
        category_id = category.id if category else None

        new_assignment = Assignment(
            id=assignment_id,
            name=name,
            category_id=category_id,
            points_possible=points_possible,
            due_date=due_date,
        )
    except Exception as e:
        print(f"\nError: Could not create assignment ... {e}")
        return None

    return new_assignment


def prompt_due_date() -> tuple[Optional[str], Optional[str]]:
    due_date_str = helpers.prompt_user_input_or_default(
        "Enter due date (YYYY-MM-DD, leave blank for no due date):"
    )
    if due_date_str == MenuSignal.DEFAULT:
        due_date_str = None
    else:
        due_date_str = cast(str, due_date_str)

    due_time_str = (
        helpers.prompt_user_input_or_default(
            "Enter due time (24-hour HH:MM, leave blank for 23:59):"
        )
        if due_date_str
        else None
    )
    if due_time_str == MenuSignal.DEFAULT:
        due_time_str = "23:59"
    elif due_time_str is not None:
        due_time_str = cast(str, due_time_str)

    return (due_date_str, due_time_str)


def prompt_linked_category(gradebook: Gradebook) -> Optional[Category] | MenuSignal:
    title = formatters.format_banner_text("Category Selection")
    options = [
        ("Search for a category", link_category_by_search),
        ("Select from active categories", link_category_from_list),
        ("Mark as 'Uncategorized'", mark_as_uncategorized),
    ]
    zero_option = "Return and cancel"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response == MenuSignal.EXIT:
        return MenuSignal.CANCEL

    if callable(menu_response):
        return menu_response(gradebook)


def link_category_by_search(gradebook: Gradebook) -> Optional[Category] | MenuSignal:
    search_results = helpers.search_categories(gradebook)
    category = helpers.prompt_category_selection_from_search(search_results)
    return MenuSignal.CANCEL if category is None else category


def link_category_from_list(gradebook: Gradebook) -> Optional[Category] | MenuSignal:
    active_categories = gradebook.get_records(
        gradebook.categories, lambda x: x.is_active
    )
    category = helpers.prompt_category_selection_from_list(
        active_categories, "Active Categories"
    )
    return MenuSignal.CANCEL if category is None else category


def mark_as_uncategorized(_: Gradebook) -> None:
    return None


# === edit assignment ===


def get_editable_fields() -> (
    list[tuple[str, Callable[[Assignment, Gradebook], Optional[MenuSignal]]]]
):
    return [
        ("Name", edit_name_and_confirm),
        ("Linked Category", edit_linked_category_and_confirm),
        ("Due Date", edit_due_date_and_confirm),
        ("Points Possible", edit_points_possible_and_confirm),
        ("Archived Status", edit_active_status_and_confirm),
    ]


def edit_assignment(gradebook: Gradebook) -> None:
    search_results = helpers.search_assignments(gradebook)
    assignment = helpers.prompt_assignment_selection_from_search(search_results)

    if not assignment:
        return None

    title = formatters.format_banner_text("Editable Fields")
    options = get_editable_fields()
    zero_option = "Return without changes"

    while True:
        print("\nYou are viewing the following assignment:")
        print(formatters.format_assignment_oneline(assignment))

        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response == MenuSignal.EXIT:
            helpers.returning_without_changes()
            return None

        if callable(menu_response):
            menu_response(assignment, gradebook)

        if not helpers.confirm_action(
            "Would you like to continue editing this assignment?"
        ):
            print("\nReturning to Manage Assignments menu.")
            return None


def edit_name_and_confirm(assignment: Assignment, gradebook: Gradebook) -> None:
    current_name = assignment.name
    new_name = helpers.prompt_user_input_or_cancel(
        "Enter a new name (leave blank to cancel):"
    )

    if new_name == MenuSignal.CANCEL:
        helpers.returning_without_changes()
        return None
    else:
        new_name = cast(str, new_name)

    print(
        f"\nCurrent assignment name: {current_name} ... New assignment name: {new_name}"
    )

    save_change = helpers.confirm_action("Do you want to save this change?")

    if not save_change:
        helpers.returning_without_changes()
        return None

    assignment.name = new_name
    gradebook.save(gradebook.path)
    print("\nName successfully updated.")


def edit_linked_category_and_confirm(
    assignment: Assignment, gradebook: Gradebook
) -> None:
    current_category = (
        gradebook.find_category_by_uuid(assignment.category_id)
        if assignment.category_id
        else None
    )
    new_category = prompt_linked_category

    if new_category == MenuSignal.CANCEL:
        helpers.returning_without_changes()
        return None
    elif new_category is not None:
        new_category = cast(Category, new_category)

    current_category_preview = (
        current_category.name if current_category else "Uncategorized"
    )
    new_category_preview = new_category.name if new_category else "Uncategorized"

    print(
        f"\nCurrent category: {current_category_preview} ... New category: {new_category_preview}"
    )

    save_change = helpers.confirm_action("Do you want to save this change?")

    if not save_change:
        helpers.returning_without_changes()
        return None

    assignment.category_id = new_category.id if new_category else None
    gradebook.save(gradebook.path)
    print("\nCategory successfully updated.")


def edit_due_date_and_confirm(assignment: Assignment, gradebook: Gradebook) -> None:
    current_due_date_str, current_due_time_str = (
        assignment.due_date_str,
        assignment.due_time_str,
    )
    new_due_date_str, new_due_time_str = prompt_due_date()

    current_due_date_preview = formatters.format_assignment_due_date(
        current_due_date_str, current_due_time_str
    )
    new_due_date_preview = formatters.format_assignment_due_date(
        new_due_date_str, new_due_time_str
    )

    print(
        f"\nCurrent due date: {current_due_date_preview} ... New due date: {new_due_date_preview}"
    )

    save_change = helpers.confirm_action("Do you want to save this change?")

    if not save_change:
        helpers.returning_without_changes()
        return None

    try:
        due_date_dt = (
            datetime.strptime(
                f"{new_due_date_str} {new_due_time_str}", "%Y-%m-%d %H:%M"
            )
            if new_due_date_str and new_due_time_str
            else None
        )
        assignment.due_date_dt = due_date_dt
        gradebook.save(gradebook.path)
        print("\nDue date successfully updated.")
    except Exception as e:
        print(f"\nError: Could not update the due date ... {e}")
        return None


def edit_points_possible_and_confirm(
    assignment: Assignment, gradebook: Gradebook
) -> None:
    current_points_possible = str(assignment.points_possible)
    new_points_possible = helpers.prompt_user_input_or_cancel(
        "Enter total points possible (leave blank to cancel):"
    )

    if new_points_possible == MenuSignal.CANCEL:
        return None
    else:
        new_points_possible = cast(str, new_points_possible)

    print(
        f"\nCurrent points possible: {current_points_possible} ... New points possible: {new_points_possible}"
    )

    save_change = helpers.confirm_action("Do you want to save this change?")

    if not save_change:
        helpers.returning_without_changes()
        return None

    try:
        new_points_possible = float(new_points_possible)
        assignment.points_possible = new_points_possible
        gradebook.save(gradebook.path)
        print("\nPoints possible successfully updated.")
    except ValueError as e:
        print(f"\nError: Could not update the points possible ... {e}")
        return None


def edit_active_status_and_confirm(
    assignment: Assignment, gradebook: Gradebook
) -> None:
    print(f"\nThis assignment is currently {assignment.status}")

    if not helpers.confirm_action("Would you like to edit the archived status?"):
        helpers.returning_without_changes()
        return None

    if assignment.is_active:
        confirm_and_archive(assignment, gradebook)
    else:
        confirm_and_reactivate(assignment, gradebook)


# === remove assignment ===


def remove_assignment(gradebook: Gradebook) -> None:
    search_results = helpers.search_assignments(gradebook)
    assignment = helpers.prompt_assignment_selection_from_search(search_results)

    if not assignment:
        return None

    print("\nYou are viewing the following assignment:")
    print(formatters.format_assignment_oneline(assignment))

    title = "What would you like to do?"
    options = [
        (
            "Permanently remove this assignment (deletes all linked submissions)",
            confirm_and_remove,
        ),
        (
            "Archive this assignment instead (preserves all linked submissions)",
            confirm_and_archive,
        ),
    ]
    zero_option = "Return to Manage Assignments menu"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response == MenuSignal.EXIT:
        helpers.returning_without_changes()
        return None

    if callable(menu_response):
        menu_response(assignment, gradebook)


def confirm_and_remove(assignment: Assignment, gradebook: Gradebook) -> None:
    caution_banner = formatters.format_banner_text("CAUTION!")
    print(f"\n{caution_banner}")
    print("You are about to permanently delete the following assignment:")
    print(f"{formatters.format_assignment_oneline(assignment)}")
    print("\nThis will also delete all linked submissions.")

    confirm_deletion = helpers.confirm_action(
        "Are you sure you want to permanently delete this assignment? This action cannot be undone."
    )

    if not confirm_deletion:
        helpers.returning_without_changes()
        return None

    gradebook.remove_assignment(assignment)
    gradebook.save(gradebook.path)
    print("\nAssignment successfully removed from Gradebook.")


def confirm_and_archive(assignment: Assignment, gradebook: Gradebook) -> None:
    if not assignment.is_active:
        print("\nThis assignment has already been archived.")
        return None

    print(
        "\nArchiving an assignment is a safe way to deactivate an assignment without losing data."
    )
    print("You are about to archive the following assignment:")
    print(f"{formatters.format_assignment_oneline(assignment)}")
    print("\nThis will preserve all linked submissions,")
    print("but they will no longer appear in reports or grade calculations.")

    confirm_archiving = helpers.confirm_action(
        "Are you sure you want to archive this assignment?"
    )

    if not confirm_archiving:
        helpers.returning_without_changes()
        return None

    assignment.toggle_archived_status()
    gradebook.save(gradebook.path)
    print("\nAssignment successfully archived.")


def confirm_and_reactivate(assignment: Assignment, gradebook: Gradebook) -> None:
    if assignment.is_active:
        print("\nThis assignment is already active.")
        return None

    print("\nYou are about to reactivate the following assignment:")
    print(f"{formatters.format_assignment_oneline(assignment)}")

    confirm_reactivate = helpers.confirm_action(
        "Are you sure you want to reactivate this assignment?"
    )

    if not confirm_reactivate:
        helpers.returning_without_changes()
        return None

    assignment.toggle_archived_status()
    gradebook.save(gradebook.path)
    print("\nAssignment successfully reactivated.")


# === view assignment ===


# TODO:
def view_assignments_menu() -> None:
    pass


# TODO: display oneline first, then options for short and long
def view_individual_assignment(gradebook: Gradebook) -> None:
    search_results = helpers.search_assignments(gradebook)
    assignment = helpers.prompt_assignment_selection_from_search(search_results)

    if not assignment:
        return None

    print("\nYou are viewing the following assignment:")
    print(formatters.format_assignment_oneline(assignment))


def view_active_assignments(gradebook: Gradebook) -> None:
    print(f"\n{formatters.format_banner_text("Active Assignments")}")

    active_assignments = gradebook.get_records(
        gradebook.assignments, lambda x: x.is_active
    )

    if not active_assignments:
        print("There are no active assignments.")
        return None

    helpers.sort_and_display_records(
        records=active_assignments,
        sort_key=lambda x: (
            gradebook.find_category_by_uuid(x.category_id),
            x.due_date_iso,
            x.name,
        ),
        formatter=formatters.format_assignment_oneline,
    )


def view_inactive_assignments(gradebook: Gradebook) -> None:
    print(f"\n{formatters.format_banner_text("Inactive Assignment")}")

    inactive_assignments = gradebook.get_records(
        gradebook.assignments, lambda x: not x.is_active
    )

    if not inactive_assignments:
        print("There are no inactive assignments.")

    helpers.sort_and_display_records(
        records=inactive_assignments,
        sort_key=lambda x: (
            gradebook.find_category_by_uuid(x.category_id),
            x.due_date_iso,
            x.name,
        ),
        formatter=formatters.format_assignment_oneline,
    )


def view_all_assignments(gradebook: Gradebook) -> None:
    print(f"\n{formatters.format_banner_text("All Assignments")}")

    all_assignments = gradebook.get_records(gradebook.assignments)

    if not all_assignments:
        print("There are no assignments yet.")
        return None

    helpers.sort_and_display_records(
        records=all_assignments,
        sort_key=lambda x: (
            gradebook.find_category_by_uuid(x.category_id),
            x.due_date_iso,
            x.name,
        ),
        formatter=formatters.format_assignment_oneline,
    )
