# cli/students_menu.py

"""
Manage Students menu for the Gradebook CLI.

Provides functions for adding, editing, removing, and viewing Students.
"""

from typing import Callable, Optional, cast

import cli.formatters as formatters
import cli.menu_helpers as helpers
from cli.menu_helpers import MenuSignal
from core.utils import generate_uuid
from models.gradebook import Gradebook
from models.student import Student


def run(gradebook: Gradebook) -> None:
    """
    Top-level loop with dispatch for the Manage Students menu.

    Args:
        gradebook: The active Gradebook.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        The finally block guarantees a check for unsaved changes before returning.
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
    Loops a prompt to create a new Student and add to the Gradebook.

    Args:
        gradebook: The active Gradebook.

    Notes:
        New Students are added to the Gradebook but not saved. Gradebook is marked dirty instead.
    """
    while True:
        new_student = prompt_new_student(gradebook)

        if new_student is not None and preview_and_confirm_student(
            new_student, gradebook
        ):
            gradebook.add_student(new_student)
            gradebook.mark_dirty()
            print(f"\n{new_student.full_name} successfully added.")

        if not helpers.confirm_action(
            "Would you like to continue adding new students?"
        ):
            break

    helpers.returning_to("Manage Students menu")


def prompt_new_student(gradebook: Gradebook) -> Optional[Student]:
    """
    Creates a new Student.

    Args:
        gradebook: The active Gradebook.

    Returns:
        A new Student object, or None.
    """
    email = prompt_email_input_or_cancel(gradebook)

    if email is MenuSignal.CANCEL:
        return None
    else:
        email = cast(str, email)

    first_name = prompt_name_input_or_cancel(gradebook, "first")

    if first_name is MenuSignal.CANCEL:
        return None
    else:
        first_name = cast(str, first_name)

    last_name = prompt_name_input_or_cancel(gradebook, "last")

    if last_name is MenuSignal.CANCEL:
        return None
    else:
        last_name = cast(str, last_name)

    try:
        student_id = generate_uuid()
        new_student = Student(
            id=student_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )
        return new_student
    except Exception as e:
        print(f"\nError: Could not create student ... {e}")
        return None


def preview_and_confirm_student(student: Student, gradebook: Gradebook) -> bool:
    """
    Preview Student details, offers opportunity to edit details, and prompts user for confirmation.

    Args:
        student: The Student under review.
        gradebook: The active Gradebook.

    Notes:
        Uses edit_queued_student() since this Student object has not yet been added to the Gradebook.
    """
    print("\nYou are about to create the following student:")
    print(formatters.format_student_multiline(student, gradebook))

    if helpers.confirm_action(
        "Would you like to edit this student first (change the name, email address, or enrollment status)?"
    ):
        edit_queued_student(student, gradebook)

    if helpers.confirm_action("Would you like to create this student?"):
        return True
    else:
        print("Discarding assignment.")
        return False


# === data input helpers ===


def prompt_email_input_or_cancel(gradebook: Gradebook) -> str | MenuSignal:
    """
    Solicits user input for Student email, validates formatting and uniqueness, and treats blank input as 'cancel'.

    Args:
        gradebook: The active Gradebook.

    Returns:
        The validated, normalized email address as a string, or MenuSignal.CANCEL if the user cancels input.

    Notes:
        The email address is normalized (stripped and lowercase) before checking and returning.
    """
    while True:
        user_input = helpers.prompt_user_input_or_cancel(
            "Enter email address (leave blank to cancel):"
        )

        if isinstance(user_input, MenuSignal):
            return user_input

        try:
            email = Student.validate_email_input(user_input)
            gradebook.require_unique_student_email(email)
            return email
        except ValueError as e:
            print(f"\nError: {e}")


def prompt_name_input_or_cancel(
    _: Gradebook, first_or_last: str = ""
) -> str | MenuSignal:
    """
    Solicits user input for Student name (first or last), treating blank input as 'cancel'.

    Args:
        _: The active Gradebook.
        first_or_last: Optional string to prefix the prompt with 'first name' or 'last name'.

    Returns:
        User input unmodified, or MenuSignal.CANCEL if input is "".
    """
    return helpers.prompt_user_input_or_cancel(
        f"Enter {(first_or_last + ' name').strip()} (leave blank to cancel):"
    )


# === edit student ===


def get_editable_fields() -> list[tuple[str, Callable[[Student, Gradebook], bool]]]:
    """
    Helper method to organize the list of editable fields and their related functions.

    Returns:
        A list of tuples - pairs of strings and function names.
    """
    return [
        ("First Name", edit_first_name_and_confirm),
        ("Last Name", edit_last_name_and_confirm),
        ("Email Address", edit_email_and_confirm),
        ("Enrollment Status", edit_active_status_and_confirm),
    ]


def find_and_edit_student(gradebook: Gradebook) -> None:
    """
    Prompts user to search for a Student and then passes the result to edit_student().

    Args:
        gradebook: The active Gradebook.
    """
    student = prompt_find_student(gradebook)

    if student is MenuSignal.CANCEL:
        return None
    else:
        student = cast(Student, student)
        edit_student(student, gradebook)


def edit_student(student: Student, gradebook: Gradebook) -> None:
    """
    Dispatch method for selecting an editable field and using boolean return values to monitor whether changes have been made.

    Args:
        student: The Student being edited.
        gradebook: The active Gradebook.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        Uses a function scoped variable to flag whether the edit_* methods have manipulated the Student at all.
        If so, the user is prompted to either save changes now, or defer and mark the Gradebook dirty for saving upstream.
    """
    print("\nYou are editing the following student:")
    print(formatters.format_student_multiline(student, gradebook))

    title = formatters.format_banner_text("Editable Fields")
    options = get_editable_fields()
    zero_option = "Finish editing and return"

    unsaved_changes = False

    while True:
        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response is MenuSignal.EXIT:
            break
        elif callable(menu_response):
            if menu_response(student, gradebook):
                unsaved_changes = True
        else:
            raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

        if not helpers.confirm_action(
            "Would you like to continue editing this student?"
        ):
            break

    if unsaved_changes:
        if helpers.confirm_unsaved_changes():
            gradebook.save(gradebook.path)
        else:
            gradebook.mark_dirty()
    else:
        helpers.returning_without_changes()

    helpers.returning_to("Manage Students menu")


def edit_queued_student(student: Student, gradebook: Gradebook) -> None:
    """
    Dispatch method for the edit menu that does not track changes, since the edited Student has not yet been added to the Gradebook.

    Args:
        student: The Student not yet added to the Gradebook and targeted for editing.
        gradebook: The active Gradebook.

    Raises:
        RuntimeError: If the menu response is unrecognized.
    """
    print("\nYou are editing the following student:")
    print(formatters.format_student_multiline(student, gradebook))

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

    helpers.returning_to("Student creation")


def edit_first_name_and_confirm(student: Student, gradebook: Gradebook) -> bool:
    """
    Edit the first_name field of a Student.

    Args:
        student: The Student targeted for editing.
        gradebook: The active Gradebook.

    Returns:
        True if the name was changed, and False otherwise.
    """
    current_first_name = student.first_name
    new_first_name = prompt_name_input_or_cancel(gradebook, "first")

    if new_first_name is MenuSignal.CANCEL:
        helpers.returning_without_changes()
        return False
    else:
        new_first_name = cast(str, new_first_name)

    print(
        f"\nCurrent first name: {current_first_name} ... New first name: {new_first_name}"
    )

    if not helpers.confirm_make_change():
        helpers.returning_without_changes()
        return False

    try:
        student.first_name = new_first_name
        print("\nFirst name successfully updated to: {student.first_name}x")
        return True
    except Exception as e:
        print(f"\nError: Could not update student ... {e}")
        helpers.returning_without_changes()
        return False


def edit_last_name_and_confirm(student: Student, gradebook: Gradebook) -> bool:
    """
    Edit the last_name field of a Student.

    Args:
        student: The Student targeted for editing.
        gradebook: The active Gradebook.

    Returns:
        True if the name was changed, and False otherwise.
    """
    current_last_name = student.last_name
    new_last_name = prompt_name_input_or_cancel(gradebook, "last")

    if new_last_name is MenuSignal.CANCEL:
        helpers.returning_without_changes()
        return False
    else:
        new_last_name = cast(str, new_last_name)

    print(
        f"\nCurrent last name: {current_last_name} ... New last name: {new_last_name}"
    )

    if not helpers.confirm_make_change():
        helpers.returning_without_changes()
        return False

    try:
        student.last_name = new_last_name
        print(f"\nLast name successfully updated to: {student.last_name}.")
        return True
    except Exception as e:
        print(f"\nError: Could not update student ... {e}")
        helpers.returning_without_changes()
        return False


def edit_email_and_confirm(student: Student, gradebook: Gradebook) -> bool:
    """
    Edit the email field of a Student.

    Args:
        student: The Student targeted for editing.
        gradebook: The active Gradebook.

    Returns:
        True if the email was chnaged, and False otherwise.
    """
    current_email = student.email
    new_email = prompt_email_input_or_cancel(gradebook)

    if new_email is MenuSignal.CANCEL:
        helpers.returning_without_changes()
        return False
    else:
        new_email = cast(str, new_email)

    print(
        f"\nCurrent email address: {current_email} ... New email address: {new_email}"
    )

    if not helpers.confirm_make_change():
        helpers.returning_without_changes()
        return False

    try:
        student.email = new_email
        print(f"\nEmail address successfully updated to: {student.email}.")
        return True
    except Exception as e:
        print(f"\nError: Could not update student ... {e}")
        helpers.returning_without_changes()
        return False


def edit_active_status_and_confirm(student: Student, gradebook: Gradebook) -> bool:
    """
    Toggles the is_active field of a Student via calls to confirm_and_archive() or confirm_and_reactivate().

    Args:
        student: The Student targeted for editing.
        gradebook: The Active Gradebook.

    Returns:
        True if the active status was changed, and False otherwise.
    """
    print(f"\nThis student is currently {student.status}.")

    if not helpers.confirm_action("Do you want to edit the enrollment status?"):
        helpers.returning_without_changes()
        return False

    if student.is_active:
        return confirm_and_archive(student, gradebook)
    else:
        return confirm_and_reactivate(student, gradebook)


# === remove student ===


def find_and_remove_student(gradebook: Gradebook) -> None:
    """
    Prompts user to search for a Student and then passes the result to remove_student().

    Args:
        gradebook: The active Gradebook.
    """
    student = prompt_find_student(gradebook)

    if student is MenuSignal.CANCEL:
        return None
    else:
        student = cast(Student, student)
        remove_student(student, gradebook)


def remove_student(student: Student, gradebook: Gradebook) -> None:
    """
    Dispatch method to either delete, archive, or edit the Student, or return without changes.

    Args:
        student: The Student targeted for deletion/archiving.
        gradebook: The active Gradebook.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        Uses a function scoped variable to detect if any function calls report data manipulation.
        If so, the user is prompted to either save now or defer, in which case the Gradebook is marked dirty.
    """
    print("\nYou are viewing the following student record:")
    print(formatters.format_student_oneline(student))

    title = "What would you like to do?"
    options = [
        (
            "Remove this student (permanently delete the student and all linked submissions)",
            confirm_and_remove,
        ),
        (
            "Archive this student instead (preserve all linked records)",
            confirm_and_archive,
        ),
        ("Edit this student instead", edit_student),
    ]
    zero_option = "Return to Manage Students menu"

    unsaved_changes = False

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response is MenuSignal.EXIT:
        helpers.returning_without_changes()
        return None
    elif callable(menu_response):
        if menu_response(student, gradebook):
            unsaved_changes = True
    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

    if unsaved_changes:
        if helpers.confirm_unsaved_changes():
            gradebook.save(gradebook.path)
        else:
            gradebook.mark_dirty()

    helpers.returning_to("Manage Students menu")


def confirm_and_remove(student: Student, gradebook: Gradebook) -> bool:
    """
    Deletes the Student from the Gradebook after preview and confirmation.

    Args:
        student: The Student targeted for deletion.
        gradebook: The active Gradebook.

    Returns:
        True if the Student was removed, and False otherwise.
    """
    caution_banner = formatters.format_banner_text("CAUTION!")
    print(f"\n{caution_banner}")
    print("You are about to permanently delete the following student record:")
    print(formatters.format_student_multiline(student, gradebook))
    print("\nThis will also delete all linked submissions.")

    confirm_deletion = helpers.confirm_action(
        "Are you sure you want to permanently delete this student? This action cannot be undone."
    )

    if not confirm_deletion:
        helpers.returning_without_changes()
        return False

    try:
        gradebook.remove_student(student)
        print("\nStudent successfully removed from Gradebook.")
        return True
    except Exception as e:
        print(f"\nError: Could not remove student ... {e}")
        helpers.returning_without_changes()
        return False


def confirm_and_archive(student: Student, gradebook: Gradebook) -> bool:
    """
    Toggles the is_active field of an active Student, after preview and confirmation.

    Args:
        student: The Student targeted for archiving.
        gradebook: The active Gradebook.

    Returns:
        True if the active status was changed, and False otherwise.
    """
    if not student.is_active:
        print("\nThis student has already been archived.")
        return False

    print(
        "\nArchiving a student is a safe way to deactivate a student without losing data."
    )
    print("You are about to archive the following student:")
    print(formatters.format_student_multiline(student, gradebook))
    print("\nThis will preserve all linked submissions,")
    print("but they will not longer appear in reports or grade calculations.")

    confirm_archiving = helpers.confirm_action(
        "Are you sure you want to archive this student?"
    )

    if not confirm_archiving:
        helpers.returning_without_changes()
        return False

    try:
        student.toggle_archived_status()
        print(f"\nStudent status successfully updated to: {student.status}")
        return True
    except Exception as e:
        print(f"\nError: Could nt update student ... {e}")
        helpers.returning_without_changes()
        return False


def confirm_and_reactivate(student: Student, gradebook: Gradebook) -> bool:
    """
    Toggles the is_active field of an inactive Student, after preview and confirmation.

    Args:
        student: The Student targeted for reactivation.
        gradebook: The active Gradebook.

    Returns:
        True if the active status was changed, and False otherwise.
    """
    if student.is_active:
        print("\nThis student is already active.")
        return False

    print("\nYou are about to reactivate the following student:")
    print(formatters.format_student_multiline(student, gradebook))

    confirm_reactivate = helpers.confirm_action(
        "Are you sure you want to reactive this student?"
    )

    if not confirm_reactivate:
        helpers.returning_without_changes()
        return False

    try:
        student.toggle_archived_status()
        print(f"\nStudent status sucessfully updated to: {student.status}.")
        return True
    except Exception as e:
        print(f"\nError: Could not update student ... {e}")
        helpers.returning_without_changes()
        return False


# === view student ===


def view_students_menu(gradebook: Gradebook) -> None:
    """
    Dispatch method for the various view options (individual, active, inactive, all).

    Args:
        gradebook: The active Gradebook.

    Raises:
        RuntimeError: If the menu response is unrecognized.
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
        return None
    elif callable(menu_response):
        menu_response(gradebook)
    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")


def view_individual_student(gradebook: Gradebook) -> None:
    """
    Calls find_student() and then displays a one-line view of that Student, followed by a prompt to view the multi-line view or return.

    Args:
        gradebook: The active Gradebook.
    """
    student = prompt_find_student(gradebook)

    if student is MenuSignal.CANCEL:
        return None
    else:
        student = cast(Student, student)

    print("\nYou are viewing the following student record:")
    print(formatters.format_student_oneline(student))

    if helpers.confirm_action(
        "Would you like to see an expanded view of this student?"
    ):
        print(formatters.format_student_multiline(student, gradebook))


def view_active_students(gradebook: Gradebook) -> None:
    """
    Displays a list of active Students.

    Args:
        gradebook: The active Gradebook.
    """
    banner = formatters.format_banner_text("Active Students")
    print(f"\n{banner}")

    active_students = gradebook.get_records(gradebook.students, lambda x: x.is_active)

    if not active_students:
        print("There are no active students.")
        return None

    helpers.sort_and_display_records(
        records=active_students,
        sort_key=lambda x: (x.last_name, x.first_name),
        formatter=formatters.format_student_oneline,
    )


def view_inactive_students(gradebook: Gradebook) -> None:
    """
    Displays a list of inactive Student.

    Args:
        gradebook: The active Gradebook.
    """
    banner = formatters.format_banner_text("Inactive Students")
    print(f"\n{banner}")

    inactive_students = gradebook.get_records(
        gradebook.students, lambda x: not x.is_active
    )

    if not inactive_students:
        print("There are no inactive students.")
        return None

    helpers.sort_and_display_records(
        records=inactive_students,
        sort_key=lambda x: (x.last_name, x.first_name),
        formatter=formatters.format_student_oneline,
    )


def view_all_students(gradebook: Gradebook) -> None:
    """
    Displays a list of all Students.

    Args:
        gradebook: The active Gradebook.
    """
    banner = formatters.format_banner_text("All Students")
    print(f"\n{banner}")

    all_students = gradebook.get_records(gradebook.students)

    if not all_students:
        print("There are no students yet.")
        return None

    helpers.sort_and_display_records(
        records=all_students,
        sort_key=lambda x: (x.last_name, x.first_name),
        formatter=formatters.format_student_oneline,
    )


# === finder methods ===


def prompt_find_student(gradebook: Gradebook) -> Student | MenuSignal:
    """
    Menu dispatch for either finding a Student by search or from a list of Students (separate lists for active and inactive).

    Args:
        gradebook: The active Gradebook.

    Returns:
        The selected Student, or MenuSignal.CANCEL if either the user cancels or the search yields no hits.

    Raises:
        RuntimeError: If the menu response is unrecognized.
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
