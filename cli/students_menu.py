# cli/students_menu.py

from cli.menu_helpers import confirm_action, display_menu, display_results, MenuSignal
from models.gradebook import Gradebook
from models.student import Student
from typing import Callable, Optional
from utils.utils import generate_uuid


def run(gradebook: Gradebook) -> None:
    title = f"=== Manage Students ==="
    options = [
        ("Add Student", add_student),
        ("Edit Student", edit_student),
        ("Remove Student", remove_student),
        ("View Student Details", view_student),
        ("View All Students", view_all_students),
    ]
    zero_option = "Return to Course Menu"

    while True:
        menu_response = display_menu(title, options, zero_option)

        if menu_response == MenuSignal.EXIT:
            break

        if isinstance(menu_response, Callable):
            menu_response(gradebook)


def add_student(gradebook: Gradebook) -> None:
    while True:
        student_first_name = input("Student first name: ").strip()
        student_last_name = input("Student last name: ").strip()
        student_email = input("Student email: ").strip()

        # minimal validation
        if student_last_name and student_first_name and student_email:
            break
        else:
            print("Full name and email are required.")

    student_id = generate_uuid()

    new_student = Student(
        student_id, student_first_name, student_last_name, student_email
    )
    gradebook.add_student(new_student)
    print(f"Student {new_student.full_name} added.")


def edit_student(gradebook: Gradebook) -> None:
    search_results = search_students(gradebook)
    student = prompt_student_selection(search_results)
    if student:
        title = "=== Editable Fields ==="
        options = get_editable_fields()
        zero_option = "Return without changes"

        while True:
            menu_response = display_menu(title, options, zero_option)

            if menu_response == MenuSignal.EXIT:
                return

            if isinstance(menu_response, Callable):
                menu_response(student, gradebook)


def edit_first_name_and_confirm(
    student: Student, gradebook: Gradebook
) -> MenuSignal | None:
    current_first_name = student.first_name
    new_first_name = input("Enter a new first name (leave blank to cancel): ").strip()

    if new_first_name == "":
        return

    print(f"Current first name: {current_first_name}")
    print(f"New first name: {new_first_name}")
    save_change = confirm_action("Do you want to save this change?")

    if save_change:
        student.first_name = new_first_name
        gradebook.save(gradebook.path)
        print("First name successfully updated!")
    else:
        print("No changes made. Returning to Manage Students menu.")
        return MenuSignal.EXIT


def edit_last_name_and_confirm(
    student: Student, gradebook: Gradebook
) -> MenuSignal | None:
    current_last_name = student.last_name
    new_last_name = input("Enter a new last name (leave blank to cancel): ").strip()

    if new_last_name == "":
        return

    print(f"Current last name: {current_last_name}")
    print(f"New last name: {new_last_name}")
    save_change = confirm_action("Do you want to save this change?")

    if save_change:
        student.last_name = new_last_name
        gradebook.save(gradebook.path)
        print("Last name successfully updated.")
    else:
        print("No changes made. Returning to Manage Students menu.")
        return MenuSignal.EXIT


def edit_email_and_confirm(student: Student, gradebook: Gradebook) -> MenuSignal | None:
    current_email = student.email
    new_email = input("Enter a new email address (leave blank to cancel): ").strip()

    if new_email == "":
        return

    print(f"Current email address: {current_email}")
    print(f"New email address: {new_email}")
    save_change = confirm_action("Do you want to save this change?")

    if save_change:
        student.email = new_email
        gradebook.save(gradebook.path)
        print("Email address successfully updated.")
    else:
        print("No changes made.. Returning to Manage Students menu.")
        return MenuSignal.EXIT


def edit_status_and_confirm(
    student: Student, gradebook: Gradebook
) -> MenuSignal | None:
    current_status = student.status

    print(f"Current enrollment status: {current_status}.")

    toggle_status = confirm_action("Do you want to change the enrollment status?")

    if toggle_status:
        student.toggle_enrollment_status()
        gradebook.save(gradebook.path)
        print(f"Enrollment status successfully updated to {student.status}")
    else:
        print("No changes made. Returning to Manage Students menu.")
        return MenuSignal.EXIT


def get_editable_fields() -> (
    list[tuple[str, Callable[[Student, Gradebook], MenuSignal | None]]]
):
    return [
        ("First Name", edit_first_name_and_confirm),
        ("Last Name", edit_last_name_and_confirm),
        ("Email Address", edit_email_and_confirm),
        ("Enrollment Status", edit_status_and_confirm),
    ]


def remove_student(gradebook: Gradebook) -> None:
    search_results = search_students(gradebook)
    student = prompt_student_selection(search_results)

    if not student:
        return

    print("You are viewing the following student record:")
    print(format_name_and_email(student))

    title = "What would you like to do?"
    options = [
        ("Permanently remove this student (destroys record)", confirm_and_remove),
        ("Change enrollment status instead (archives record)", edit_status_and_confirm),
    ]
    zero_option = "Return to Manage Students menu"

    menu_response = display_menu(title, options, zero_option)

    if menu_response == MenuSignal.EXIT:
        return

    if isinstance(menu_response, Callable):
        menu_response(student, gradebook)


def confirm_and_remove(student: Student, gradebook: Gradebook) -> None:
    print("===== CAUTION =====")
    print("You are about to permanently delete the following student record:")
    print(format_name_and_email(student))

    confirm_deletion = confirm_action(
        "Are you sure you want to permanently remove this student? This action cannot be undone."
    )

    if confirm_deletion:
        gradebook.remove_student(student)
        gradebook.save(gradebook.path)
        print("Student record successfully removed from Gradebook.")
    else:
        print("No changes made. Returning to Manage Students menu.")


def view_student(gradebook: Gradebook) -> None:
    search_results = search_students(gradebook)
    student = prompt_student_selection(search_results)
    if student:
        print(format_name_and_email(student))


def view_all_students(gradebook: Gradebook) -> None:
    course_name = gradebook.metadata["name"]
    course_term = gradebook.metadata["term"]
    print(f"\nStudent Roster for {course_name} - {course_term}:\n")

    roster = list(gradebook.students.values())
    if not roster:
        print("No students enrolled yet.")
        return

    sorted_roster = sorted(roster, key=lambda s: (s.last_name, s.first_name))
    display_results(sorted_roster, False, format_name_and_email)


def search_students(gradebook: Gradebook) -> list[Student]:
    query = input("Search for a student by name or email: ").strip().lower()
    matches = [
        student
        for student in gradebook.students.values()
        if query in student.full_name.lower() or query in student.email.lower()
    ]
    return matches


def prompt_student_selection(search_results: list[Student]) -> Optional[Student]:
    if not search_results:
        print("No matching students found.")
        return

    if len(search_results) == 1:
        return search_results[0]

    print(f"Your search returned {len(search_results)} students: ")

    while True:
        display_results(search_results, True, format_name_and_email)
        choice = input("\nSelect an option (0 to cancel): ").strip()

        if choice == "0":
            return None
        try:
            index = int(choice) - 1
            return search_results[index]
        except (ValueError, IndexError):
            print("Invalid selection. Please try again.")


def format_name_and_email(student: Student) -> str:
    return f"{student.full_name:<20} | {student.email}"
