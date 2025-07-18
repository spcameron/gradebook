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
        ("Edit Submission", find_and_edit_submission),
        ("Remove Submission", find_and_remove_submission),
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
        linked_assignment = prompt_find_assignment(gradebook)
        if linked_assignment == MenuSignal.CANCEL:
            return None
        else:
            linked_assignment = cast(Assignment, linked_assignment)

        linked_student = prompt_find_student(gradebook)
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
            print(
                f"\nSubmission for {linked_student.full_name} to {linked_assignment.name} successfully added to {gradebook.name}"
            )

        if not helpers.confirm_action(
            "Would you like to continue adding new submissions?"
        ):
            print("\nReturning to Manage Submissions menu")
            return None


def add_submissions_by_assignment(gradebook: Gradebook) -> None:
    # assignment selection
    assignment = prompt_find_assignment(gradebook)
    if assignment == MenuSignal.CANCEL:
        return None
    else:
        assignment = cast(Assignment, assignment)

    # build student list, empty queues for submissions and skips
    students_to_prompt = gradebook.get_records(
        gradebook.students,
        lambda student: not gradebook.submission_already_exists(
            assignment.id, student.id
        ),
    )

    queued_submissions = []
    skipped_students = []

    # fast entry loop
    for student in students_to_prompt:
        points_earned = prompt_score_with_bailout(assignment, student)

        if points_earned is None:
            skipped_students.append(student)
            continue

        if points_earned == MenuSignal.CANCEL:
            if helpers.confirm_action(
                f"This will also discard the other submissions in this batch. Are you sure you want to cancel?"
            ):
                return None
            else:
                skipped_students.append(student)
                continue

        points_earned = cast(float, points_earned)

        try:
            submission_id = generate_uuid()
            new_submission = Submission(
                id=submission_id,
                student_id=student.id,
                assignment_id=assignment.id,
                points_earned=points_earned,
            )
        except (TypeError, ValueError) as e:
            print(f"\nError: Could not create submission ... {e}")
            skipped_students.append(student)
            continue

        queued_submissions.append(new_submission)

    # summary preview and chance to edit or add
    preview_batch_submissions(assignment, queued_submissions, gradebook)

    if helpers.confirm_action("Would you like to edit any of these submissions?"):
        edit_batch_submissions(
            assignment, queued_submissions, skipped_students, gradebook
        )

    if helpers.confirm_action("Would you like to review the skipped students?"):
        review_skipped_students(
            assignment, queued_submissions, skipped_students, gradebook
        )

    # final confirmation
    preview_batch_submissions(assignment, queued_submissions, gradebook)

    if helpers.confirm_action("Do you want to add these submissions to the Gradebook?"):
        for submission in queued_submissions:
            gradebook.add_submission(submission)
        print(
            f"\n{len(queued_submissions)} submissions successfully added to the Gradebook."
        )
    else:
        print(f"\nDiscarding {len(queued_submissions)} submissions. No changes saved.")


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
    points_earned_str = prompt_score_input()
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
            points_earned=points_earned,
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


def preview_batch_submissions(
    assignment: Assignment, submissions: list[Submission], gradebook: Gradebook
) -> None:
    print(f"\nYou are about to add the following submissions to {assignment.name}:")

    for submission in submissions:
        student = gradebook.find_student_by_uuid(submission.student_id)
        student_name = student.full_name if student else ""

        print(
            f"...{student_name:<20} | {submission.points_earned} / {assignment.points_possible}"
        )


def edit_batch_submissions(
    assignment: Assignment,
    skipped_students: list[Student],
    queued_submissions: list[Submission],
    gradebook: Gradebook,
) -> None:
    def sort_key_student_name(submission: Submission) -> Optional[tuple[str, str]]:
        student = gradebook.find_student_by_uuid(submission.student_id)
        return (student.last_name, student.first_name) if student else None

    def format_submission_batch_preview(submission: Submission) -> str:
        student = gradebook.find_student_by_uuid(submission.student_id)
        late_status = "[LATE] " if submission.is_late else ""
        score_or_exempt = (
            "[EXEMPT]"
            if submission.is_exempt
            else f"{submission.points_earned} / {assignment.points_possible}"
        )

        return (
            f"{late_status}{student.full_name:<20} | {score_or_exempt}"
            if student
            else f"{late_status}[MISSING STUDENT] | {score_or_exempt}"
        )

    def make_edit_fn(
        assignment: Assignment, submission: Submission, gradebook: Gradebook
    ) -> Callable[[], None]:
        return lambda: edit_queued_submission(assignment, submission, gradebook)

    def make_delete_fn(
        queued_submissions: list[Submission],
        skipped_students: list[Student],
        submission: Submission,
        gradebook: Gradebook,
    ) -> Callable[[], None]:
        return lambda: delete_queued_submission(
            queued_submissions, skipped_students, submission, gradebook
        )

    while True:
        if not queued_submissions:
            print("\nThere are no queued submissions to edit.")
            return None

        # prompt submission selection
        submission = helpers.prompt_selection_from_list(
            list_data=queued_submissions,
            list_description="Queued Submissions",
            sort_key=sort_key_student_name,
            formatter=format_submission_batch_preview,
        )

        if submission is None:
            return None

        # action fork - edit or delete
        print(f"\nYou are viewing the following submission:")
        print(formatters.format_submission_multiline(submission, gradebook))

        title = "What would you like to do with this submission?"
        options = [
            (
                "Edit Submission Fields",
                make_edit_fn(assignment, submission, gradebook),
            ),
            (
                "Delete Submission",
                make_delete_fn(
                    queued_submissions, skipped_students, submission, gradebook
                ),
            ),
        ]
        zero_option = "Return to Queued Submissions list"

        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response == MenuSignal.EXIT:
            continue

        if callable(menu_response):
            menu_response()


# TODO:
def review_skipped_students(
    assignment: Assignment,
    skipped_students: list[Student],
    queued_submissions: list[Submission],
    gradebook: Gradebook,
) -> None:
    pass


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


def prompt_score_input() -> str | MenuSignal:
    return helpers.prompt_user_input_or_cancel(
        "Enter points earned (leave blank to cancel):"
    )


def prompt_score_with_bailout(
    assignment: Assignment, student: Student
) -> Optional[float] | MenuSignal:
    while True:
        print(f"\nRecord a submission from {student.full_name} in {assignment.name}")
        input = helpers.prompt_user_input_or_none(
            "Enter points earned (leave blank to skip, 'q' to cancel):"
        )

        if input is None:
            return None

        if input in {"q", ":exit"}:
            return MenuSignal.CANCEL

        try:
            return float(input)
        except ValueError:
            print(
                f"\nInvalid input. Please enter a number, leave blank to skip, or 'q' to cancel."
            )


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
    submission = find_submission(gradebook)
    if submission is not None:
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
            "Would you like to continue editing this submission?"
        ):
            print("\nReturning to Manage Submissions menu")
            return None


def edit_score_and_confirm(submission: Submission, gradebook: Gradebook) -> None:
    linked_assignment = gradebook.find_assignment_by_uuid(submission.assignment_id)

    if linked_assignment is None:
        return None

    current_points_earned = submission.points_earned
    new_points_earned_str = prompt_score_input()
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


def edit_late_and_confirm(submission: Submission, gradebook: Gradebook) -> None:
    print(
        f"\nSubmission current late status: {'Late' if submission.is_late else 'Not Late'}"
    )

    if not helpers.confirm_action("Would you like to edit the late status?"):
        helpers.returning_without_changes()
        return None

    submission.toggle_late_status()
    gradebook.save(gradebook.path)
    print(
        f"\nSubmission late status successfully updated to: {'Late' if submission.is_late else 'Not Late'}"
    )


def edit_exempt_and_confirm(submission: Submission, gradebook: Gradebook) -> None:
    print(
        f"\nSubmission current exempt status: {'Exempt' if submission.is_exempt else 'Not Exempt'}"
    )

    if not helpers.confirm_action("Would you like to edit the exempt status?"):
        helpers.returning_without_changes()
        return None

    submission.toggle_exempt_status()
    gradebook.save(gradebook.path)
    print(
        f"\nSubmission exempt status successfully updated to: {'Exempt' if submission.is_exempt else 'Not Exempt'}"
    )


# === edit queued submission ===


def get_editable_fields_queued() -> (
    list[
        tuple[str, Callable[[Assignment, Submission, Gradebook], Optional[MenuSignal]]]
    ]
):
    return [
        ("Score", edit_score_queued),
        ("Late Status", edit_late_queued),
        ("Exempt Status", edit_exempt_queued),
    ]


def edit_queued_submission(
    assignment: Assignment, submission: Submission, gradebook: Gradebook
) -> None:
    title = "Editable Fields"
    options = get_editable_fields_queued()
    zero_option = "Return without changes"

    while True:
        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response == MenuSignal.EXIT:
            helpers.returning_without_changes()
            return None

        if callable(menu_response):
            menu_response(assignment, submission, gradebook)

        if not helpers.confirm_action(
            "Would you like to continue editing this submission?"
        ):
            print("\nReturning to Queued Submissions list")
            return None


# TODO:
def edit_score_queued(
    assignment: Assignment, submission: Submission, gradebook: Gradebook
) -> None:
    pass


# TODO:
def edit_late_queued(
    assignment: Assignment, submission: Submission, gradebook: Gradebook
) -> None:
    pass


# TODO:
def edit_exempt_queued(
    assignment: Assignment, submission: Submission, gradebook: Gradebook
) -> None:
    pass


# === remove submission ===


def find_and_remove_submission(gradebook: Gradebook) -> None:
    submission = find_submission(gradebook)
    if submission is not None:
        remove_submission(submission, gradebook)


def remove_submission(submission: Submission, gradebook: Gradebook) -> None:
    print(f"\nYou are viewing the following submission:")
    print(formatters.format_submission_oneline(submission, gradebook))

    title = "What would you like to do?"
    options = [
        (
            "Permanently remove this submission (deletes the record)",
            confirm_and_remove,
        ),
        (
            "Edit this submission instead (update score, late status, or exempt status)",
            edit_submission,
        ),
    ]
    zero_option = "Return to Manage Submissions menu"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response == MenuSignal.EXIT:
        helpers.returning_without_changes()
        return None

    if callable(menu_response):
        menu_response(submission, gradebook)


def confirm_and_remove(submission: Submission, gradebook: Gradebook) -> None:
    caution_banner = formatters.format_banner_text("CAUTION!")
    print(f"\n{caution_banner}")
    print("You are about to permanently delete the following submission:")
    print(f"{formatters.format_submission_multiline(submission, gradebook)}")

    confirm_deletion = helpers.confirm_action(
        "Are you sure you want to permanently delete this submission? This action cannot be undone."
    )

    if not confirm_deletion:
        helpers.returning_without_changes()
        return None

    gradebook.remove_submission(submission)
    gradebook.save(gradebook.path)
    print("\nSubmission successfully removed from Gradebook.")


def delete_queued_submission(
    queued_submissions: list[Submission],
    skipped_students: list[Student],
    submission: Submission,
    gradebook: Gradebook,
) -> None:
    student = gradebook.find_student_by_uuid(submission.student_id)
    if student is None:
        return

    caution_banner = formatters.format_banner_text("CAUTION!")
    print(f"\n{caution_banner}")
    print("You are about to permanently delete the following submission:")
    print(f"{formatters.format_submission_multiline(submission, gradebook)}")

    confirm_deletion = helpers.confirm_action(
        "Are you sure you want to permanently delete this submission? This action cannot be undone."
    )

    if not confirm_deletion:
        helpers.returning_without_changes()
        return None

    queued_submissions.remove(submission)
    skipped_students.append(student)
    print("Submission successfully deleted and student added to skipped students list.")


# === view submission ===


def view_submissions_menu(gradebook: Gradebook) -> None:
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


def view_individual_submission(gradebook: Gradebook) -> None:
    submission = find_submission(gradebook)

    if not submission:
        return None

    print("\nYou are viewing the following submission:")
    print(formatters.format_submission_oneline(submission, gradebook))

    if helpers.confirm_action("Would you like to see an expanded view of this record?"):
        print(formatters.format_submission_multiline(submission, gradebook))


def view_submissions_by_assignment(gradebook: Gradebook) -> None:
    def sort_key_student_name(submission: Submission) -> Optional[tuple[str, str]]:
        student = gradebook.find_student_by_uuid(submission.student_id)
        return (student.last_name, student.first_name) if student else None

    assignment = prompt_find_assignment(gradebook)
    if assignment == MenuSignal.CANCEL:
        return None
    else:
        assignment = cast(Assignment, assignment)

    submissions = gradebook.get_records(
        gradebook.submissions, lambda x: x.assignment_id == assignment.id
    )

    banner = formatters.format_banner_text(f"Submissions to {assignment.name}")
    print(f"\n{banner}")

    if not submissions:
        print(f"There are no submissions linked to this assignment yet.")
        return None

    helpers.sort_and_display_submissions(
        submissions=submissions,
        gradebook=gradebook,
        sort_key=sort_key_student_name,
        formatter=formatters.format_submission_oneline,
    )


def view_submissions_by_student(gradebook: Gradebook) -> None:
    def sort_key_assignment_due_date(submission: Submission) -> str:
        assignment = gradebook.find_assignment_by_uuid(submission.assignment_id)
        due_date_iso = assignment.due_date_iso if assignment else ""
        return due_date_iso if due_date_iso else ""

    student = prompt_find_student(gradebook)
    if student == MenuSignal.CANCEL:
        return None
    else:
        student = cast(Student, student)

    submissions = gradebook.get_records(
        gradebook.submissions, lambda x: x.student_id == student.id
    )

    banner = formatters.format_banner_text(f"Submissions from {student.full_name}")
    print(f"\n{banner}")

    if not submissions:
        print(f"There are no submissions linked to this student yet.")
        return None

    helpers.sort_and_display_submissions(
        submissions=submissions,
        gradebook=gradebook,
        sort_key=sort_key_assignment_due_date,
        formatter=formatters.format_submission_oneline,
    )


# === finder methods ===


def find_submission(gradebook: Gradebook) -> Optional[Submission]:
    linked_assignment = prompt_find_assignment(gradebook)
    if linked_assignment == MenuSignal.CANCEL:
        return None
    else:
        linked_assignment = cast(Assignment, linked_assignment)

    linked_student = prompt_find_student(gradebook)
    if linked_student == MenuSignal.CANCEL:
        return None
    else:
        linked_student = cast(Student, linked_student)

    submission = gradebook.find_submission_by_assignment_and_student(
        linked_assignment.id, linked_student.id
    )

    return submission


def prompt_find_assignment(gradebook: Gradebook) -> Assignment | MenuSignal:
    title = formatters.format_banner_text("Assignment Selection")
    options = [
        ("Search for an assignment", find_assignment_by_search),
        ("Select from active assignments", find_assignment_from_list),
    ]
    zero_option = "Return and cancel"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response == MenuSignal.EXIT:
        return MenuSignal.CANCEL

    if callable(menu_response):
        return menu_response(gradebook)

    raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")


def find_assignment_by_search(
    gradebook: Gradebook,
) -> Assignment | MenuSignal:
    search_results = helpers.search_assignments(gradebook)
    assignment = helpers.prompt_assignment_selection_from_search(search_results)
    return MenuSignal.CANCEL if assignment is None else assignment


def find_assignment_from_list(
    gradebook: Gradebook,
) -> Assignment | MenuSignal:
    active_assignments = gradebook.get_records(
        gradebook.assignments, lambda x: x.is_active
    )
    assignment = helpers.prompt_assignment_selection_from_list(
        active_assignments, "Active Assignments"
    )
    return MenuSignal.CANCEL if assignment is None else assignment


def prompt_find_student(gradebook: Gradebook) -> Student | MenuSignal:
    title = formatters.format_banner_text("Student Selection")
    options = [
        ("Search for a student", find_student_by_search),
        ("Select from active students", find_student_from_list),
    ]
    zero_option = "Return and cancel"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response == MenuSignal.EXIT:
        return MenuSignal.CANCEL

    if callable(menu_response):
        return menu_response(gradebook)

    raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")


def find_student_by_search(gradebook: Gradebook) -> Student | MenuSignal:
    search_results = helpers.search_students(gradebook)
    student = helpers.prompt_student_selection_from_search(search_results)
    return MenuSignal.CANCEL if student is None else student


def find_student_from_list(gradebook: Gradebook) -> Student | MenuSignal:
    active_students = gradebook.get_records(gradebook.students, lambda x: x.is_active)
    student = helpers.prompt_student_selection_from_list(
        active_students, "Active Students"
    )
    return MenuSignal.CANCEL if student is None else student
