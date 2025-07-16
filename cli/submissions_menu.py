# cli/submissions_menu.py

import cli.formatters as formatters
import cli.menu_helpers as helpers
from cli.menu_helpers import MenuSignal
from models.assignment import Assignment
from models.gradebook import Gradebook
from models.student import Student
from models.submission import Submission
from typing import assert_never, cast, Callable, Optional
from utils.utils import generate_uuid


def run(gradebook: Gradebook) -> None:
    title = formatters.format_banner_text("Manage Submissions")
    options = [
        ("Add Single Submission", add_single_submission),
        ("Batch Enter Submissions by Assignment", add_submissions_by_assignment),
        ("Edit Submission", edit_submission),
        ("Remove Submission", remove_submission),
        ("View Submissions", view_submissions_menu),
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


# === add submission ===


def add_single_submission(gradebook: Gradebook) -> None:
    while True:
        linked_assignment = prompt_linked_assignment(gradebook)
        if linked_assignment == MenuSignal.CANCEL:
            return None
        else:
            linked_assignment = cast(Assignment, linked_assignment)

        linked_student = prompt_linked_student(gradebook)
        if linked_student == MenuSignal.CANCEL:
            return None
        else:
            linked_student = cast(Student, linked_student)

        new_submission = prompt_new_submission(
            linked_assignment, linked_student, gradebook
        )

        if new_submission is not None and preview_and_confirm_submission(
            new_submission, gradebook
        ):
            gradebook.add_submission(new_submission)
            assignment_name = linked_assignment.name
            student_name = linked_student.full_name
            print(
                f"\nSubmission for {student_name} to {assignment_name} successfully added to {gradebook.name}"
            )

        if not helpers.confirm_action(
            "Would you like to continue adding new submissions?"
        ):
            print("\nReturning to Manage Submissions menu")
            return None


# TODO: this is the special batch entry process
def add_submissions_by_assignment(gradebook: Gradebook) -> None:
    pass


def prompt_new_submission(
    linked_assignment: Assignment, linked_student: Student, gradebook: Gradebook
) -> Optional[Submission]:
    # check for existing submission with same student/asssignment already
    if gradebook.submission_already_exists(linked_assignment.id, linked_student.id):
        handle_existing_submission(linked_assignment, linked_student, gradebook)
        return None

    # alert to linked assignment and linked student
    print(f"\nAssignment: {linked_assignment.name}")
    print(f"Student: {linked_student.full_name}")

    # collect user input
    points_earned_str = prompt_points_earned_input()
    if points_earned_str == MenuSignal.CANCEL:
        return None
    else:
        points_earned_str = cast(str, points_earned_str)

    # TODO:
    # preview and confirm is found in add_single_submission
    # export this pattern to Assignments, Categories, and Students

    try:
        points_earned = float(points_earned_str)
        submission_id = generate_uuid()

        new_submission = Submission(
            id=submission_id,
            student_id=linked_student.id,
            assignment_id=linked_assignment.id,
            score=points_earned,
        )
    except (TypeError, ValueError) as e:
        print(f"\nError: Could not create submission ... {e}")
        return None

    return new_submission


def prompt_linked_assignment(gradebook: Gradebook) -> Assignment | MenuSignal:
    title = formatters.format_banner_text("Assignment Selection")
    options = [
        ("Search for an assignment", link_assignment_by_search),
        ("Select from active assignments", link_assignment_from_list),
    ]
    zero_option = "Return and cancel"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response == MenuSignal.EXIT:
        return MenuSignal.CANCEL

    if callable(menu_response):
        return menu_response(gradebook)

    raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")


def link_assignment_by_search(
    gradebook: Gradebook,
) -> Assignment | MenuSignal:
    search_results = helpers.search_assignments(gradebook)
    assignment = helpers.prompt_assignment_selection_from_search(search_results)
    return MenuSignal.CANCEL if assignment is None else assignment


def link_assignment_from_list(
    gradebook: Gradebook,
) -> Assignment | MenuSignal:
    active_assignments = gradebook.get_records(
        gradebook.assignments, lambda x: x.is_active
    )
    assignment = helpers.prompt_assignment_selection_from_list(
        active_assignments, "Active Assignments"
    )
    return MenuSignal.CANCEL if assignment is None else assignment


def prompt_linked_student(gradebook: Gradebook) -> Student | MenuSignal:
    title = formatters.format_banner_text("Student Selection")
    options = [
        ("Search for a student", link_student_by_search),
        ("Select from active students", link_student_from_list),
    ]
    zero_option = "Return and cancel"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response == MenuSignal.EXIT:
        return MenuSignal.CANCEL

    if callable(menu_response):
        return menu_response(gradebook)

    raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")


def link_student_by_search(gradebook: Gradebook) -> Student | MenuSignal:
    search_results = helpers.search_students(gradebook)
    student = helpers.prompt_student_selection_from_search(search_results)
    return MenuSignal.CANCEL if student is None else student


def link_student_from_list(gradebook: Gradebook) -> Student | MenuSignal:
    active_students = gradebook.get_records(gradebook.students, lambda x: x.is_active)
    student = helpers.prompt_student_selection_from_list(
        active_students, "Active Students"
    )
    return MenuSignal.CANCEL if student is None else student


def preview_and_confirm_submission(
    submission: Submission, gradebook: Gradebook
) -> bool:
    student = gradebook.find_student_by_uuid(submission.student_id)
    assignment = gradebook.find_assignment_by_uuid(submission.assignment_id)

    if not student or not assignment:
        return False

    print("\nYou are about to add the following submission:")
    print(f"...Assignment: {assignment.name}")
    print(f"...Student: {student.full_name}")
    print(f"...Score: {submission.points_earned} / {assignment.points_possible}")

    return helpers.confirm_action("\nConfirm creation?")


def handle_existing_submission(
    linked_assignment: Assignment, linked_student: Student, gradebook: Gradebook
) -> None:
    existing_submission = gradebook.find_submission_by_assignment_and_student(
        linked_assignment.id, linked_student.id
    )
    if existing_submission is None:
        return None

    print(
        f"\nA submission from {linked_student.full_name} in {linked_assignment.name} already exists:"
    )
    print(
        f"...Score: {existing_submission.points_earned} / {linked_assignment.points_possible}"
    )
    print(f"...Late: {'Yes' if existing_submission.is_late else 'No'}")
    print(f"...Exempt: {'Yes' if existing_submission.is_exempt else 'No'}")

    title = "What would you like to do?"
    options = [
        ("Edit the existing submission", edit_submission),
        ("Delete and create a new submission", delete_and_create_new_submission),
    ]
    zero_option = "Cancel and return"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response == MenuSignal.EXIT:
        helpers.returning_without_changes()
        return None

    if callable(menu_response):
        menu_response(existing_submission, gradebook)


def delete_and_create_new_submission(
    existing_submission: Submission, gradebook: Gradebook
) -> None:
    confirm_and_remove(existing_submission, gradebook)

    linked_assignment = gradebook.find_assignment_by_uuid(
        existing_submission.assignment_id
    )
    linked_student = gradebook.find_student_by_uuid(existing_submission.student_id)

    if linked_assignment is None or linked_student is None:
        return None

    new_submission = prompt_new_submission(linked_assignment, linked_student, gradebook)

    if new_submission is not None and preview_and_confirm_submission(
        new_submission, gradebook
    ):
        gradebook.add_submission(new_submission)
        assignment_name = linked_assignment.name
        student_name = linked_student.full_name
        print(
            f"\nSubmission for {student_name} to {assignment_name} successfully added to {gradebook.name}"
        )


# === data input helpers ===


def prompt_points_earned_input() -> str | MenuSignal:
    return helpers.prompt_user_input_or_cancel(
        "Enter points earned (leave blank to cancel):"
    )


# === edit submission ===

# TODO:
# def get_editable_fields() -> (
#     list[tuple[str, Callable[[Submission, Gradebook], Optional[MenuSignal]]]]
# ):
#     pass


def find_and_edit_submission(gradebook: Gradebook) -> None:
    linked_assignment = prompt_linked_assignment(gradebook)
    if linked_assignment == MenuSignal.CANCEL:
        return None
    else:
        linked_assignment = cast(Assignment, linked_assignment)

    linked_student = prompt_linked_student(gradebook)
    if linked_student == MenuSignal.CANCEL:
        return None
    else:
        linked_student = cast(Student, linked_student)

    submission = gradebook.find_submission_by_assignment_and_student(
        linked_assignment.id, linked_student.id
    )

    if submission is None:
        return None

    edit_submission(submission, gradebook)


# TODO:
def edit_submission(submission: Submission, gradebook: Gradebook) -> None:
    pass


# === remove submission ===


# TODO:
def remove_submission(gradebook: Gradebook) -> None:
    pass


# TODO:
def confirm_and_remove(submission: Submission, gradebook: Gradebook) -> None:
    pass


# === view submission ===


# TODO:
def view_submissions_menu(gradebook: Gradebook) -> None:
    pass
