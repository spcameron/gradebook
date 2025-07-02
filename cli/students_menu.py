# cli/students_menu.py

from cli.menu_helpers import display_menu, display_results, MenuSignal
from models.gradebook import Gradebook
from models.student import Student
from typing import Optional
from utils.utils import generate_uuid


def run(gradebook: Gradebook) -> None:
    title = f"=== MANAGE STUDENTS ==="
    options = {
        "Add Student": lambda: add_student(gradebook),
        "Edit Student": lambda: print("STUB: Edit Student"),
        "Remove Student": lambda: print("STUB: Remove Student"),
        "View Student Details": lambda: view_student(gradebook),
        "View All Students": lambda: view_all_students(gradebook),
    }
    zero_option = "Return to Course Menu"

    while True:
        result = display_menu(title, options, zero_option)
        if result == MenuSignal.EXIT:
            break


def add_student(gradebook: Gradebook) -> None:
    while True:
        student_last_name = input("Student last name: ").strip()
        student_first_name = input("Student first name: ").strip()
        student_email = input("Student email: ").strip()

        # minimal validation
        # TODO: validate email input
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
