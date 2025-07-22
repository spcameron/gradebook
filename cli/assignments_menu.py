# cli/assignments_menu.py

"""
Manage Assignments menu for the Gradebook CLI.

Provides functions for addings, editing, removing, and viewing Assignments.
"""

from datetime import datetime
from typing import Callable, Optional, cast

import cli.formatters as formatters
import cli.menu_helpers as helpers
from cli.menu_helpers import MenuSignal
from models.assignment import Assignment
from models.category import Category
from models.gradebook import Gradebook
from utils.utils import generate_uuid


def run(gradebook: Gradebook) -> None:
    """
    Top-level loop with dispatch for the Manage Assignments menu.

    Args:
        gradebook: the active Gradebook.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        The finally block guarantees a check for unsaved changes before returning.
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
    Loops a prompt to create a new Assignment and add to the Gradebook.

    Args:
        gradebook: the active Gradebook.

    Notes:
        New assignments are added to the Gradebook but not saved. Gradebook is marked dirty instead.
    """
    while True:
        new_assignment = prompt_new_assignment(gradebook)

        if new_assignment is not None and preview_and_confirm_assignment(
            new_assignment, gradebook
        ):
            gradebook.add_assignment(new_assignment)
            gradebook.mark_dirty()
            print(f"\n{new_assignment.name} successfully added.")

        if not helpers.confirm_action(
            "Would you like to continue adding new assignments?"
        ):
            break

    helpers.returning_to("Manage Assignments menu")


def prompt_new_assignment(gradebook: Gradebook) -> Optional[Assignment]:
    """
    Creates a new Assignment.

    Args:
        gradebook: the active Gradebook.

    Returns:
        A new Assignment object, or None.
    """
    name = prompt_name_input_or_cancel(gradebook)

    if name is MenuSignal.CANCEL:
        return None
    else:
        name = cast(str, name)

    category = prompt_find_category_or_none(gradebook)

    if category is MenuSignal.CANCEL:
        return None
    elif category is not None:
        category = cast(Category, category)

    points_possible = prompt_points_possible_input_or_cancel()

    if points_possible is MenuSignal.CANCEL:
        return None
    else:
        points_possible = cast(float, points_possible)

    due_date = prompt_due_date()

    try:
        category_id = category.id if category else None
        assignment_id = generate_uuid()
        new_assignment = Assignment(
            id=assignment_id,
            name=name,
            category_id=category_id,
            points_possible=points_possible,
            due_date=due_date,
        )
        return new_assignment
    except (ValueError, TypeError) as e:
        print(f"\nError: Could not create assignment ... {e}")
        return None


def preview_and_confirm_assignment(
    assignment: Assignment, gradebook: Gradebook
) -> bool:
    """
    Previews Assignment details, offers opportunity to edit details, and prompts user for confirmation.

    Args:
        assignment: the Assignment under review.
        gradebook: the active Gradebook.

    Notes:
        Uses edit_queued_assignment() since this Submission object has not yet been added to the Gradebook.
    """
    print("\nYou are about to create the following assignment:")
    print(formatters.format_assignment_multiline(assignment, gradebook))

    if helpers.confirm_action(
        "Would you like to edit this assignment first (change the name, points possible, due date, or linked category)?"
    ):
        edit_queued_assignment(assignment, gradebook)

    if helpers.confirm_action("Would you like to create this assignment?"):
        return True
    else:
        print("Discarding assignment.")
        return False


# === data input helpers ===


def prompt_name_input_or_cancel(gradebook: Gradebook) -> str | MenuSignal:
    """
    Solicits user input for Assignment name, validates uniqueness, and treats blank input as 'cancel'.

    Args:
        gradebook: the active Gradebook.

    Returns:
        User input, or MenuSignal.CANCEL if input is "".

    Notes:
        The only validation is the call to require_unique_assignment_name. Defensive validation against malicious input is missing.
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
            print(f"\nError: {e}")


def prompt_points_possible_input_or_cancel() -> float | MenuSignal:
    """
    Solicits user input for points possible, casts it to float, and treats a blank input as 'cancel'.

    Returns:
        User input as a float, or MenuSignal.CANCEL if input is "".

    Notes:
        Handles the type casting from string to float, but further data validation is the responsibility of the caller.
    """
    while True:
        user_input = helpers.prompt_user_input_or_cancel(
            "Enter total points possible (leave blank to cancel):"
        )

        if isinstance(user_input, MenuSignal):
            return user_input

        try:
            return float(user_input)
        except ValueError:
            print(
                "\nError: Invalid input. Please enter a number or leave blank to cancel."
            )


def prompt_due_date() -> Optional[datetime]:
    """
    Solicits user input for due date and time, with the option for 'No due date' and default due time of '23:59' for blank entries.

    Returns:
        A datetime object, or None to signal 'No due date'.

    Notes:
        Handles the strptime() conversion from string to datetime inside a try/except block.
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
            due_date = (
                datetime.strptime(f"{due_date_str} {due_time_str}", "%Y-%m-%d %H:%M")
                if due_date_str and due_time_str
                else None
            )
            return due_date
        except (ValueError, TypeError):
            print(
                "\nError: Invalid input. Please enter the due date as YYYY-MM-DD and the time as 24-hour HH:MM."
            )
        except Exception as e:
            print(f"\nError: prompt_due_date() ... {e}")


# === edit assignment ===


def get_editable_fields() -> list[tuple[str, Callable[[Assignment, Gradebook], bool]]]:
    """
    Helper method to organize the list of editable fields and their related functions.

    Returns:
        A list of tuples - pairs of strings and function names.
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
    Prompts user to search for an Assignment and then passes the result to edit_assignment().

    Args:
        gradebook: the active Gradebook.
    """
    assignment = prompt_find_assignment(gradebook)

    if assignment is MenuSignal.CANCEL:
        return None
    else:
        assignment = cast(Assignment, assignment)
        edit_assignment(assignment, gradebook)


def edit_assignment(assignment: Assignment, gradebook: Gradebook) -> None:
    """
    Dispatch method for selecting and editable field and using boolean return values to monitor whether changes have been made.

    Args:
        assignment: the Assignment being edited.
        gradebook: the active Gradebook.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        Uses a function scoped variable to flag whether the edit_* methods have manipulated the Assignment at all.
        If so, the user is prompted to either save changes now, or defer and mark the Gradebook dirty for saving upstream.
    """
    print("\nYou are editing the following assignment:")
    print(formatters.format_assignment_multiline(assignment, gradebook))

    title = formatters.format_banner_text("Editable Fields")
    options = get_editable_fields()
    zero_option = "Finish editing and return"

    unsaved_changes = False

    while True:
        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response is MenuSignal.EXIT:
            break
        elif callable(menu_response):
            if menu_response(assignment, gradebook):
                unsaved_changes = True
        else:
            raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

        if not helpers.confirm_action(
            "Would you like to continue editing this assignment?"
        ):
            break

    if unsaved_changes:
        if helpers.confirm_unsaved_changes():
            gradebook.save(gradebook.path)
        else:
            gradebook.mark_dirty()
    else:
        helpers.returning_without_changes()

    helpers.returning_to("Manage Assignments menu")


def edit_queued_assignment(assignment: Assignment, gradebook: Gradebook) -> None:
    """
    Dispatch method for the edit menu that does not track changes, since the edited Assignment has not yet been added to the Gradebook.

    Args:
        assignment: an Assignment not yet added to the Gradebook and targeted for editing.
        gradebook: the active Gradebook.

    Raises:
        RuntimeError: If the menu response is unrecognized.
    """
    print("\nYou are editing the folllowing assignment:")
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

    helpers.returning_to("Assignment creation")


def edit_name_and_confirm(assignment: Assignment, gradebook: Gradebook) -> bool:
    """
    Edit the name field of an Assignment.

    Args:
        assignment: the Assignment targeted for editing.
        gradebook: the active Gradebook.

    Returns:
        True if the name was changed, and False otherwise.
    """
    current_name = assignment.name
    new_name = prompt_name_input_or_cancel(gradebook)

    if new_name is MenuSignal.CANCEL:
        helpers.returning_without_changes()
        return False
    else:
        new_name = cast(str, new_name)

    print(
        f"\nCurrent assignment name: {current_name} ... New assignment name: {new_name}"
    )

    if not helpers.confirm_make_change():
        helpers.returning_without_changes()
        return False

    try:
        assignment.name = new_name
        print(f"\nName successfully updated to {assignment.name}.")
        return True
    except Exception as e:
        print(f"\nError: Could not update assignment ... {e}")
        helpers.returning_without_changes()
        return False


def edit_linked_category_and_confirm(
    assignment: Assignment, gradebook: Gradebook
) -> bool:
    """
    Edit the linked Category of an Assignment.

    Args:
        assignment: the Assignment targeted for editing.
        gradebook: the active Gradebook.

    Returns:
        True if the linked Category was changed, and False otherwise.
    """
    current_category = (
        gradebook.find_category_by_uuid(assignment.category_id)
        if assignment.category_id
        else None
    )
    new_category = prompt_find_category_or_none(gradebook)

    if new_category is MenuSignal.CANCEL:
        helpers.returning_without_changes()
        return False
    elif new_category is not None:
        new_category = cast(Category, new_category)

    current_category_preview = (
        current_category.name if current_category else "Uncategorized"
    )
    new_category_preview = new_category.name if new_category else "Uncategorized"

    print(
        f"\nCurrent category: {current_category_preview} ... New category: {new_category_preview}"
    )

    if not helpers.confirm_make_change():
        helpers.returning_without_changes()
        return False

    try:
        assignment.category_id = new_category.id if new_category else None
        print(f"\nCategory successfully updated to {new_category_preview}.")
        return True
    except Exception as e:
        print(f"\nError: Could not update assignment ... {e}")
        helpers.returning_without_changes()
        return False


def edit_due_date_and_confirm(assignment: Assignment, _: Gradebook) -> bool:
    """
    Edit the due date of an Assignment.

    Args:
        assignment: the Assignment targeted for editing.
        _: the active Gradebook (unused).

    Returns:
        True if the due date was changed, and False otherwise.
    """
    current_due_date = assignment.due_date_dt
    new_due_date = prompt_due_date()

    current_due_date_preview = formatters.format_due_date_from_datetime(
        current_due_date
    )
    new_due_date_preview = formatters.format_due_date_from_datetime(new_due_date)

    print(
        f"\nCurrent due date: {current_due_date_preview} ... New due date: {new_due_date_preview}"
    )

    if not helpers.confirm_make_change():
        helpers.returning_without_changes()
        return False

    try:
        assignment.due_date_dt = new_due_date
        print(
            f"\nDue date successfully updated to {formatters.format_due_date_from_datetime(assignment.due_date_dt)}."
        )
        return True
    except Exception as e:
        print(f"\nError: Could not update the due date ... {e}")
        helpers.returning_without_changes()
        return False


def edit_points_possible_and_confirm(assignment: Assignment, _: Gradebook) -> bool:
    """
    Edit the points possible of an Assignment.

    Args:
        assignment: the Assignment targeted for editing.
        _: the active Gradebook (unused).

    Returns:
        True if the points possible was changed, and False otherwise.
    """
    current_points_possible = assignment.points_possible
    new_points_possible = prompt_points_possible_input_or_cancel()

    if new_points_possible is MenuSignal.CANCEL:
        helpers.returning_without_changes()
        return False
    else:
        new_points_possible = cast(float, new_points_possible)

    print(
        f"\nCurrent points possible: {current_points_possible} ... New points possible: {new_points_possible}"
    )

    if not helpers.confirm_make_change():
        helpers.returning_without_changes()
        return False

    try:
        assignment.points_possible = new_points_possible
        print(
            f"\nPoints possible successfully updated to {assignment.points_possible}."
        )
        return True
    except ValueError as e:
        print(f"\nError: Could not update the points possible ... {e}")
        helpers.returning_without_changes()
        return False


def edit_active_status_and_confirm(
    assignment: Assignment, gradebook: Gradebook
) -> bool:
    """
    Toggles the is_active field of an Assignment via calls to confirm_and_archive() or confirm_and_reactivate().

    Args:
        assignment: the Assignment targeted for editing.
        gradebook: the active Gradebook.

    Returns:
        True if the active status was changed, and False otherwise.
    """
    print(f"\nThis assignment is currently {assignment.status}")

    if not helpers.confirm_action("Would you like to edit the archived status?"):
        helpers.returning_without_changes()
        return False

    if assignment.is_active:
        return confirm_and_archive(assignment, gradebook)
    else:
        return confirm_and_reactivate(assignment, gradebook)


# === remove assignment ===


def find_and_remove_assignment(gradebook: Gradebook) -> None:
    """
    Prompts user to search for an Assignment and then passes the result to remove_assignment().

    Args:
        gradebook: the active Gradebook.
    """
    assignment = prompt_find_assignment(gradebook)

    if assignment is MenuSignal.CANCEL:
        return None
    else:
        assignment = cast(Assignment, assignment)
        remove_assignment(assignment, gradebook)


def remove_assignment(assignment: Assignment, gradebook: Gradebook) -> None:
    """
    Dispatch method to either delete, archive, or edit the Assignment, or return without changes.

    Args:
        assignment: the Assignment targeted for deleting/archiving.
        gradebook: the active Gradebook.

    Raise:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        Uses a function scope variable to detect if any function calls report data manipulation.
        If so, the user is prompted to either save now or defer, in which case the Gradebook is marked dirty.
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

    unsaved_changes = False

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response is MenuSignal.EXIT:
        helpers.returning_without_changes()
        return None
    elif callable(menu_response):
        if menu_response(assignment, gradebook):
            unsaved_changes = True
    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

    if unsaved_changes:
        if helpers.confirm_unsaved_changes():
            gradebook.save(gradebook.path)
        else:
            gradebook.mark_dirty()

    helpers.returning_to("Manage Assignments menu")


def confirm_and_remove(assignment: Assignment, gradebook: Gradebook) -> bool:
    """
    Deletes the Assignment from the Gradebook after preview and confirmation.

    Args:
        assignment: the Assignment targeted for deletion.
        gradebook: the active Gradebook.

    Returns:
        True if the Assignment was removed, and False otherwise.
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
        return False

    try:
        gradebook.remove_assignment(assignment)
        print("\nAssignment successfully removed from Gradebook.")
        return True
    except Exception as e:
        print(f"\nError: Could not remove submission ... {e}")
        helpers.returning_without_changes()
        return False


def confirm_and_archive(assignment: Assignment, gradebook: Gradebook) -> bool:
    """
    Toggles the is_active field of an active Assignment, after preview and confirmation.

    Args:
        assignment: the Assignment targeted for archiving.
        gradebook: the active Gradebook.

    Returns:
        True if the active status was changed, and False otherwise.
    """
    if not assignment.is_active:
        print("\nThis assignment has already been archived.")
        return False

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
        return False

    try:
        assignment.toggle_archived_status()
        print(f"\nAssignment status successfully updated to: {assignment.status}")
        return True
    except Exception as e:
        print(f"\nError: Could not update assignment ... {e}")
        helpers.returning_without_changes()
        return False


def confirm_and_reactivate(assignment: Assignment, gradebook: Gradebook) -> bool:
    """
    Toggle the is_active field of an inactive Assignment, after preview and confirmation.

    Args:
        assignment: the Assignment targeted for reactivation.
        gradebook: the active Gradebook.

    Returns:
        True if the active status was changed, and False otherwise.
    """
    if assignment.is_active:
        print("\nThis assignment is already active.")
        return False

    print("\nYou are about to reactivate the following assignment:")
    print(formatters.format_assignment_multiline(assignment, gradebook))

    confirm_reactivate = helpers.confirm_action(
        "Are you sure you want to reactivate this assignment?"
    )

    if not confirm_reactivate:
        helpers.returning_without_changes()
        return False

    try:
        assignment.toggle_archived_status()
        print(f"\nAssignment status successfully updated to: {assignment.status}")
        return True
    except Exception as e:
        print(f"\nError: Could not update assignment ... {e}")
        helpers.returning_without_changes()
        return False


# === view assignment ===


def view_assignments_menu(gradebook: Gradebook) -> None:
    """
    Dispatch method for the various view options (individual, active, inactive, all).

    Args:
        gradebook: the active Gradebook.

    Raises:
        RuntimeError: If the menu response is unrecognized.
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
        return None
    elif callable(menu_response):
        menu_response(gradebook)
    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")


def view_individual_assignment(gradebook: Gradebook) -> None:
    """
    Calls find_assignment() and then displays a one-line view of that Assignment, followed by a prompt to view the multi-line view or return.

    Args:
        gradebook: the active Gradebook.
    """
    assignment = prompt_find_assignment(gradebook)

    if assignment is MenuSignal.CANCEL:
        return None
    else:
        assignment = cast(Assignment, assignment)

    print("\nYou are viewing the following assignment:")
    print(formatters.format_assignment_oneline(assignment))

    if helpers.confirm_action(
        "Would you like to see an expanded view of this assignment?"
    ):
        print(formatters.format_assignment_multiline(assignment, gradebook))


def view_active_assignments(gradebook: Gradebook) -> None:
    """
    Displays a list of active Assignments.

    Args:
        gradebook: the active Gradebook.
    """
    banner = formatters.format_banner_text("Active Assignments")
    print(f"\n{banner}")

    active_assignments = gradebook.get_records(
        gradebook.assignments, lambda x: x.is_active
    )

    if not active_assignments:
        print("There are no active assignments.")
        return None

    helpers.sort_and_display_records(
        records=active_assignments,
        sort_key=make_assignment_sort_key(gradebook),
        formatter=formatters.format_assignment_oneline,
    )


def view_inactive_assignments(gradebook: Gradebook) -> None:
    """
    Displays a list of inactive Assignments.

    Args:
        gradebook: the active Gradebook.
    """
    banner = formatters.format_banner_text("Inactive Assignments")
    print(f"\n{banner}")

    inactive_assignments = gradebook.get_records(
        gradebook.assignments, lambda x: not x.is_active
    )

    if not inactive_assignments:
        print("There are no inactive assignments.")
        return None

    helpers.sort_and_display_records(
        records=inactive_assignments,
        sort_key=make_assignment_sort_key(gradebook),
        formatter=formatters.format_assignment_oneline,
    )


def view_all_assignments(gradebook: Gradebook) -> None:
    """
    Displays a list of all Assignments.

    Args:
        gradebook: the active Gradebook.
    """
    banner = formatters.format_banner_text("All Assignments")
    print(f"\n{banner}")

    all_assignments = gradebook.get_records(gradebook.assignments)

    if not all_assignments:
        print("There are no assignments yet.")
        return None

    helpers.sort_and_display_records(
        records=all_assignments,
        sort_key=make_assignment_sort_key(gradebook),
        formatter=formatters.format_assignment_oneline,
    )


def make_assignment_sort_key(gradebook: Gradebook) -> Callable[[Assignment], tuple]:
    """
    Helper method to return a sort key function for sorting Assignments.

    Args:
        gradebook: the Active gradebook.

    Returns:
        sort_key function.
    """

    def sort_key(assignment: Assignment) -> tuple:
        """
        Sort key function to organize Assignments, first by Category, then by due date, and lastly by name.

        Args:
            assignment: the Assignment being sorted.

        Returns:
            Tuple - (category name, due date, assignment name).
        """
        category = (
            gradebook.find_category_by_uuid(assignment.category_id)
            if assignment.category_id
            else None
        )
        category_name = category.name if category else "zzz_Uncategorized"
        due_date_iso = assignment.due_date_iso or "zzz_No due date"
        name = assignment.name

        return (category_name, due_date_iso, name)

    return sort_key


# === finder methods ===


def prompt_find_category_or_none(
    gradebook: Gradebook,
) -> Optional[Category] | MenuSignal:
    """
    Menu dispatch for either finding a Category by search or from a list of Categories (separate lists for active and inactive).

    Args:
        gradebook: the active Gradebook.

    Returns:
        The selected Category, None to indicate 'Uncategorized', or MenuSignal.CANCEL if either the user cancels or the search yields no hits.

    Raises:
        RuntimeError: If the menu response is unrecognized.
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
    Menu dispatch for either finding an Assignment by search or from a list of Assignments (separate lists for active and inactive.)

    Args:
        gradebook: the active Gradebook.

    Returns:
        The selected Assignment, or MenuSignal.CANCEL if either the user cancels or the search yields no hits.

    Raises:
        RuntimeError: If the menu response is unrecognized.
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
