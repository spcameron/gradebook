# cli/students_menu.py

"""
Manage Students menu for the Gradebook CLI.

This module defines the full interface for managing `Student` records, including:
- Adding new students
- Editing student attributes (name, email, enrollment status)
- Archiving or permanently removing students
- Viewing student records (individual, filtered, or all)

All operations are routed through the `Gradebook` API for consistency, validation, and state tracking.
Control flow adheres to structured CLI menu patterns with clear terminal-level feedback.
"""

from collections.abc import Callable
from typing import cast

import cli.menu_helpers as helpers
import cli.model_formatters as model_formatters
import core.formatters as formatters
from cli.menu_helpers import MenuSignal
from core.utils import generate_uuid
from models.gradebook import Gradebook
from models.student import Student


def run(gradebook: Gradebook) -> None:
    """
    Top-level loop with dispatch for the Manage Students menu.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        - The finally block guarantees a check for unsaved changes before returning.
    """
    title = formatters.format_banner_text("Manage Students")
    options = [
        ("Add Student", add_student),
        ("Edit Student", find_and_edit_student),
        ("Remove Student", find_and_remove_student),
        ("View Students", view_students_menu),
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


# === add student ===


def add_student(gradebook: Gradebook) -> None:
    """
    Loops a prompt to create a new `Student` object and add it to the gradebook.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Additions are not saved automatically. If the gradebook is marked dirty after adding, the user will be prompted to save before returning to the previous menu.
    """
    while True:
        new_student = prompt_new_student(gradebook)

        if new_student is not None and preview_and_confirm_student(
            new_student, gradebook
        ):
            gradebook_response = gradebook.add_student(new_student)

            if not gradebook_response.success:
                helpers.display_response_failure(gradebook_response)
                print(f"\n{new_student.full_name} was not added.")

            else:
                print(f"\n{gradebook_response.detail}")

        if not helpers.confirm_action(
            "Would you like to continue adding new students?"
        ):
            break

    helpers.prompt_if_dirty(gradebook)

    helpers.returning_to("Manage Students menu")


def prompt_new_student(gradebook: Gradebook) -> Student | None:
    """
    Creates a new `Student` object.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        A new `Student` object, or None.
    """
    email = prompt_email_input_or_cancel(gradebook)

    if email is MenuSignal.CANCEL:
        return None
    email = cast(str, email)

    first_name = prompt_name_input_or_cancel(gradebook, "first")

    if first_name is MenuSignal.CANCEL:
        return None
    first_name = cast(str, first_name)

    last_name = prompt_name_input_or_cancel(gradebook, "last")

    if last_name is MenuSignal.CANCEL:
        return None
    last_name = cast(str, last_name)

    try:
        return Student(
            id=generate_uuid(),
            first_name=first_name,
            last_name=last_name,
            email=email,
        )

    except (TypeError, ValueError) as e:
        print(f"\n[ERROR] Could not create student: {e}")
        return None


def preview_and_confirm_student(student: Student, gradebook: Gradebook) -> bool:
    """
    Previews new `Student` details, offers opportunity to edit details, and prompts user for confirmation.

    Args:
        student (Student): The `Student` object under review.
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        True if user confirms the `Student` details, and False otherwise.
    """
    print("\nYou are about to create the following student:")
    print(model_formatters.format_student_multiline(student, gradebook))

    if helpers.confirm_action(
        "Would you like to edit this student first (change the name, email address, or enrollment status)?"
    ):
        edit_student(student, gradebook, "Student creation preview")

    if helpers.confirm_action("Would you like to create this student?"):
        return True

    else:
        print(f"\nDiscarding student: {student.full_name}")
        return False


# === data input helpers ===


def prompt_email_input_or_cancel(gradebook: Gradebook) -> str | MenuSignal:
    """
    Solicits user input for student email, validates formatting and uniqueness, and treats blank input as 'cancel'.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        The validated, normalized email address as a string, or `MenuSignal.CANCEL` if the user cancels input.

    Notes:
        - The email address is normalized (stripped and lowercased) before checking and returning.
        - If the input is invalid or not unique, the user is prompted again.
    """
    while True:
        email_input = helpers.prompt_user_input_or_cancel(
            "Enter email address (leave blank to cancel):"
        )

        if isinstance(email_input, MenuSignal):
            return email_input

        try:
            email = Student.validate_email_input(email_input)
            gradebook.require_unique_student_email(email)
            return email

        except ValueError as e:
            print(f"\n[ERROR] {e}")
            print("Please try again.")


def prompt_name_input_or_cancel(
    _: Gradebook, first_or_last: str = ""
) -> str | MenuSignal:
    """
    Solicits user input for student name (first or last), treating blank input as 'cancel'.

    Args:
        _ (Gradebook): The active `Gradebook` (unused).
        first_or_last (str): Optional string to prefix the prompt with 'first name' or 'last name'.

    Returns:
        User input unmodified, or `MenuSignal.CANCEL` if input is "".
    """
    # uses this structure in case validators are added later
    while True:
        name_input = helpers.prompt_user_input_or_cancel(
            f"Enter {(first_or_last + ' name').strip()} (leave blank to cancel):"
        )

        if isinstance(name_input, MenuSignal):
            return name_input

        try:
            return name_input

        except Exception as e:
            print(f"\n[ERROR] {e}")
            print("Please try again.")


# === edit student ===


def get_editable_fields() -> list[tuple[str, Callable[[Student, Gradebook], None]]]:
    """
    Helper method to organize the list of editable fields and their related functions.

    Returns:
        A list of `(field_name, edit_function)` tuples used to prompt and edit `Student` attributes.
    """
    return [
        ("First Name", edit_first_name_and_confirm),
        ("Last Name", edit_last_name_and_confirm),
        ("Email Address", edit_email_and_confirm),
        ("Enrollment Status", edit_active_status_and_confirm),
    ]


def find_and_edit_student(gradebook: Gradebook) -> None:
    """
    Prompts user to search for a `Student` and then passes the result to `edit_student()`.

    Args:
        gradebook (Gradebook): The active `Gradebook`.
    """
    student = prompt_find_student(gradebook)

    if student is MenuSignal.CANCEL:
        return
    student = cast(Student, student)

    edit_student(student, gradebook)


def edit_student(
    student: Student, gradebook: Gradebook, return_context: str = "Manage Students menu"
) -> None:
    """
    Interface for editing fields of a `Student` record.

    Args:
        student (Student): The `Student` object being edited.
        gradebook (Gradebook): The active `Gradebook`.
        return_context (str): An optional description of the call site, uses "Manage Students menu" by default.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        - All edit operations are dispatched through `Gradebook` to ensure proper mutation and state tracking.
        - Changes are not saved automatically. If the gradebook is marked dirty after edits, the user will be prompted to save before returning to the previous menu.
        - The `return_context` label is used to display a confirmation message when exiting the edit menu.
    """
    print("\nYou are editing the following student:")
    print(model_formatters.format_student_multiline(student, gradebook))

    title = formatters.format_banner_text("Editable Fields")
    options = get_editable_fields()
    zero_option = "Finish editing and return"

    while True:
        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response is MenuSignal.EXIT:
            break
        elif callable(menu_response):
            menu_response(student, gradebook)
        else:
            raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

        if not helpers.confirm_action(
            "Would you like to continue editing this student?"
        ):
            break

    if gradebook.has_unsaved_changes:
        helpers.prompt_if_dirty(gradebook)
    else:
        helpers.returning_without_changes()

    helpers.returning_to(return_context)


def edit_first_name_and_confirm(student: Student, gradebook: Gradebook) -> None:
    """
    Prompts for a new first name and updates the `Student` record via `Gradebook`.

    Args:
        student (Student): The `Student` object targeted for editing.
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Cancels early if the user enters nothing or declines the confirmation.
        - Uses `Gradebook.update_student_first_name()` to perform the update and track changes.
    """
    current_first_name = student.first_name
    new_first_name = prompt_name_input_or_cancel(gradebook, "first")

    if new_first_name is MenuSignal.CANCEL:
        helpers.returning_without_changes()
        return
    new_first_name = cast(str, new_first_name)

    print(
        f"\nCurrent first name: {current_first_name} -> New first name: {new_first_name}"
    )

    if not helpers.confirm_make_change():
        helpers.returning_without_changes()
        return

    gradebook_response = gradebook.update_student_first_name(student, new_first_name)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print("\nStudent name was not updated.")
        helpers.returning_without_changes()
    else:
        print(f"\n{gradebook_response.detail}")


def edit_last_name_and_confirm(student: Student, gradebook: Gradebook) -> None:
    """
    Prompts for a new last name and updates the `Student` record via `Gradebook`.

    Args:
        student (Student): The `Student` object targeted for editing.
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Cancels early if the user enters nothing or declines the confirmation.
        - Uses `Gradebook.update_student_last_name()` to perform the update and track changes.
    """
    current_last_name = student.last_name
    name_input = prompt_name_input_or_cancel(gradebook, "last")

    if name_input is MenuSignal.CANCEL:
        helpers.returning_without_changes()
        return

    new_last_name = cast(str, name_input)

    print(f"\nCurrent last name: {current_last_name} -> New last name: {new_last_name}")

    if not helpers.confirm_make_change():
        helpers.returning_without_changes()
        return

    gradebook_response = gradebook.update_student_last_name(student, new_last_name)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print("\nStudent name was not updated.")
        helpers.returning_without_changes()
    else:
        print(f"\n{gradebook_response.detail}")


def edit_email_and_confirm(student: Student, gradebook: Gradebook) -> None:
    """
    Prompts for a new email and updates the `Student` record via `Gradebook`.

    Args:
        student (Student): The `Student` targeted for editing.
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Cancels early if the user enters nothing or declines the confirmation.
        - Uses `Gradebook.update_student_email()` to perform the update and track changes.
    """
    current_email = student.email
    email_input = prompt_email_input_or_cancel(gradebook)

    if email_input is MenuSignal.CANCEL:
        helpers.returning_without_changes()
        return

    new_email = cast(str, email_input)

    print(f"\nCurrent email address: {current_email} -> New email address: {new_email}")

    if not helpers.confirm_make_change():
        helpers.returning_without_changes()
        return

    gradebook_response = gradebook.update_student_email(student, new_email)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print("\nStudent email was not updated.")
        helpers.returning_without_changes()
    else:
        print(f"\n{gradebook_response.detail}")


def edit_active_status_and_confirm(student: Student, gradebook: Gradebook) -> None:
    """
    Toggles the `is_active` field of a `Student` record via calls to `confirm_and_archive()` or `confirm_and_reactivate()`.

    Args:
        student (Student): The `Student` targeted for editing.
        gradebook (Gradebook): The active `Gradebook`.
    """
    print(f"\nThis student is currently {student.status}.")

    if not helpers.confirm_action("Do you want to edit the enrollment status?"):
        helpers.returning_without_changes()
        return

    if student.is_active:
        confirm_and_archive(student, gradebook)
    else:
        confirm_and_reactivate(student, gradebook)


# === remove student ===


def find_and_remove_student(gradebook: Gradebook) -> None:
    """
    Prompts user to search for a `Student` and then passes the result to `remove_student()`.

    Args:
        gradebook (Gradebook): The active `Gradebook`.
    """
    student_input = prompt_find_student(gradebook)

    if student_input is MenuSignal.CANCEL:
        return

    student = cast(Student, student_input)

    remove_student(student, gradebook)


def remove_student(student: Student, gradebook: Gradebook) -> None:
    """
    Interface for removing, archiving, or editing a `Student` record.

    Args:
        student (Student): The `Student` object targeted for deletion/archiving.
        gradebook (Gradebook): The active `Gradebook`.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        - All remove and edit operations are dispatched through `Gradebook` to ensure proper mutation and state tracking.
        - Changes are not saved automatically. If the gradebook is marked dirty, the user will be prompted to save before returning to the previous menu.
    """
    print("\nYou are viewing the following student:")
    print(model_formatters.format_student_oneline(student))

    title = "What would you like to do?"
    options = [
        (
            "Remove this student (permanently delete the student and all linked submissions)",
            confirm_and_remove,
        ),
        (
            "Archive this student (preserve all linked records)",
            confirm_and_archive,
        ),
        ("Edit this student instead", edit_student),
    ]
    zero_option = "Return to Manage Students menu"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response is MenuSignal.EXIT:
        helpers.returning_without_changes()
        return
    elif callable(menu_response):
        menu_response(student, gradebook)
    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

    if gradebook.has_unsaved_changes:
        helpers.prompt_if_dirty(gradebook)
    else:
        helpers.returning_without_changes()

    helpers.returning_to("Manage Students menu")


def confirm_and_remove(student: Student, gradebook: Gradebook) -> None:
    """
    Deletes the `Student` record and all linked `Submissions` from the `Gradebook` after preview and user confirmation.

    Args:
        student (Student): The `Student` targeted for deletion.
        gradebook (Gradebook): The active `Gradebook`.
    """
    helpers.caution_banner()
    print("You are about to permanently delete the following student record:")
    print(model_formatters.format_student_multiline(student, gradebook))
    print("\nThis will also delete all linked submissions.")

    confirm_deletion = helpers.confirm_action(
        "Are you sure you want to permanently delete this student? This action cannot be undone."
    )

    if not confirm_deletion:
        helpers.returning_without_changes()
        return

    gradebook_response = gradebook.remove_student(student)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print("\nStudent was not removed.")
        helpers.returning_without_changes()
    else:
        print(f"\n{gradebook_response.detail}")


def confirm_and_archive(student: Student, gradebook: Gradebook) -> None:
    """
    Archives an active `Student` after preview and confirmation.

    Args:
        student (Student): The `Student` targeted for archiving.
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Archiving preserves all linked `Submission` records but excludes the student from reports and calculation.
        - If the `Student` is already archived, the method exits early.
    """
    if not student.is_active:
        print("\nThis student has already been archived.")
        return

    print(
        "\nArchiving a student is a safe way to deactivate a student without losing data."
    )
    print("You are about to archive the following student record:")
    print(model_formatters.format_student_multiline(student, gradebook))
    print("\nThis will preserve all linked submissions,")
    print("but they will no longer appear in reports or grade calculations.")

    confirm_archiving = helpers.confirm_action(
        "Are you sure you want to archive this student?"
    )

    if not confirm_archiving:
        helpers.returning_without_changes()
        return

    gradebook_response = gradebook.toggle_student_active_status(student)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print("\nStudent status was not changed.")
        helpers.returning_without_changes()
    else:
        print(f"\n{gradebook_response.detail}")


def confirm_and_reactivate(student: Student, gradebook: Gradebook) -> None:
    """
    Reactivates an inactive `Student` after preview and confirmation.

    Args:
        student (Student): The `Student` targeted for reactivation.
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - If the `Student` is already active, the method exits early.
    """
    if student.is_active:
        print("\nThis student is already active.")
        return

    print("\nYou are about to reactivate the following student record:")
    print(model_formatters.format_student_multiline(student, gradebook))

    confirm_reactivate = helpers.confirm_action(
        "Are you sure you want to reactivate this student?"
    )

    if not confirm_reactivate:
        helpers.returning_without_changes()
        return

    gradebook_response = gradebook.toggle_student_active_status(student)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print("\nStudent status was not changed.")
        helpers.returning_without_changes()
    else:
        print(f"\n{gradebook_response.detail}")


# === view student ===


def view_students_menu(gradebook: Gradebook) -> None:
    """
    Displays the student view menu and dispatches selected view options.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        - Options include viewing individual, active, inactive, or all students.
    """
    title = "View Students"
    options = [
        ("View Individual Student", view_individual_student),
        ("View Active Students", view_active_students),
        ("View Inactive Students", view_inactive_students),
        ("View All Students", view_all_students),
    ]
    zero_option = "Return to Manage Students menu"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response is MenuSignal.EXIT:
        return
    elif callable(menu_response):
        menu_response(gradebook)
    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

    helpers.returning_to("Manage Students menu")


def view_individual_student(gradebook: Gradebook) -> None:
    """
    Displays a one-line summary of a selected `Student` record, with the option to view full details.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Uses `prompt_find_student()` to search for a record.
        - Prompts the user before displaying the multi-line format.
    """
    student_input = prompt_find_student(gradebook)

    if student_input is MenuSignal.CANCEL:
        return

    student = cast(Student, student_input)

    print("\nYou are viewing the following student record:")
    print(model_formatters.format_student_oneline(student))

    if helpers.confirm_action(
        "Would you like to see an expanded view of this student?"
    ):
        print(model_formatters.format_student_multiline(student, gradebook))


def view_active_students(gradebook: Gradebook) -> None:
    """
    Displays a sorted list of active `Student` records.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Uses `Gradebook.get_records()` with a filter for active students.
        - Records are sorted by last name, then first name.
    """
    banner = formatters.format_banner_text("Active Students")
    print(f"\n{banner}")

    gradebook_response = gradebook.get_records(
        gradebook.students, lambda x: x.is_active
    )

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        return

    active_students = gradebook_response.data["records"]

    if not active_students:
        print("There are no active students.")
        return

    helpers.sort_and_display_records(
        records=active_students,
        sort_key=lambda x: (x.last_name, x.first_name),
        formatter=model_formatters.format_student_oneline,
    )


def view_inactive_students(gradebook: Gradebook) -> None:
    """
    Displays a sorted list of inactive `Student` records.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Uses `Gradebook.get_records()` with a filter for inactive students.
        - Records are sorted by last name, then first name.
    """
    banner = formatters.format_banner_text("Inactive Students")
    print(f"\n{banner}")

    gradebook_response = gradebook.get_records(
        gradebook.students, lambda x: not x.is_active
    )

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        return

    inactive_students = gradebook_response.data["records"]

    if not inactive_students:
        print("There are no inactive students.")
        return

    helpers.sort_and_display_records(
        records=inactive_students,
        sort_key=lambda x: (x.last_name, x.first_name),
        formatter=model_formatters.format_student_oneline,
    )


def view_all_students(gradebook: Gradebook) -> None:
    """
    Displays a list of all `Students` records.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Uses `Gradebook.get_records()` to retrieve all students, active and inactive.
        - Records are sorted by last name, then first name.
    """
    banner = formatters.format_banner_text("All Students")
    print(f"\n{banner}")

    gradebook_response = gradebook.get_records(gradebook.students)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        return

    all_students = gradebook_response.data["records"]

    if not all_students:
        print("There are no students yet.")
        return

    helpers.sort_and_display_records(
        records=all_students,
        sort_key=lambda x: (x.last_name, x.first_name),
        formatter=model_formatters.format_student_oneline,
    )


# === finder methods ===


def prompt_find_student(gradebook: Gradebook) -> Student | MenuSignal:
    """
    Prompts the user to locate a `Student` record by search or list selection.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        Student | MenuSignal: The selected `Student`, or `MenuSignal.CANCEL` if canceled or no matches are found.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        - Offers search, active list, and inactive list as selection methods.
        - Returns early if the user chooses to cancel or if no selection is made.
    """
    title = formatters.format_banner_text("Student Selection")
    options = [
        ("Search for a student", helpers.find_student_by_search),
        ("Select from active students", helpers.find_active_student_from_list),
        ("Select from inactive students", helpers.find_inactive_student_from_list),
    ]
    zero_option = "Return and cancel"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response is MenuSignal.EXIT:
        return MenuSignal.CANCEL
    elif callable(menu_response):
        return menu_response(gradebook)
    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")
