# cli/submissions_menu.py

"""
Manage Submissions menu for the Gradebook CLI.

This module defines the full interace for managing `Submission` records, including:
- Adding new submissions, individually or in batches by assignment
- Editing submission attributes (TODO)
- Permanently removing submissions
- View submission records (TODO)

All operations are routed through the `Gradebook` API for consistency, validation, and state-tracking.
Control flow adheres to traditional CLI menu patterns with clear terminal-level feedback.
"""

from typing import Callable, cast

import cli.formatters as formatters
import cli.menu_helpers as helpers
from cli.menu_helpers import MenuSignal
from core.response import ErrorCode
from core.utils import generate_uuid
from models.assignment import Assignment
from models.gradebook import Gradebook
from models.student import Student
from models.submission import Submission


def run(gradebook: Gradebook) -> None:
    """
    Top-level loop with dispatch for the Manage Submissions menu.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        - The finally block guarantees a check for unsaved changes before returning.
    """
    title = formatters.format_banner_text("Manage Submissions")
    options = [
        ("Add Single Submission", add_single_submission),
        ("Batch Add Submissions by Assignment", batch_add_submissions_by_assignment),
        ("Edit Submission", find_and_edit_submission),
        ("Remove Submission", find_and_remove_submission),
        ("View Submissions", view_submissions_menu),
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


# === add submission ===


def add_single_submission(gradebook: Gradebook) -> None:
    """
    Loops a prompt to search/select an `Assignment`, `Student`, and create new `Submission`.

    Args:
        gradebook (Gradebook): The active `gradebook`.

    Notes:
        - Additions are not saved automatically. If the gradebook is marked dirty after adding, the user will be prompted to save before returning to the previous menu.
    """
    while True:
        assignment = prompt_find_assignment(gradebook)

        if assignment is MenuSignal.CANCEL:
            break
        assignment = cast(Assignment, assignment)

        student = prompt_find_student(gradebook)

        if student is MenuSignal.CANCEL:
            break
        student = cast(Student, student)

        new_submission = prompt_new_submission(assignment, student, gradebook)

        if new_submission is not None and preview_and_confirm_submission(
            new_submission, gradebook
        ):
            gradebook_response = gradebook.add_submission(new_submission)

            if not gradebook_response.success:
                helpers.display_response_failure(gradebook_response)
                print(
                    f"\nSubmission from {student.full_name} to {assignment.name} was not added."
                )

            else:
                print(f"\n{gradebook_response.detail}")

        if not helpers.confirm_action(
            "Would you like to continue adding new submissions?"
        ):
            break

    helpers.prompt_if_dirty(gradebook)

    helpers.returning_to("Manage Submissions menu")


def prompt_new_submission(
    linked_assignment: Assignment, linked_student: Student, gradebook: Gradebook
) -> Submission | None:
    """
    Creates a new `Submission` record for the `Assignment` and `Student` passed as arguments.

    Args:
        linked_assignment (Assignment): The `Assignment` object to associate with this submission.
        linked_student (Student): The `Student` object to associate with this submission.
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        A new `Submission` object, or None.

    Notes:
        - Checks first for an existing submission with the given assignment/student pair and diverts to `handle_existing_submission()` if one is found.
    """
    if gradebook.submission_already_exists(linked_assignment.id, linked_student.id):
        return resolve_existing_submission_conflict(
            linked_assignment, linked_student, gradebook
        )

    print(
        f"\nYou are logging a submission from {linked_student.full_name} to {linked_assignment.name}."
    )

    points_earned = prompt_points_earned_input_or_cancel()

    if points_earned is MenuSignal.CANCEL:
        return None
    points_earned = cast(float, points_earned)

    try:
        return Submission(
            id=generate_uuid(),
            student_id=linked_student.id,
            assignment_id=linked_assignment.id,
            points_earned=points_earned,
        )

    except (TypeError, ValueError) as e:
        print(f"\n[ERROR] Could not create submission: {e}")
        return None


def preview_and_confirm_submission(
    submission: Submission, gradebook: Gradebook
) -> bool:
    """
    Previews new `Submission` details, offers opportunity to edit details, and prompts user for confirmation.

    Args:
        submission (Submission): The `Submission` object under review.
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        True if user confirms the `Submission` details, and False otherwise.
    """
    print("\nYou are about to create the following submission:")
    print(formatters.format_submission_multiline(submission, gradebook))

    if helpers.confirm_action(
        "Would you like to edit this submission first (change the score, mark late, or mark exempt)?"
    ):
        edit_submission(submission, gradebook, "Submission creation preview")

    if helpers.confirm_action("Would you like to create this submission?"):
        return True

    else:
        print("Discarding submission.")
        return False


def batch_add_submissions_by_assignment(gradebook: Gradebook) -> None:
    """
    Guides the user through batch entry of `Submission` records for a selected assignment.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - The user can cancel at assignment selection, during score entry, or at final confirmation.
        - Only active students without existing submissions for the chosen assignment are included.
        - Points can be entered for each student or skipped; skipped students are queued separately.
        - After entry, the user may edit submissions, review skipped students, and confirm final additions.
        - Submissions are committed via `Gradebook.batch_add_submissions()` with validation and state tracking.
        - The gradebook is not automatically saved; if modified, the user will be prompted to save before exiting.
    """
    assignment = prompt_find_assignment(gradebook)

    if assignment is MenuSignal.CANCEL:
        return
    assignment = cast(Assignment, assignment)

    students_response = gradebook.get_records(
        gradebook.students,
        lambda student: student.is_active
        and not gradebook.submission_already_exists(assignment.id, student.id),
    )

    if not students_response.success:
        helpers.display_response_failure(students_response)
        print("Unable to populate the active student roster.")
        helpers.returning_without_changes()
        return

    students_to_prompt = students_response.data["records"]

    if not students_to_prompt:
        print(
            "\nThere are no active students who have yet to submit for this assignment."
        )
        helpers.returning_without_changes()
        return

    queued_submissions = []
    skipped_students = []

    for student in students_to_prompt:
        points_earned = prompt_score_with_bailout(assignment, student)

        if points_earned is None:
            print(f"\nAdding {student.full_name} to skipped students.")
            skipped_students.append(student)
            continue

        elif points_earned is MenuSignal.CANCEL:
            if helpers.confirm_action(
                "This will also discard the other submissions in this batch. Are you sure you want to cancel?"
            ):
                print(
                    f"\nDiscarding {len(queued_submissions)} submissions. No changes saved."
                )
                return

            else:
                print(f"\nAdding {student.full_name} to skipped students instead.")
                skipped_students.append(student)
                continue

        else:
            points_earned = cast(float, points_earned)

        try:
            queued_submissions.append(
                Submission(
                    id=generate_uuid(),
                    student_id=student.id,
                    assignment_id=assignment.id,
                    points_earned=points_earned,
                )
            )

        except (TypeError, ValueError) as e:
            print(f"\nError: Could not create submission ... {e}")
            skipped_students.append(student)
            print(f"\nAdding {student.full_name} to skipped students instead.")
            continue

    if review_and_confirm_batch_add(
        assignment, queued_submissions, skipped_students, gradebook
    ):
        gradebook_response = gradebook.batch_add_submissions(queued_submissions)

        added_submissions = gradebook_response.data["added"]
        skipped_submissions = gradebook_response.data["skipped"]

        if not gradebook_response.success:
            helpers.display_response_failure(gradebook_response)

            if gradebook_response.error is ErrorCode.VALIDATION_FAILED:
                print(
                    f"{len(added_submissions)} of {len(queued_submissions)} submissions were added."
                )
                print(
                    f"{len(skipped_submissions)} submissions were skipped due to validation errors."
                )

            else:
                print(
                    f"Batch entry failed after adding {len(added_submissions)} of {len(queued_submissions)} submissions."
                )

        else:
            print(f"\n{gradebook_response.detail}")

    else:
        print(f"\nDiscarding {len(queued_submissions)} submissions. No changes made.")

    helpers.prompt_if_dirty(gradebook)

    helpers.returning_to("Manage Submissions menu")


def review_and_confirm_batch_add(
    assignment: Assignment,
    queued_submissions: list[Submission],
    skipped_students: list[Student],
    gradebook: Gradebook,
) -> bool:
    """
    Handles user review, optional editing, and final confirmation for a batch of queued `Submission` records.

    Args:
        assignment (Assignment): The target assignment for the batch.
        queued_submissions (list[Submission]): The submissions prepared during batch entry.
        skipped_students (list[Student]): Students who were skipped during score entry.
        gradebook (Gradebook): The active `Gradebook`, used for previewing and editing.

    Returns:
        bool: True if the user confirms final submission; False if the operation is canceled or abandoned.

    Notes:
        - Allows optional editing of queued submissions.
        - Offers a chance to review and update skipped students.
        - If no submissions remain after review, the process is aborted.
        - This method does not mutate the gradebook; it only prepares data for potential submission.
    """
    if queued_submissions:
        preview_queued_submissions(assignment, queued_submissions, gradebook)

        if helpers.confirm_action("Would you like to edit any of these submissions?"):
            edit_queued_submissions(
                assignment, queued_submissions, skipped_students, gradebook
            )

    if skipped_students and helpers.confirm_action(
        "Would you like to review the skipped students?"
    ):
        review_skipped_students(
            assignment, queued_submissions, skipped_students, gradebook
        )

    if not queued_submissions:
        print("You have not entered any submissions to add to the gradebook.")
        return False

    banner = formatters.format_banner_text("Batch Entry: Final Preview")
    print(f"\n{banner}\n")
    preview_queued_submissions(assignment, queued_submissions, gradebook)

    return helpers.confirm_action(
        "Do you want to add these submissions to the gradebook?"
    )


def preview_queued_submissions(
    assignment: Assignment, submissions: list[Submission], gradebook: Gradebook
) -> None:
    """
    Previews the queued submissions from batch entry using a modified one-line formatting.

    Args:
        assignment (Assignment): The linked assignment.
        submissions (list[Submission]): The list of queued submissions populated during batch entry.
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Includes a safeguard check for an empty submissions list for coverage, but callers will typically check for populated list first.
        - If find_student_by_uuid() fails to return a `Student` record, the formatter displays '[MISSING STUDENT]' in the preview.
    """
    if not submissions:
        print("\nThere are no queued submissions.")
        return None

    print(f"\nYou are about to add the following submissions to {assignment.name}:")

    for submission in submissions:
        student_response = gradebook.find_student_by_uuid(submission.student_id)

        student = student_response.data["record"] if student_response.success else None

        student_name = student.full_name if student else "[MISSING STUDENT]"

        print(
            f"... {student_name:<20} | {submission.points_earned} / {assignment.points_possible}"
        )


def edit_queued_submissions(
    assignment: Assignment,
    queued_submissions: list[Submission],
    skipped_students: list[Student],
    gradebook: Gradebook,
) -> None:
    """
    Prompts user to select a queued `Submission` record and either edit or delete it.

    Args:
        assignment (Assignment): The assignment targeted by the batch entry.
        queued_submission (list[Submission]): The list of submissions created and queued during batch entry.
        skipped_students (list[Student]): The list of students who were skipped during batch entry.
        gradebook (Gradebook): The active `Gradebook`.
    """

    def sort_key_student_name(submission: Submission) -> tuple[str, str] | None:
        """
        Sort key method for organizing submissions by student name (last, first).

        Args:
            submission (Submission): The `Submission` record being sorted.

        Returns:
            A tuple (last name, first name), or None if the student could not be found.
        """
        student_response = gradebook.find_student_by_uuid(submission.student_id)

        student = student_response.data["record"] if student_response.success else None

        return (student.last_name, student.first_name) if student else None

    def format_submission_batch_preview(submission: Submission) -> str:
        """
        Formatter method for previewing a queued submission.

        Args:
            submission (Submission): The `Submission` record being previewed.

        Returns:
            A string representing the submission preview.

        Notes:
            - Displays '[LATE]' and '[EXEMPT]' in reponse to flags, and '[MISSING STUDENT]' if the linked student cannot be located.
        """
        student_response = gradebook.find_student_by_uuid(submission.student_id)

        student = student_response.data["record"] if student_response.success else None

        student_name = student.full_name if student else "[MISSING STUDENT]"

        late_status = "[LATE] " if submission.is_late else ""

        score_or_exempt = (
            "[EXEMPT]"
            if submission.is_exempt
            else f"{submission.points_earned} / {assignment.points_possible}"
        )

        return f"{late_status}{student_name:<20} | {score_or_exempt}"

    def make_edit_fn(
        submission: Submission, gradebook: Gradebook
    ) -> Callable[[], None]:
        """
        Helper method necessary for narrowing a submission variable.

        Args:
            submission (Submission): The `Submission` record being narrowed from None to `Submission` type.
            gradebook (Gradebook): The active `Gradebook`.

        Returns:
            Lambda expression that calls `edit_submission()`.
        """
        return lambda: edit_submission(
            submission, gradebook, "Queued Submissions review"
        )

    def make_delete_fn(
        queued_submissions: list[Submission],
        skipped_students: list[Student],
        submission: Submission,
        gradebook: Gradebook,
    ) -> Callable[[], None]:
        """
        Helper method necessary for narrowing a submission variable.

        Args:
            submission (Submission): The `Submission` record being narrowed from None to `Submission` type.
            gradebook (Gradebook): The Active `Gradebook`.

        Returns:
            Lambda expression that calls `delete_queued_submission()`.
        """
        return lambda: delete_queued_submission(
            queued_submissions, skipped_students, submission, gradebook
        )

    while True:
        if not queued_submissions:
            print("\nThere are no queued submissions available to edit.")
            break

        submission = helpers.prompt_selection_from_list(
            list_data=queued_submissions,
            list_description="Queued Submissions",
            sort_key=sort_key_student_name,
            formatter=format_submission_batch_preview,
        )

        if submission is None:
            break

        print(f"\nYou are viewing the following submission:")
        print(formatters.format_submission_multiline(submission, gradebook))

        title = "What would you like to do with this submission?"
        options = [
            (
                "Edit Submission Fields",
                make_edit_fn(submission, gradebook),
            ),
            (
                "Delete Submission",
                make_delete_fn(
                    queued_submissions, skipped_students, submission, gradebook
                ),
            ),
        ]
        zero_option = "Choose a different queued submission"

        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response is MenuSignal.EXIT:
            continue

        elif callable(menu_response):
            menu_response()

        else:
            raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

        if not helpers.confirm_action(
            "Would you like to continue editing the queued submissions?"
        ):
            break

    helpers.returning_to("Submission batch entry review")


def review_skipped_students(
    assignment: Assignment,
    queued_submissions: list[Submission],
    skipped_students: list[Student],
    gradebook: Gradebook,
) -> None:
    """
    Prompts user to select a skipped student and either log a submission or mark them exempt from this assignment, or leave them skipped.

    Args:
        assignment (Assignment): The assignment targeted by the batch entry.
        queued_submissions (list[Submission]): The list of submissions created and queued during batch entry.
        skipped_students (list[Student]): The list of students who were skipped during batch entry.
        gradebook (Gradebook): The active `Gradebook`.
    """

    def prompt_score_skipped_student(student: Student) -> None:
        """
        Wrapper method to solicit a new score, then update the queued submissions and skipped students lists.

        Args:
            student (Student): The `Student` record selected from the skipped students list.
        """
        new_submission = prompt_new_submission(assignment, student, gradebook)

        if new_submission is not None and preview_and_confirm_submission(
            new_submission, gradebook
        ):
            queued_submissions.append(new_submission)
            skipped_students.remove(student)

            print(
                f"\nSubmission from {student.full_name} to {assignment.name} successfully added to the queued submissions."
            )

    def create_exempt_submission(student: Student) -> None:
        """
        Wrapper method to mark a student 'Exempt' from an assignment, then update the queued submissions and skipped students lists.

        Args:
            student (Student): The student selected from the skipped students list.
        """
        new_submission = Submission(
            id=generate_uuid(),
            student_id=student.id,
            assignment_id=assignment.id,
            points_earned=0,
            is_exempt=True,
        )

        if new_submission is not None:
            queued_submissions.append(new_submission)
            skipped_students.remove(student)

            print(
                f"\n{student.full_name} successfully exempted from {assignment.name}."
            )

    def make_new_submission_fn(student: Student) -> Callable[[], None]:
        """
        Helper method necessary for narrowing a student variable.

        Args:
            student (Student): The `Student` record being narrowed from None to `Student` type.

        Returns:
            Lambda expression that calls `prompt_score_skipped_student()`.
        """
        return lambda: prompt_score_skipped_student(student)

    def make_mark_exempt_fn(student: Student) -> Callable[[], None]:
        """
        Helper method necessary for narrowing a student variable.

        Args:
            student (Student): The `Student` record being narrowed from None to `Student` type.

        Returns:
            Lambda expression that calls `create_exempt_submission()`.
        """
        return lambda: create_exempt_submission(student)

    while True:
        if not skipped_students:
            print("\nThere are no skipped students to review.")
            break

        student = helpers.prompt_selection_from_list(
            list_data=skipped_students,
            list_description="Skipped Students",
            sort_key=lambda x: (x.last_name, x.first_name),
            formatter=formatters.format_student_oneline,
        )

        if student is None:
            break

        print(f"\nYou are viewing the following student:")
        print(formatters.format_student_oneline(student))

        title = "What would you like to do with this student?"
        options = [
            ("Record a submission", make_new_submission_fn(student)),
            ("Mark this student exempt", make_mark_exempt_fn(student)),
        ]
        zero_option = "Choose a different skipped student"

        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response is MenuSignal.EXIT:
            continue

        elif callable(menu_response):
            menu_response()

        else:
            raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

        if not helpers.confirm_action(
            "Would you like to continue reviewing the skipped students?"
        ):
            break

    helpers.returning_to("Submission batch entry review")


def resolve_existing_submission_conflict(
    linked_assignment: Assignment, linked_student: Student, gradebook: Gradebook
) -> Submission | None:
    """
    Handles a submission conflict when a `Student` has already submitted work for a given `Assignment`.

    Prompts the user to either:
    - Edit the existing submission,
    - Delete it and create a new one, or
    - Cancel the operation.

    Args:
        linked_assignment (Assignment): The assignment associated with the existing submission.
        linked_student (Student): The student associated with the existing submission.
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        Submission | None:
            - A new `Submission` object if the user deletes the existing record and opts to create a replacement.
            - `None` if the user cancels or chooses to edit the existing submission instead.

    Raises:
        RuntimeError: If the menu response is unrecognized.
    """
    submission_response = gradebook.find_submission_by_assignment_and_student(
        linked_assignment.id, linked_student.id
    )

    existing_submission = (
        submission_response.data["record"] if submission_response.success else None
    )

    if existing_submission is None:
        return

    print(
        f"\nA submission from {linked_student.full_name} already exists for {linked_assignment.name}."
    )

    title = "What would you like to do?"
    options = [
        ("Edit the existing submission", edit_submission),
        ("Delete and create a new submission", delete_and_create_new_submission),
    ]
    zero_option = "Cancel and return"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response is MenuSignal.EXIT:
        helpers.returning_without_changes()
        return

    elif callable(menu_response):
        return menu_response(existing_submission, gradebook)

    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")


def delete_and_create_new_submission(
    existing_submission: Submission, gradebook: Gradebook
) -> Submission | None:
    """
    Allows the user to delete the existing `Submission` record and create a new one.

    Args:
        existing_submission (Submission): The submission targeted for deletion and replacement.
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - It is permissible for the user to delete the existing Submission but not create a new submission.
        - After the call to `confirm_and_remove()`, the method checks the gradebook to see whether the deletion succeeded or not. If not, the method exits early and returns None.
    """
    gradebook_response = gradebook.get_assignment_and_student(existing_submission)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        return None

    assignment = gradebook_response.data["assignment"]
    student = gradebook_response.data["student"]

    confirm_and_remove(existing_submission, gradebook)

    submission_response = gradebook.find_submission_by_uuid(existing_submission.id)

    if submission_response.success:
        print("Submission was not removed.")
        return None

    new_submission = prompt_new_submission(assignment, student, gradebook)

    if new_submission is None:
        print("The existing submission was deleted, but no new submission was created.")

    return new_submission


# === data input helpers ===


# TODO: resume refactor from here
def prompt_points_earned_input_or_cancel() -> float | MenuSignal:
    """
    Solicits user input for points earned, casts it to float, and treats a blank input as 'cancel'.

    Returns:
        User input as a float, or MenuSignal.CANCEL if input is "".

    Notes:
        Handles the type casting from string to float, but further data validation is the responsibility of the caller.
    """
    while True:
        user_input = helpers.prompt_user_input_or_cancel(
            "Enter points earned (leave blank to cancel):"
        )

        if isinstance(user_input, MenuSignal):
            return user_input

        try:
            return float(user_input)
        except ValueError:
            print(
                "\nError: Invalid input. Please enter a number or leave blank to cancel."
            )


def prompt_score_with_bailout(
    assignment: Assignment, student: Student
) -> Optional[float] | MenuSignal:
    """
    Input prompt for use during the batch entry process. Accepts a float, treats a blank input as 'skip', and 'q' as 'cancel'.

    Args:
        assignment: The Assignment associated with this submission.
        student: The Student associated with this submission.

    Returns:
        One of three return values: float value, None if input is "", and MenuSignal.CANCEL if input is "q" or ":exit".

    Notes:
        Handles the type casting from string to float, but further data validation is the responsibility of the caller.
    """
    while True:
        print(f"\nRecord a submission from {student.full_name} in {assignment.name}")

        user_input = helpers.prompt_user_input_or_none(
            "Enter points earned (leave blank to skip, 'q' to cancel):"
        )

        if user_input is None:
            return None
        elif user_input in {"q", ":exit"}:
            return MenuSignal.CANCEL

        try:
            return float(user_input)
        except ValueError:
            print(
                "\nInvalid input. Please enter a number, leave blank to skip, or 'q' to cancel."
            )


# === edit submission ===


def get_editable_fields() -> list[tuple[str, Callable[[Submission, Gradebook], bool]]]:
    """
    Helper method to organize the list of editable fields and their related functions.

    Returns:
        A list of tuples - pairs of strings and function names.
    """
    return [
        ("Score", edit_score_and_confirm),
        ("Late Status", edit_late_and_confirm),
        ("Exempt Status", edit_exempt_and_confirm),
    ]


def find_and_edit_submission(gradebook: Gradebook) -> None:
    """
    Prompts user to search for a Submission and then passes the result to edit_submission().

    Args:
        gradebook: The active Gradebook.
    """
    submission = prompt_find_submission(gradebook)

    if submission is not None:
        edit_submission(submission, gradebook)


def edit_submission(
    submission: Submission,
    gradebook: Gradebook,
    return_context: str = "Manage Submissions menu",
) -> None:
    """
    Dispatch method for selecting an editable field and using boolean return values to monitor whether changes have been made.

    Args:
        submission: The Submission being edited.
        gradebook: The active Gradebook.

    Notes:
        Uses a function scoped variable to flag whether the edit_* methods have manipulated the Submission at all.
        If so, the user is prompted to either save changes now, or defer saving and mark the Gradebook dirty for saving upstream.

    Raises:
        RuntimeError: If the menu response is unrecognized.
    """
    print("\nYou are editing the following submission:")
    print(formatters.format_submission_multiline(submission, gradebook))

    title = formatters.format_banner_text("Editable Fields")
    options = get_editable_fields()
    zero_option = "Finish editing and return"

    unsaved_changes = False

    while True:
        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response is MenuSignal.EXIT:
            break
        elif callable(menu_response):
            if menu_response(submission, gradebook):
                unsaved_changes = True
        else:
            raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

        if not helpers.confirm_action(
            "Would you like to continue editing this submission?"
        ):
            break

    if unsaved_changes:
        if helpers.confirm_unsaved_changes():
            gradebook.save(gradebook.path)
        else:
            gradebook.mark_dirty()
    else:
        helpers.returning_without_changes()

    helpers.returning_to("Manage Submissions menu")


# def edit_queued_submission(submission: Submission, gradebook: Gradebook) -> None:
#     """
#     Dispatch method for the edit menu that does not track changes, since the edited Submission has not yet been added to the Gradebook.
#
#     Args:
#         submission: A Submission not yet added to the Gradebook and targeted for editing.
#         gradebook: The active Gradebook.
#
#     Raises:
#         RuntimeError: If the menu response is unrecognized.
#     """
#     print("\nYou are editing the following submission:")
#     print(formatters.format_submission_multiline(submission, gradebook))
#
#     title = formatters.format_banner_text("Editable Fields")
#     options = get_editable_fields()
#     zero_option = "Finish editing and return"
#
#     while True:
#         menu_response = helpers.display_menu(title, options, zero_option)
#
#         if menu_response is MenuSignal.EXIT:
#             break
#         elif callable(menu_response):
#             menu_response(submission, gradebook)
#         else:
#             raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")
#
#         if not helpers.confirm_action(
#             "Would you like to continue editing this submission?"
#         ):
#             break
#
#     helpers.returning_to("Submission preview")


def edit_score_and_confirm(submission: Submission, gradebook: Gradebook) -> bool:
    """
    Edits the points_earned field of a Submission.

    Returns:
        True if the score was changed, and False otherwise.
    """
    assignment = gradebook.find_assignment_by_uuid(submission.assignment_id)

    if assignment is None:
        return False

    current_points_earned = submission.points_earned
    new_points_earned = prompt_points_earned_input_or_cancel()
    points_possible = assignment.points_possible

    if new_points_earned is MenuSignal.CANCEL:
        helpers.returning_without_changes()
        return False
    else:
        new_points_earned = cast(float, new_points_earned)

    print(
        f"Current score: {current_points_earned} / {points_possible} ... New score: {new_points_earned} / {points_possible}"
    )

    if not helpers.confirm_make_change():
        helpers.returning_without_changes()
        return False

    try:
        submission.points_earned = new_points_earned
        print(
            f"\nSubmission score successfully updated to {new_points_earned} / {points_possible}."
        )
        return True
    except (TypeError, ValueError) as e:
        print(f"\nError: Could not update submission ... {e}:")
        helpers.returning_without_changes()
        return False


def edit_late_and_confirm(submission: Submission, _: Gradebook) -> bool:
    """
    Toggles the is_late field of a Submission.

    Returns:
        True if the late status was changed, and False otherwise.
    """
    print(
        f"\nSubmission current late status: {'Late' if submission.is_late else 'Not Late'}."
    )

    if not helpers.confirm_action("Would you like to edit the late status?"):
        helpers.returning_without_changes()
        return False

    try:
        submission.toggle_late_status()
        print(
            f"\nSubmission late status successfully updated to {'Late' if submission.is_late else 'Not Late'}."
        )
        return True
    except Exception as e:
        print(f"\nError: Could not update submission ... {e}")
        helpers.returning_without_changes()
        return False


def edit_exempt_and_confirm(submission: Submission, _: Gradebook) -> bool:
    """
    Toggles the is_exempt field of a Submission.

    Returns:
        True is the exempt status was changed, and False otherwise.
    """
    print(
        f"\nSubmission current exempt status: {'Exempt' if submission.is_exempt else 'Not Exempt'}."
    )

    if not helpers.confirm_action("Would you like to edit the exempt status?"):
        helpers.returning_without_changes()
        return False

    try:
        submission.toggle_exempt_status()
        print(
            f"\nSubmission exempt status successfully updated to {'Exempt' if submission.is_exempt else 'Not Exempt'}."
        )
        return True
    except Exception as e:
        print(f"\nError: Could not update submission ... {e}")
        helpers.returning_without_changes()
        return False


# === remove submission ===


def find_and_remove_submission(gradebook: Gradebook) -> None:
    """
    Prompts user to search for a Submission and then passes the result to remove_submission().

    Args:
        gradebook: The active Gradebook.
    """
    submission = prompt_find_submission(gradebook)

    if submission is not None:
        remove_submission(submission, gradebook)


def remove_submission(submission: Submission, gradebook: Gradebook) -> None:
    """
    Dispatch method to either delete or edit the Submission, or return without changes.

    Args:
        submission: The Submission targeted for deletion/editing.
        gradebook: The active Gradebook.

    Raises:
        RuntimeError: If the menu response if unrecognized.

    Notes:
        Uses a function scoped variable to detect if any function calls report a data change.
        If so, the user is prompted to either save now or defer, in which case the Gradebook is marked dirty.
    """
    print(f"\nYou are viewing the following submission:")
    print(formatters.format_submission_oneline(submission, gradebook))

    title = "What would you like to do?"
    options = [
        (
            "Remove this submission (permanently delete the record)",
            confirm_and_remove,
        ),
        (
            "Edit this submission (change the score, late status, or exempt status)",
            edit_submission,
        ),
    ]
    zero_option = "Return to Manage Submissions menu"

    unsaved_changes = False

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response is MenuSignal.EXIT:
        helpers.returning_without_changes()
        return None
    elif callable(menu_response):
        if menu_response(submission, gradebook):
            unsaved_changes = True
    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

    if unsaved_changes:
        if helpers.confirm_unsaved_changes():
            gradebook.save(gradebook.path)
        else:
            gradebook.mark_dirty()

    helpers.returning_to("Manage Submissions menu")


def confirm_and_remove(submission: Submission, gradebook: Gradebook) -> bool:
    """
    Deletes the Submission from the Gradebook after preview and confirmation.

    Args:
        submission: The Submission targeted for deletion.
        gradebook: The active Gradebook.

    Returns:
        True if the Submission was removed, and False otherwise.
    """
    caution_banner = formatters.format_banner_text("CAUTION!")
    print(f"\n{caution_banner}")
    print("You are about to permanently delete the following submission:")
    print(formatters.format_submission_multiline(submission, gradebook))

    confirm_deletion = helpers.confirm_action(
        "Are you sure you want to permanently delete this submission? This action cannot be undone."
    )

    if not confirm_deletion:
        helpers.returning_without_changes()
        return False

    try:
        gradebook.remove_submission(submission)
        print("\nSubmission successfully removed from Gradebook.")
        return True
    except Exception as e:
        print(f"\nError: Could not remove submission ... {e}")
        helpers.returning_without_changes()
        return False


def delete_queued_submission(
    queued_submissions: list[Submission],
    skipped_students: list[Student],
    submission: Submission,
    gradebook: Gradebook,
) -> None:
    """
    Deletes the user queued submission and adds the student to skipped students after preview and confirmation.

    Args:
        queued_submissions: The queued Submissions generated during batch entry.
        skipped_students: The Students skipped during batch entry.
        submission: The queued Submission targeted for deletion.
        gradebook: The active Gradebook.

    Notes:
        No save prompt or gradebook.mark_dirty() since these Submissions have not yet been added to the Gradebook.
    """
    student = gradebook.find_student_by_uuid(submission.student_id)

    if student is None:
        return None

    caution_banner = formatters.format_banner_text("CAUTION!")
    print(f"\n{caution_banner}")
    print("You are about to permanently delete the following submission:")
    print(formatters.format_submission_multiline(submission, gradebook))

    confirm_deletion = helpers.confirm_action(
        "Are you sure you want to permanently delete this submission? This action cannot be undone."
    )

    if not confirm_deletion:
        helpers.returning_without_changes()
        return None

    queued_submissions.remove(submission)
    skipped_students.append(student)
    print(
        f"\nSubmission successfully deleted and {student.full_name} added to skipped students list."
    )


# === view submission ===


def view_submissions_menu(gradebook: Gradebook) -> None:
    """
    Dispatch method for the various view options (individual, all by student, all by assignment).

    Args:
        gradebook: The active Gradebook.

    Raises:
        RuntimeError: If the menu response is unrecognized.
    """
    title = "View Submissions"
    options = [
        ("View Individual Submission", view_individual_submission),
        ("View All Submissions by Assignment", view_submissions_by_assignment),
        ("View All Submissions by Student", view_submissions_by_student),
    ]
    zero_option = "Return to Manage Submissions menu"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response is MenuSignal.EXIT:
        return None
    elif callable(menu_response):
        menu_response(gradebook)
    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")


def view_individual_submission(gradebook: Gradebook) -> None:
    """
    Calls find_submission() and then displays a one-line view of that Submission, followed by a prompt to view the multi-line view or return.

    Args:
        gradebook: The active Gradebook.
    """
    submission = prompt_find_submission(gradebook)

    if submission is None:
        return None

    print("\nYou are viewing the following submission:")
    print(formatters.format_submission_oneline(submission, gradebook))

    if helpers.confirm_action(
        "Would you like to see an expanded view of this submission?"
    ):
        print(formatters.format_submission_multiline(submission, gradebook))


def view_submissions_by_assignment(gradebook: Gradebook) -> None:
    """
    Searches for an Assigment and then displays a list of linked Submissions.

    Args:
        gradebook: The active Gradebook.
    """

    def sort_key_student_name(submission: Submission) -> Optional[tuple[str, str]]:
        """
        Sort key method to organize the Submissions in order of Student name (last, first).

        Args:
            submission: The Submission being sorted.

        Returns:
            Either a tuple (last name, firstname) or None if the Student cannot be found.
        """
        student = gradebook.find_student_by_uuid(submission.student_id)
        return (student.last_name, student.first_name) if student else None

    assignment = prompt_find_assignment(gradebook)

    if assignment is MenuSignal.CANCEL:
        return None
    else:
        assignment = cast(Assignment, assignment)

    banner = formatters.format_banner_text(f"Submissions to {assignment.name}")
    print(f"\n{banner}")

    submissions = gradebook.get_records(
        gradebook.submissions, lambda x: x.assignment_id == assignment.id
    )

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
    """
    Searches for a Student and then displays a list of linked Submissions.

    Args:
        gradebook: The active Gradebook.
    """

    def sort_key_assignment_due_date(submission: Submission) -> str:
        """
        Sort key method to order the Submissions in order of Assignment due date.

        Args:
            submission: The Submission being sorted.

        Returns:
            The due date in iso format as a string, or "" if the due date cannot be found.
        """
        assignment = gradebook.find_assignment_by_uuid(submission.assignment_id)
        due_date_iso = assignment.due_date_iso if assignment else ""
        return due_date_iso if due_date_iso else ""

    student = prompt_find_student(gradebook)

    if student is MenuSignal.CANCEL:
        return None
    else:
        student = cast(Student, student)

    banner = formatters.format_banner_text(f"Submissions from {student.full_name}")
    print(f"\n{banner}")

    submissions = gradebook.get_records(
        gradebook.submissions, lambda x: x.student_id == student.id
    )

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


def prompt_find_submission(gradebook: Gradebook) -> Optional[Submission]:
    """
    Prompts search for linked Assignment and Student, and then returns the associated Submission.

    Args:
        gradebook: The active Gradebook.

    Returns:
        The linked Submission, or None if no matching Submission exists.
    """
    linked_assignment = prompt_find_assignment(gradebook)

    if linked_assignment is MenuSignal.CANCEL:
        return None
    else:
        linked_assignment = cast(Assignment, linked_assignment)

    linked_student = prompt_find_student(gradebook)

    if linked_student is MenuSignal.CANCEL:
        return None
    else:
        linked_student = cast(Student, linked_student)

    return gradebook.find_submission_by_assignment_and_student(
        linked_assignment.id, linked_student.id
    )


def prompt_find_assignment(gradebook: Gradebook) -> Assignment | MenuSignal:
    """
    Menu dispatch for either finding an Assignment by search or from a list of active Assignments.

    args:
        gradebook: The active Gradebook.

    Returns:
        The selected Assignment, or MenuSignal.CANCEL if the user bails out.

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


def prompt_find_student(gradebook: Gradebook) -> Student | MenuSignal:
    """
    Menu dispatch for either finding a Student by search or from a list of active Students.

    args:
        gradebook: The active Gradebook.

    Returns:
        The selected Student, or MenuSignal.CANCEL if the user bails out.

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
