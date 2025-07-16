# cli/submissions_menu.py

import cli.formatters as formatters
import cli.menu_helpers as helpers
from cli.menu_helpers import MenuSignal
from models.assignment import Assignment
from models.gradebook import Gradebook
from models.student import Student
from models.submission import Submission
from typing import cast, Callable, Optional
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

    print("\nA submission from this student already exists in this assignment.")
    print(formatters.format_submission_multiline(existing_submission, gradebook))

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


# === edit submission ===


def get_editable_fields() -> (
    list[tuple[str, Callable[[Submission, Gradebook], Optional[MenuSignal]]]]
):
    return [
        ("Score", edit_score_and_confirm),
        ("Late Status", edit_late_and_confirm),
        ("Exempt Status", edit_exempt_and_confirm),
    ]


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


def edit_submission(submission: Submission, gradebook: Gradebook) -> None:
    title = formatters.format_banner_text("Editable Fields")
    options = get_editable_fields()
    zero_option = "Return without changes"

    while True:
        print("\nYou are viewing the following submission:")
        print(formatters.format_submission_multiline(submission, gradebook))

        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response == MenuSignal.EXIT:
            helpers.returning_without_changes()
            return None

        if callable(menu_response):
            menu_response(submission, gradebook)

        if not helpers.confirm_action(
            "Would you like to continue editing this submissions?"
        ):
            print("\nReturning to Manage Submissions menu")
            return None


def edit_score_and_confirm(submission: Submission, gradebook: Gradebook) -> None:
    linked_assignment = gradebook.find_assignment_by_uuid(submission.assignment_id)

    if linked_assignment is None:
        return None

    current_points_earned = submission.points_earned
    new_points_earned_str = prompt_points_earned_input()
    points_possible = linked_assignment.points_possible

    if new_points_earned_str == MenuSignal.CANCEL:
        helpers.returning_without_changes()
        return None
    else:
        new_points_earned = cast(str, new_points_earned_str)

    print(
        f"Current score: {current_points_earned} / {points_possible} ... New score: {new_points_earned} / {points_possible}"
    )

    if not helpers.confirm_save_change():
        helpers.returning_without_changes()
        return None

    try:
        new_points_earned = float(new_points_earned)
        submission.points_earned = new_points_earned
        gradebook.save(gradebook.path)
        print("\nScore successfully updated.")
    except (TypeError, ValueError) as e:
        print(f"\nError: Could not update submission ... {e}:")


# TODO: add updated status inside success message
def edit_late_and_confirm(submission: Submission, gradebook: Gradebook) -> None:
    late_status = "marked late" if submission.is_late else "not marked late"
    print(f"\nThis submission is currently {late_status}.")

    if not helpers.confirm_action("Would you like to edit the late status?"):
        helpers.returning_without_changes()
        return None
    else:
        submission.toggle_late_status()
        gradebook.save(gradebook.path)
        print("\nSubmission late status successfully updated.")


# TODO: discard pre/post check, add updated status inside success message
def edit_exempt_and_confirm(submission: Submission, gradebook: Gradebook) -> None:
    exempt_status = "marked exempt" if submission.is_exempt else "not marked exempt"
    print(f"\nThis submission is currently {exempt_status}.")

    if not helpers.confirm_action("Would you like to edit the exempt status?"):
        helpers.returning_without_changes()
        return None
    else:
        status_pre = submission.is_exempt

        submission.toggle_exempt_status()
        gradebook.save(gradebook.path)

        status_post = submission.is_exempt

        assert status_pre is not status_post
        print("\nSubmission exempt status successfully updated.")


# === remove submission ===


# TODO:
def remove_submission(gradebook: Gradebook) -> None:
    pass


# TODO:
def confirm_and_remove(submission: Submission, gradebook: Gradebook) -> None:
    pass


# === view submission ===


def view_submissions_menu(gradebook: Gradebook) -> None:
    pass
    title = "View Submissions"
    options = [
        ("View Individual Submission", view_individual_submission),
        ("View All Submissions by Assignment", view_submissions_by_assignment),
        ("View All Submissions by Student", view_submissions_by_student),
    ]
    zero_option = "Return to Manage Submissions menu"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response == MenuSignal.EXIT:
        return None

    if callable(menu_response):
        menu_response(gradebook)


# TODO:
def view_individual_submission(gradebook: Gradebook) -> None:
    pass


# TODO:
def view_submissions_by_assignment(gradebook: Gradebook) -> None:
    pass


# TODO:
def view_submissions_by_student(gradebook: Gradebook) -> None:
    pass
