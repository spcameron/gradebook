# cli/assignments_menu.py

"""
Manage Assignments menu for the Gradebook CLI.

This module defines the full interface for managing `Assignment` records, including:
- Adding new assignments
- Editing assignment attributes (name, due date, points possible, linked category)
- Archiving or permanently removing assignments
- Viewing assignment records (individual, filtered, or all)

All operations are routed through the `Gradebook` API for consistency, validation, and state tracking.
Control flow adheres to structured CLI menu patterns with clear terminal-level feedback.
"""

import datetime
from typing import Callable, cast

import cli.formatters as formatters
import cli.menu_helpers as helpers
from cli.menu_helpers import MenuSignal
from core.utils import generate_uuid
from models.assignment import Assignment
from models.category import Category
from models.gradebook import Gradebook


def run(gradebook: Gradebook) -> None:
    """
    Top-level loop with dispatch for the Manage Assignments menu.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        - The finally block guarantees a check for unsaved changes before returning.
    """
    title = formatters.format_banner_text("Manage Assignments")
    options = [
        ("Add Assignment", add_assignment),
        ("Edit Assignment", find_and_edit_assignment),
        ("Remove Assignment", find_and_remove_assignment),
        ("View Assignments", view_assignments_menu),
    ]
    zero_option = "Return to Course Manager menu"

    try:
        while True:
            menu_response = helpers.display_menu(title, options, zero_option)

            if menu_response is MenuSignal.EXIT:
                break

            elif callable(menu_response):
                menu_response(gradebook)

            else:
                raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

    finally:
        helpers.prompt_if_dirty(gradebook)

    helpers.returning_to("Course Manager menu")


# === add assignment ===


def add_assignment(gradebook: Gradebook) -> None:
    """
    Loops a prompt to create a new `Assignment` object and add it to the gradebook.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Additions are not saved automatically. If the gradebook is marked dirty after adding, the user will be prompted to save before returning to the previous menu.
    """
    while True:
        new_assignment = prompt_new_assignment(gradebook)

        if new_assignment is not None and preview_and_confirm_assignment(
            new_assignment, gradebook
        ):
            gradebook_response = gradebook.add_assignment(new_assignment)

            if not gradebook_response.success:
                helpers.display_response_failure(gradebook_response)
                print(f"\n{new_assignment.name} was not added.")

            else:
                print(f"\n{gradebook_response.detail}")

        if not helpers.confirm_action(
            "Would you like to continue adding new assignments?"
        ):
            break

    helpers.prompt_if_dirty(gradebook)

    helpers.returning_to("Manage Assignments menu")


def prompt_new_assignment(gradebook: Gradebook) -> Assignment | None:
    """
    Creates a new `Assignment` object.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        A new `Assignment` object, or None.
    """
    name = prompt_name_input_or_cancel(gradebook)

    if name is MenuSignal.CANCEL:
        return None
    name = cast(str, name)

    category = prompt_find_category_or_none(gradebook)

    if category is MenuSignal.CANCEL:
        return None

    elif category is not None:
        category = cast(Category, category)

    points_possible = prompt_points_possible_input_or_cancel()

    if points_possible is MenuSignal.CANCEL:
        return None
    points_possible = cast(float, points_possible)

    due_date = prompt_due_date()

    try:
        return Assignment(
            id=generate_uuid(),
            name=name,
            category_id=category.id if category else None,
            points_possible=points_possible,
            due_date=due_date,
        )

    except (ValueError, TypeError) as e:
        print(f"\n[ERROR] Could not create assignment: {e}")
        return None


def preview_and_confirm_assignment(
    assignment: Assignment, gradebook: Gradebook
) -> bool:
    """
    Previews new `Assignment` details, offers opportunity to edit details, and prompts user for confirmation.

    Args:
        assignment (Assignment): The `Assignment` object under review.
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        True if user confirms the `Assignment` details, and False otherwise.
    """
    print("\nYou are about to create the following assignment:")
    print(formatters.format_assignment_multiline(assignment, gradebook))

    if helpers.confirm_action(
        "Would you like to edit this assignment first (change the name, points possible, due date, or linked category)?"
    ):
        edit_assignment(assignment, gradebook, "Assignment creation preview")

    if helpers.confirm_action("Would you like to create this assignment?"):
        return True

    else:
        print(f"Discarding assignment: {assignment.name}")
        return False


# === data input helpers ===


def prompt_name_input_or_cancel(gradebook: Gradebook) -> str | MenuSignal:
    """
    Solicits user input for assignment name, validates uniqueness, and treats blank input as 'cancel'.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        User input unmodified, or `MenuSignal.CANCEL` if input is "".

    Notes:
        - The only validation is the call to `require_unique_assignment_name()`. Defensive validation against malicious input is missing.
    """
    while True:
        user_input = helpers.prompt_user_input_or_cancel(
            "Enter assignment name (leave blank to cancel):"
        )

        if isinstance(user_input, MenuSignal):
            return user_input

        try:
            gradebook.require_unique_assignment_name(user_input)

            return user_input

        except ValueError as e:
            print(f"\n[ERROR] {e}")
            print("Please try again.")


def prompt_points_possible_input_or_cancel() -> float | MenuSignal:
    """
    Solicits user input for points possible, validates and normalizes the input, and treats a blank input as 'cancel'.

    Returns:
        The validated user input as a float, or `MenuSignal.CANCEL` if input is "".

    Notes:
        - Validation and normalization is handled by `Assignment.validate_points_input()`.
    """
    while True:
        user_input = helpers.prompt_user_input_or_cancel(
            "Enter total points possible (leave blank to cancel):"
        )

        if isinstance(user_input, MenuSignal):
            return user_input

        try:
            points = Assignment.validate_points_input(user_input)

            return points

        except (ValueError, TypeError) as e:
            print(f"\n[ERROR] {e}")
            print("Please try again.")


def prompt_due_date() -> datetime.datetime | None:
    """
    Solicits user input for due date and time, with options for 'No due date', or default due time of '23:59' if only a due date is provided.

    Returns:
        A datetime.datetime object, or None to signal 'No due date'.

    Notes:
        - Handles the strptime() conversion from string to datetime.datetime inside a try/except block.
    """
    while True:
        due_date_str = helpers.prompt_user_input_or_default(
            "Enter due date (YYYY-MM-DD, leave blank for no due date):"
        )

        if due_date_str is MenuSignal.DEFAULT:
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

        if due_time_str is MenuSignal.DEFAULT:
            due_time_str = "23:59"

        elif due_time_str is not None:
            due_time_str = cast(str, due_time_str)

        try:
            due_date_dt = Assignment.validate_due_date_input(due_date_str, due_time_str)

            return due_date_dt

        except TypeError as e:
            print(f"\n[ERROR] {e}")
            print("Please try again.")


# === edit assignment ===


def get_editable_fields() -> list[tuple[str, Callable[[Assignment, Gradebook], None]]]:
    """
    Helper method to organize the list of editable fields and their related functions.

    Returns:
        A list of `(field_name, edit_function)` tuples used to prompt and edit `Category` attributes.
    """
    return [
        ("Name", edit_name_and_confirm),
        ("Linked Category", edit_linked_category_and_confirm),
        ("Due Date", edit_due_date_and_confirm),
        ("Points Possible", edit_points_possible_and_confirm),
        ("Archived Status", edit_active_status_and_confirm),
    ]


def find_and_edit_assignment(gradebook: Gradebook) -> None:
    """
    Prompts user to search for an `Assignment` and then passes the result to `edit_assignment()`.

    Args:
        gradebook (Gradebook): The active `Gradebook`.
    """
    assignment = prompt_find_assignment(gradebook)

    if assignment is MenuSignal.CANCEL:
        return
    assignment = cast(Assignment, assignment)

    edit_assignment(assignment, gradebook)


def edit_assignment(
    assignment: Assignment,
    gradebook: Gradebook,
    return_context: str = "Manage Assignments menu",
) -> None:
    """
    Interface for editing fields of an `Assignment` record.

    Args:
        assignment (Assignment): The `Assignment` object being edited.
        gradebook (Gradebook): The active `Gradebook`.
        return_context (str): An optional description of the call site, uses "Manage Assignments menu" by default.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        - All edit operations are dispatched through `Gradebook` to ensure proper mutation and state tracking.
        - Changes are not saved automatically. If the gradebook is marked dirty after edits, the user will be prompted to save before returning to the previous menu.
        - The `return_context` label is used to display a confirmation message when exiting the edit menu.
    """
    print("\nYou are editing the following assignment:")
    print(formatters.format_assignment_multiline(assignment, gradebook))

    title = formatters.format_banner_text("Editable Fields")
    options = get_editable_fields()
    zero_option = "Finish editing and return"

    while True:
        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response is MenuSignal.EXIT:
            break

        elif callable(menu_response):
            menu_response(assignment, gradebook)

        else:
            raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

        if not helpers.confirm_action(
            "Would you like to continue editing this assignment?"
        ):
            break

    if gradebook.has_unsaved_changes:
        helpers.prompt_if_dirty(gradebook)

    else:
        helpers.returning_without_changes()

    helpers.returning_to(return_context)


def edit_name_and_confirm(assignment: Assignment, gradebook: Gradebook) -> None:
    """
    Prompts for a new name and updates the `Assignment` record via `Gradebook`.

    Args:
        assignment (Assignment): The `Assignment` object targeted for editing.
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Cancels early if the user enters nothing or declines the confirmation.
        - Uses `Gradebook.update_assignment_name()` to perform the update and track changes.
    """
    current_name = assignment.name
    new_name = prompt_name_input_or_cancel(gradebook)

    if new_name is MenuSignal.CANCEL:
        helpers.returning_without_changes()
        return
    new_name = cast(str, new_name)

    print(
        f"\nCurrent assignment name: {current_name} -> New assignment name: {new_name}"
    )

    if not helpers.confirm_make_change():
        helpers.returning_without_changes()
        return

    gradebook_response = gradebook.update_assignment_name(assignment, new_name)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print("\nAssignment name was not updated.")
        helpers.returning_without_changes()

    else:
        print(f"\n{gradebook_response.detail}")


def edit_linked_category_and_confirm(
    assignment: Assignment, gradebook: Gradebook
) -> None:
    """
    Prompts to search for a new linked `Category` and updates the `Assignment` record via `Gradebook`.

    Args:
        assignment (Assignment): The `Assignment` object targeted for editing.
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Cancels early if the user opts out from `prompt_find_category_or_none()`.
        - Accepts both a linked `Category` object and None as valid values.
        - Uses `Gradebook.update_assignment_linked_category()` to perform the update and track changes.
    """
    if assignment.category_id:
        category_response = gradebook.find_category_by_uuid(assignment.category_id)

        if not category_response.success:
            helpers.display_response_failure(category_response)
            helpers.returning_without_changes()
            return

        current_category = category_response.data["record"]

    else:
        current_category = None

    new_category = prompt_find_category_or_none(gradebook)

    if new_category is MenuSignal.CANCEL:
        helpers.returning_without_changes()
        return

    elif new_category is not None:
        new_category = cast(Category, new_category)

    current_category_preview = (
        current_category.name if current_category else "[UNCATEGORIZED]"
    )
    new_category_preview = new_category.name if new_category else "[UNCATEGORIZED]"

    print(
        f"\nCurrent category: {current_category_preview} -> New category: {new_category_preview}"
    )

    if not helpers.confirm_make_change():
        helpers.returning_without_changes()
        return

    gradebook_response = gradebook.update_assignment_linked_category(
        assignment, new_category
    )

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print("\nAssignment linked category was not updated.")
        helpers.returning_without_changes()

    else:
        print(f"\n{gradebook_response.detail}")


def edit_due_date_and_confirm(assignment: Assignment, gradebook: Gradebook) -> None:
    """
    Prompts for a new due date and udpates the `Assignment` record via `Gradebook`.

    Args:
        assignment (Assignment): The `Assignment` object targeted for editing.
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Accepts both a datetime.datetime object and None as valid values.
        - Uses `Gradebook.update_assignment_due_date()` to perform the update and track changes.
    """
    current_due_date = assignment.due_date_dt
    new_due_date = prompt_due_date()

    current_due_date_preview = formatters.format_due_date_from_datetime(
        current_due_date
    )
    new_due_date_preview = formatters.format_due_date_from_datetime(new_due_date)

    print(
        f"\nCurrent due date: {current_due_date_preview} -> New due date: {new_due_date_preview}"
    )

    if not helpers.confirm_make_change():
        helpers.returning_without_changes()
        return

    gradebook_response = gradebook.update_assignment_due_date(assignment, new_due_date)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print("\nAssignment due date was not updated.")
        helpers.returning_without_changes()

    else:
        print(f"\n{gradebook_response.detail}")


def edit_points_possible_and_confirm(
    assignment: Assignment, gradebook: Gradebook
) -> None:
    """
    Prompts for a new points possible value and updates the `Assignment` record via `Gradebook`.

    Args:
        assignment (Assignment): The `Assignment` object targeted for editing.
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Cancels early if the user enters nothing or declines the confirmation.
        - Uses `Gradebook.update_assignment_points_possible()` to perform the update and track changes.
    """
    current_points_possible = assignment.points_possible
    new_points_possible = prompt_points_possible_input_or_cancel()

    if new_points_possible is MenuSignal.CANCEL:
        helpers.returning_without_changes()
        return
    new_points_possible = cast(float, new_points_possible)

    print(
        f"\nCurrent points possible: {current_points_possible} -> New points possible: {new_points_possible}"
    )

    if not helpers.confirm_make_change():
        helpers.returning_without_changes()
        return

    gradebook_response = gradebook.update_assignment_points_possible(
        assignment, new_points_possible
    )

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print("\nAssignment points possible value was not updated.")
        helpers.returning_without_changes()

    else:
        print(f"\n{gradebook_response.detail}")


def edit_active_status_and_confirm(
    assignment: Assignment, gradebook: Gradebook
) -> None:
    """
    Toggles the `is_active` field of an `Assignment` record via calls to `confirm_and_archive()` or `confirm_and_reactivate()`.

    Args:
        assignment (Assignment): The `Assignment` object targeted for editing.
        gradebook (Gradebook): The active `Gradebook`.
    """
    print(f"\nThis assignment is currently {assignment.status}")

    if not helpers.confirm_action("Would you like to edit the archived status?"):
        helpers.returning_without_changes()
        return

    if assignment.is_active:
        confirm_and_archive(assignment, gradebook)

    else:
        confirm_and_reactivate(assignment, gradebook)


# === remove assignment ===


def find_and_remove_assignment(gradebook: Gradebook) -> None:
    """
    Prompts user to search for an `Assignment` and then passes the result to `remove_assignment()`.

    Args:
        gradebook (Gradebook): The active `Gradebook`.
    """
    assignment = prompt_find_assignment(gradebook)

    if assignment is MenuSignal.CANCEL:
        return
    assignment = cast(Assignment, assignment)

    remove_assignment(assignment, gradebook)


def remove_assignment(assignment: Assignment, gradebook: Gradebook) -> None:
    """
    Interface for removing, archiving, or editing an `Assignment` record.

    Args:
        assignment (Assignment): The `Assignment` object targeted for deleting/archiving.
        gradebook (Gradebook): The active `Gradebook`.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        - All remove and edit operations are dispatched through `Gradebook` to ensure proper mutation and state tracking.
        - Changes are not saved automatically. If the gradebook is marked dirty, the user will be prompted to save before returning to the previous menu.
    """
    print("\nYou are viewing the following assignment:")
    print(formatters.format_assignment_oneline(assignment))

    title = "What would you like to do?"
    options = [
        (
            "Remove this assignment (permanently delete the assignment and all linked submissions)",
            confirm_and_remove,
        ),
        (
            "Archive this assignment (preserve all linked submissions)",
            confirm_and_archive,
        ),
        ("Edit this assignment instead", edit_assignment),
    ]
    zero_option = "Return to Manage Assignments menu"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response is MenuSignal.EXIT:
        helpers.returning_without_changes()
        return

    elif callable(menu_response):
        menu_response(assignment, gradebook)

    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

    if gradebook.has_unsaved_changes:
        helpers.prompt_if_dirty(gradebook)

    else:
        helpers.returning_without_changes()

    helpers.returning_to("Manage Assignments menu")


def confirm_and_remove(assignment: Assignment, gradebook: Gradebook) -> None:
    """
    Deletes the `Assignment` and all linked `Submissions` from the `Gradebook` after preview and confirmation.

    Args:
        assignment (Assignment): The `Assignment` object targeted for deletion.
        gradebook (Gradebook): The active `Gradebook`.
    """
    caution_banner = formatters.format_banner_text("CAUTION!")
    print(f"\n{caution_banner}")
    print("You are about to permanently delete the following assignment:")
    print(formatters.format_assignment_multiline(assignment, gradebook))
    print("\nThis will also delete all linked submissions.")

    confirm_deletion = helpers.confirm_action(
        "Are you sure you want to permanently delete this assignment? This action cannot be undone."
    )

    if not confirm_deletion:
        helpers.returning_without_changes()
        return

    gradebook_response = gradebook.remove_assignment(assignment)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print("\nAssignment was not removed.")
        helpers.returning_without_changes()

    else:
        print(f"\n{gradebook_response.detail}")


def confirm_and_archive(assignment: Assignment, gradebook: Gradebook) -> None:
    """
    Archives an active `Assignment` after preview and confirmation.

    Args:
        assignment (Assignment): The `Assignment` object targeted for archiving.
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Archiving preserve all linked `Submission` records but excludes the assignment from reports and calculations.
        - If the `Assignment` is already archived, the method exits early.
    """
    if not assignment.is_active:
        print("\nThis assignment has already been archived.")
        return

    print(
        "\nArchiving an assignment is a safe way to deactivate an assignment without losing data."
    )
    print("\nYou are about to archive the following assignment:")
    print(formatters.format_assignment_multiline(assignment, gradebook))
    print("\nThis will preserve all linked submissions,")
    print("but they will no longer appear in reports or grade calculations.")

    confirm_archiving = helpers.confirm_action(
        "Are you sure you want to archive this assignment?"
    )

    if not confirm_archiving:
        helpers.returning_without_changes()
        return

    gradebook_response = gradebook.toggle_assignment_active_status(assignment)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print("\nAssignment status was not changed.")
        helpers.returning_without_changes()

    else:
        print(f"\n{gradebook_response.detail}")


def confirm_and_reactivate(assignment: Assignment, gradebook: Gradebook) -> None:
    """
    Reactivates an inactive `Assignment` after preview and confirmation.

    Args:
        assignment (Assignment): The `Assignment` object targeted for reactivation.
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - If the `Assignment` is already active, the method exits early.
    """
    if assignment.is_active:
        print("\nThis assignment is already active.")
        return

    print("\nYou are about to reactivate the following assignment:")
    print(formatters.format_assignment_multiline(assignment, gradebook))

    confirm_reactivate = helpers.confirm_action(
        "Are you sure you want to reactivate this assignment?"
    )

    if not confirm_reactivate:
        helpers.returning_without_changes()
        return

    gradebook_response = gradebook.toggle_assignment_active_status(assignment)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print("\nAssignment status was not changed.")
        helpers.returning_without_changes()

    else:
        print(f"\n{gradebook_response.detail}")


# === view assignment ===


def view_assignments_menu(gradebook: Gradebook) -> None:
    """
    Displays the assignment view menu and dispatches selected view options.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        - Options include viewing individual, active, inactive, or all assignments.
    """
    title = "View Assignments"
    options = [
        ("View Individual Assignment", view_individual_assignment),
        ("View Active Assignments", view_active_assignments),
        ("View Inactive Assignments", view_inactive_assignments),
        ("View All Assignments", view_all_assignments),
    ]
    zero_option = "Return to Manage Assignments menu"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response is MenuSignal.EXIT:
        return

    elif callable(menu_response):
        menu_response(gradebook)

    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

    helpers.returning_to("Manage Assignments menu")


def view_individual_assignment(gradebook: Gradebook) -> None:
    """
    Display a one-line summary of a selected `Assignment` record, with the option to view full details.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Uses `prompt_find_assignment()` to search for a record.
        - Prompts the user before displaying the multi-line format.
    """
    assignment = prompt_find_assignment(gradebook)

    if assignment is MenuSignal.CANCEL:
        return
    assignment = cast(Assignment, assignment)

    print("\nYou are viewing the following assignment:")
    print(formatters.format_assignment_oneline(assignment))

    if helpers.confirm_action(
        "Would you like to see an expanded view of this assignment?"
    ):
        print(formatters.format_assignment_multiline(assignment, gradebook))


def view_active_assignments(gradebook: Gradebook) -> None:
    """
    Displays a sorted list of active `Assignment` records.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Uses `Gradebook.get_records()` with a filter for active assignments.
        - Records are sorted by category, then by due date, then by name.
    """
    banner = formatters.format_banner_text("Active Assignments")
    print(f"\n{banner}")

    gradebook_response = gradebook.get_records(
        gradebook.assignments, lambda x: x.is_active
    )

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        return

    active_assignments = gradebook_response.data["records"]

    if not active_assignments:
        print("There are no active assignments.")
        return

    helpers.sort_and_display_records(
        records=active_assignments,
        sort_key=make_assignment_sort_key(gradebook),
        formatter=formatters.format_assignment_oneline,
    )


def view_inactive_assignments(gradebook: Gradebook) -> None:
    """
    Displays a sorted list of inactive `Assignment` records.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Uses `Gradebook.get_records()` with a filter for inactive assignments.
        - Records are sorted by category, then by due date, then by name.
    """
    banner = formatters.format_banner_text("Inactive Assignments")
    print(f"\n{banner}")

    gradebook_response = gradebook.get_records(
        gradebook.assignments, lambda x: not x.is_active
    )

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        return

    inactive_assignments = gradebook_response.data["records"]

    if not inactive_assignments:
        print("There are no inactive assignments.")
        return

    helpers.sort_and_display_records(
        records=inactive_assignments,
        sort_key=make_assignment_sort_key(gradebook),
        formatter=formatters.format_assignment_oneline,
    )


def view_all_assignments(gradebook: Gradebook) -> None:
    """
    Displays a list of all `Assignment` records.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Uses `Gradebook.get_records()` to retrive all assignments, active and inactive.
        - Records are sorted by category, then by due date, then by name.
    """
    banner = formatters.format_banner_text("All Assignments")
    print(f"\n{banner}")

    gradebook_response = gradebook.get_records(gradebook.assignments)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        return

    all_assignments = gradebook_response.data["records"]

    if not all_assignments:
        print("There are no assignments yet.")
        return

    helpers.sort_and_display_records(
        records=all_assignments,
        sort_key=make_assignment_sort_key(gradebook),
        formatter=formatters.format_assignment_oneline,
    )


def make_assignment_sort_key(gradebook: Gradebook) -> Callable[[Assignment], tuple]:
    """
    Helper method to return a sort key function for sorting `Assignment` records.

    Args:
        gradebook (Gradebook): The Active `gradebook`.

    Returns:
        The sort_key function.
    """

    def sort_key(assignment: Assignment) -> tuple:
        """
        Sort key function to organize `Assignments`, first by linked category, then by due date, and lastly by name.

        Args:
            assignment (Assignment): The `Assignment` object being sorted.

        Returns:
            Tuple - (category_name, due_date, assignment_name).
        """
        if assignment.category_id:
            category_response = gradebook.find_category_by_uuid(assignment.category_id)

            if not category_response.success:
                helpers.display_response_failure(category_response)
                category = None

            category = category_response.data["record"]

        else:
            category = None

        category_name = category.name if category else "zzz_Uncategorized"
        due_date_iso = assignment.due_date_iso or "zzz_No due date"
        name = assignment.name

        return (category_name, due_date_iso, name)

    return sort_key


# === finder methods ===


def prompt_find_category_or_none(
    gradebook: Gradebook,
) -> Category | None | MenuSignal:
    """
    Prompts the user to locate a `Category` record by search or list selection.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        The selected `Category`, None to indicate 'Uncategorized', or `MenuSignal.CANCEL` if either the user cancels or the search yields no hits.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        - Offers search, active list, and inactive list as selection methods, as well as the option to declare the `Assignment` uncategorized.
        - Returns early if the user chooses to cancel or no selection is made.
    """
    title = formatters.format_banner_text("Category Selection")
    options = [
        ("Search for a category", helpers.find_category_by_search),
        ("Select from active categories", helpers.find_active_category_from_list),
        ("Select from inactive categories", helpers.find_inactive_category_from_list),
        ("Mark as 'Uncategorized'", lambda _: None),
    ]
    zero_option = "Return and cancel"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response is MenuSignal.EXIT:
        return MenuSignal.CANCEL

    elif callable(menu_response):
        return menu_response(gradebook)

    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")


def prompt_find_assignment(gradebook: Gradebook) -> Assignment | MenuSignal:
    """
    Prompts the user to locate an `Assignment` record by search or list selection.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        The selected `Assignment`, or `MenuSignal.CANCEL` if either the user cancels or the search yields no hits.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        - Offers search, active list, and inactive list as selection methods.
        - Returns early if the user chooses to cancel or if no selection is made.
    """
    title = formatters.format_banner_text("Assignment Selection")
    options = [
        ("Search for an assignment", helpers.find_assignment_by_search),
        ("Select from active assignments", helpers.find_active_assignment_from_list),
        (
            "Select from inactive assignments",
            helpers.find_inactive_assignment_from_list,
        ),
    ]
    zero_option = "Return and cancel"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response is MenuSignal.EXIT:
        return MenuSignal.CANCEL

    elif callable(menu_response):
        return menu_response(gradebook)

    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")
