# cli/students_menu.py

import cli.formatters as formatters
import cli.menu_helpers as helpers
from cli.menu_helpers import MenuSignal
from models.gradebook import Gradebook
from models.student import Student
from typing import cast, Callable, Optional
from utils.utils import generate_uuid


def run(gradebook: Gradebook) -> None:
    title = formatters.format_banner_text("Manage Students")
    options = [
        ("Add Student", add_student),
        ("Edit Student", edit_student),
        ("Remove Student", remove_student),
        ("View Students", view_students_menu),
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


# === add student ===


def add_student(gradebook: Gradebook) -> None:
    while True:
        new_student = prompt_new_student()

        if new_student is not None:
            gradebook.add_student(new_student)
            print(f"\n{new_student.full_name} successfully added to {gradebook.name}.")

        if not helpers.confirm_action(
            "Would you like to continue adding new students?"
        ):
            print(f"\nReturning to Manage Students menu.")
            return None


def prompt_new_student() -> Optional[Student]:
    # collect user input
    first_name = helpers.prompt_user_input_or_cancel(
        "Enter first name (leave blank to cancel):"
    )
    if first_name == MenuSignal.CANCEL:
        return None
    else:
        first_name = cast(str, first_name)

    last_name = helpers.prompt_user_input_or_cancel(
        "Enter last name (leave blank to cancel):"
    )
    if last_name == MenuSignal.CANCEL:
        return None
    else:
        last_name = cast(str, last_name)

    email = helpers.prompt_user_input_or_cancel(
        "Enter email address (leave blank to cancel):"
    )
    if email == MenuSignal.CANCEL:
        return None
    else:
        email = cast(str, email)

    # preview and confirm
    print("\nYou are about to create the following student:")
    print(f"... Name: {first_name} {last_name}")
    print(f"... Email: {email}")

    if not helpers.confirm_action("\nConfirm creation?"):
        return None

    # attempt object instantiation
    try:
        student_id = generate_uuid()
        new_student = Student(
            id=student_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )
    except Exception as e:
        print(f"\nError: Could not create student ... {e}")
        return None

    return new_student


# === edit student ===


def get_editable_fields() -> (
    list[tuple[str, Callable[[Student, Gradebook], Optional[MenuSignal]]]]
):
    return [
        ("First Name", edit_first_name_and_confirm),
        ("Last Name", edit_last_name_and_confirm),
        ("Email Address", edit_email_and_confirm),
        ("Enrollment Status", edit_active_status_and_confirm),
    ]


def edit_student(gradebook: Gradebook) -> None:
    search_results = helpers.search_students(gradebook)
    student = helpers.prompt_student_selection(search_results)

    if not student:
        return None

    title = formatters.format_banner_text("Editable Fields")
    options = get_editable_fields()
    zero_option = "Return without changes"

    while True:
        print("\nYou are viewing the following student record:")
        print(formatters.format_student_oneline(student))

        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response == MenuSignal.EXIT:
            helpers.returning_without_changes()
            return None

        if callable(menu_response):
            menu_response(student, gradebook)

        if not helpers.confirm_action(
            "Would you like to continue editing this student record?"
        ):
            print("\nReturning to Manage Students menu.")
            return None


def edit_first_name_and_confirm(student: Student, gradebook: Gradebook) -> None:
    current_first_name = student.first_name
    new_first_name = helpers.prompt_user_input(
        "Enter a new first name (leave blank to cancel):"
    )

    if new_first_name == "":
        helpers.returning_without_changes()
        return None

    print(
        f"\nCurrent first name: {current_first_name} ... New first name: {new_first_name}"
    )

    save_change = helpers.confirm_action("Do you want to save this change?")

    if not save_change:
        helpers.returning_without_changes()
        return None

    student.first_name = new_first_name
    gradebook.save(gradebook.path)
    print("\nFirst name successfully updated.")


def edit_last_name_and_confirm(student: Student, gradebook: Gradebook) -> None:
    current_last_name = student.last_name
    new_last_name = helpers.prompt_user_input(
        "Enter a new last name (leave blank to cancel):"
    )

    if new_last_name == "":
        helpers.returning_without_changes()
        return None

    print(
        f"\nCurrent last name: {current_last_name} ... New last name: {new_last_name}"
    )

    save_change = helpers.confirm_action("Do you want to save this change?")

    if not save_change:
        helpers.returning_without_changes()
        return None

    student.last_name = new_last_name
    gradebook.save(gradebook.path)
    print("\nLast name successfully updated.")


def edit_email_and_confirm(student: Student, gradebook: Gradebook) -> None:
    current_email = student.email
    new_email = helpers.prompt_user_input(
        "Enter a new email address (leave blank to cancel):"
    )

    if new_email == "":
        helpers.returning_without_changes()
        return None

    print(
        f"\nCurrent email address: {current_email} ... New email address: {new_email}"
    )

    save_change = helpers.confirm_action("Do you want to save this change?")

    if not save_change:
        helpers.returning_without_changes()
        return None

    student.email = new_email
    gradebook.save(gradebook.path)
    print("\nEmail address successfully updated.")


def edit_active_status_and_confirm(student: Student, gradebook: Gradebook) -> None:
    print(f"\nThis student is currently {student.status}.")

    if not helpers.confirm_action("Do you want to change the enrollment status?"):
        helpers.returning_without_changes()
        return None

    student.toggle_enrollment_status()
    gradebook.save(gradebook.path)
    print(f"\nEnrollment status successfully updated to {student.status}.")


# === remove student ===


def remove_student(gradebook: Gradebook) -> None:
    search_results = helpers.search_students(gradebook)
    student = helpers.prompt_student_selection(search_results)

    if not student:
        return None

    print("\nYou are viewing the following student record:")
    print(formatters.format_student_oneline(student))

    title = "What would you like to do?"
    options = [
        ("Permanently remove this student (destroys record)", confirm_and_remove),
        (
            "Change enrollment status instead (archives record)",
            edit_active_status_and_confirm,
        ),
    ]
    zero_option = "Return to Manage Students menu"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response == MenuSignal.EXIT:
        helpers.returning_without_changes()
        return None

    if callable(menu_response):
        menu_response(student, gradebook)


def confirm_and_remove(student: Student, gradebook: Gradebook) -> None:
    caution_banner = formatters.format_banner_text("CAUTION!")
    print(f"\n{caution_banner}")
    print("You are about to permanently delete the following student record:")
    print(formatters.format_student_oneline(student))

    confirm_deletion = helpers.confirm_action(
        "Are you sure you want to permanently remove this student? This action cannot be undone."
    )

    if not confirm_deletion:
        helpers.returning_without_changes()
        return None

    gradebook.remove_student(student)
    gradebook.save(gradebook.path)
    print("\nStudent record successfully removed from Gradebook.")


# === view student ===


def view_students_menu(gradebook: Gradebook) -> None:
    title = "View Students"
    options = [
        ("View Individual Student", view_individual_student),
        ("View Active Students", view_active_students),
        ("View Inactive Students", view_inactive_students),
        ("View All Students", view_all_students),
    ]
    zero_option = "Return to Manage Students menu"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response == MenuSignal.EXIT:
        return None

    if callable(menu_response):
        menu_response(gradebook)


# TODO: display "short" report first, prompt for "long" report second
def view_individual_student(gradebook: Gradebook) -> None:
    search_results = helpers.search_students(gradebook)
    student = helpers.prompt_student_selection(search_results)

    if not student:
        return None

    print("\nYou are viewing the following student record:")
    print(formatters.format_student_oneline(student))


def view_active_students(gradebook: Gradebook) -> None:
    print(f"\n{formatters.format_banner_text("Active Students")}")

    active_students = gradebook.get_records(gradebook.students, lambda x: x.is_active)

    if not active_students:
        print("There are no active students.")
        return None

    sort_and_display_students(active_students)


def view_inactive_students(gradebook: Gradebook) -> None:
    print(f"\n{formatters.format_banner_text("Inactive Students")}")

    inactive_students = gradebook.get_records(
        gradebook.students, lambda x: not x.is_active
    )

    if not inactive_students:
        print("There are no inactive students.")
        return None

    sort_and_display_students(inactive_students)


def view_all_students(gradebook: Gradebook) -> None:
    print(f"\n{formatters.format_banner_text("All Students")}")

    all_students = gradebook.get_records(gradebook.students)

    if not all_students:
        print("There are no students yet.")
        return None

    sort_and_display_students(all_students)


def sort_and_display_students(roster: list[Student]) -> None:
    sorted_roster = sorted(roster, key=lambda x: (x.last_name, x.first_name))
    helpers.display_results(sorted_roster, False, formatters.format_student_oneline)
