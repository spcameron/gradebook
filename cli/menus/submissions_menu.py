# cli/submissions_menu.py

"""
Manage Submissions menu for the Gradebook CLI.

Provides functions for adding, editing, removing, and viewing Submissions.
Includes a special batch entry process to quickly enter Submissions by Assignment.
"""

from typing import Callable, Optional, cast

import cli.formatters as formatters
import cli.menu_helpers as helpers
from cli.menu_helpers import MenuSignal
from core.utils import generate_uuid
from models.assignment import Assignment
from models.gradebook import Gradebook
from models.student import Student
from models.submission import Submission


def run(gradebook: Gradebook) -> None:
    """
    Top-level loop with dispatch for the Manage Submissions menu.

    Args:
        gradebook: The active Gradebook.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        The finally block guarantees a check for unsaved changes before returning.
    """
    title = formatters.format_banner_text("Manage Submissions")
    options = [
        ("Add Single Submission", add_single_submission),
        ("Batch Enter Submissions by Assignment", add_submissions_by_assignment),
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
    Loops a prompt to search/select an Assignment, Student, and create new Submission.

    Args:
        gradebook: The active gradebook.

    Notes:
        New Submissions are added to the Gradebook but not saved. Gradebook is marked dirty instead.
    """
    while True:
        assignment = prompt_find_assignment(gradebook)

        if assignment is MenuSignal.CANCEL:
            break
        else:
            assignment = cast(Assignment, assignment)

        student = prompt_find_student(gradebook)

        if student is MenuSignal.CANCEL:
            break
        else:
            student = cast(Student, student)

        new_submission = prompt_new_submission(assignment, student, gradebook)

        if new_submission is not None and preview_and_confirm_submission(
            new_submission, gradebook
        ):
            gradebook.add_submission(new_submission)
            gradebook.mark_dirty()
            print(
                f"\nSubmission for {student.full_name} to {assignment.name} successfully added."
            )

        if not helpers.confirm_action(
            "Would you like to continue adding new submissions?"
        ):
            break

    helpers.returning_to("Manage Submissions menu")


def add_submissions_by_assignment(gradebook: Gradebook) -> None:
    """
    Batch entry process for choosing an assignment, iterating across active student roster, and adding Submissions (or skipping) for each.

    Args:
        gradebook: The active gradebook.

    Notes:
        Only active students who have not submitted for this assignment are displayed.
        New submissions are queued for review and chance to edit.
        Skipped students are also queued for review and chance to mark exempt.
        After preview and confirmation, submissions are added to Gradebook but not saved. Gradebook is marked dirty.
    """
    assignment = prompt_find_assignment(gradebook)

    if assignment is MenuSignal.CANCEL:
        return None
    else:
        assignment = cast(Assignment, assignment)

    students_to_prompt = gradebook.get_records(
        gradebook.students,
        lambda student: student.is_active
        and not gradebook.submission_already_exists(assignment.id, student.id),
    )

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
                    f"\nDiscarding {len(queued_submissions)} submissions. No change saved."
                )
                return None
            else:
                print(f"\nAdding {student.full_name} to skipped students instead.")
                skipped_students.append(student)
                continue
        else:
            points_earned = cast(float, points_earned)

        try:
            submission_id = generate_uuid()
            new_submission = Submission(
                id=submission_id,
                student_id=student.id,
                assignment_id=assignment.id,
                points_earned=points_earned,
            )
            queued_submissions.append(new_submission)
        except (TypeError, ValueError) as e:
            print(f"\nError: Could not create submission ... {e}")
            skipped_students.append(student)
            print(f"\nAdding {student.full_name} to skipped students instead.")
            continue

    if queued_submissions:
        preview_batch_submissions(assignment, queued_submissions, gradebook)

    if queued_submissions and helpers.confirm_action(
        "Would you like to edit any of these submissions?"
    ):
        edit_batch_submissions(
            assignment, queued_submissions, skipped_students, gradebook
        )

    if skipped_students and helpers.confirm_action(
        "Would you like to review the skipped students?"
    ):
        review_skipped_students(
            assignment, queued_submissions, skipped_students, gradebook
        )

    if queued_submissions:
        preview_batch_submissions(assignment, queued_submissions, gradebook)

    if queued_submissions and helpers.confirm_action(
        "Do you want to add these submissions to the Gradebook?"
    ):
        for submission in queued_submissions:
            gradebook.add_submission(submission)
        gradebook.mark_dirty()
        print(
            f"\n{len(queued_submissions)} submissions successfully added to the Gradebook."
        )
    elif queued_submissions:
        print(f"\nDiscarding {len(queued_submissions)} submissions. No changes saved.")

    helpers.returning_to("Manage Submissions menu")


# TODO:
# preview and confirm is found in add methods
# data input prompts are extracted to their own functions
# export this pattern to Assignment, Categories, and Students
def prompt_new_submission(
    linked_assignment: Assignment, linked_student: Student, gradebook: Gradebook
) -> Optional[Submission]:
    """
    Creates a new Submission for the Assignment and Student passed as argument.

    Args:
        linked_assignment: The Assignment object to associate with this Submission.
        linked_student: The Student object to associate with this Submission.
        gradebook: The active Gradebook.

    Returns:
        A new Submission object, or None.

    Notes:
        Checks first for existing Submission with the given Assignment/Student pair and diverts if found.
    """
    if gradebook.submission_already_exists(linked_assignment.id, linked_student.id):
        handle_existing_submission(linked_assignment, linked_student, gradebook)
        return None

    print(
        f"\nYou are recording a submission from {linked_student.full_name} to {linked_assignment.name}."
    )

    points_earned = prompt_points_earned_input_or_cancel()

    if points_earned is MenuSignal.CANCEL:
        return None
    else:
        points_earned = cast(float, points_earned)

    try:
        submission_id = generate_uuid()
        new_submission = Submission(
            id=submission_id,
            student_id=linked_student.id,
            assignment_id=linked_assignment.id,
            points_earned=points_earned,
        )
        return new_submission
    except (TypeError, ValueError) as e:
        print(f"\nError: Could not create submission ... {e}")
        return None


def preview_and_confirm_submission(
    submission: Submission, gradebook: Gradebook
) -> bool:
    """
    Previews Submission details, offers opportunity to edit details, and prompts user for confirmation.

    Args:
        submission: The Submission under review.
        gradebook: The active Gradebook.

    Returns:
        True if user confirms the Submission details, and False otherwise.

    Notes:
        Uses edit_queued_submission() since this Submission object has not yet been added to the Gradebook.
    """
    print("\nYou are about to create the following submission:")
    print(formatters.format_submission_multiline(submission, gradebook))

    if helpers.confirm_action(
        "Would you like to edit this submission first (change the score, mark late, or mark exempt)?"
    ):
        edit_queued_submission(submission, gradebook)

    if helpers.confirm_action("Would you like to create this submission?"):
        return True
    else:
        print("Discarding submission.")
        return False


def preview_batch_submissions(
    assignment: Assignment, submissions: list[Submission], gradebook: Gradebook
) -> None:
    """
    Previews the queued Submissions from batch entry using a modified one-line formatting.

    Args:
        assignment: The linked Assignment.
        submissions: The list of queued Submissions populated during batch entry.
        gradebook: The active Gradebook.

    Notes:
        Includes a safeguard check for an empty submissions list for coverage, but callers will typically check for populated list first.
        If find_student_by_uuid() returns None, the formatter displays '[MISSING STUDENT]' in the preview.
    """
    if not submissions:
        print("\nThere are no queued submissions.")
        return None

    print(f"\nYou are about to add the following submissions to {assignment.name}:")

    for submission in submissions:
        student = gradebook.find_student_by_uuid(submission.student_id)
        student_name = student.full_name if student else "[MISSING STUDENT]"
        print(
            f"... {student_name:<20} | {submission.points_earned} / {assignment.points_possible}"
        )


def edit_batch_submissions(
    assignment: Assignment,
    queued_submissions: list[Submission],
    skipped_students: list[Student],
    gradebook: Gradebook,
) -> None:
    """
    Initiates a loop prompting user to select a queued submission and either edit or delete it.

    Args:
        assignment: The Assignment targeted by the batch entry.
        skipped_students: The list of Students who were skipped during batch entry.
        queued_submission: The list of Submissions created and queued during batch entry.
        gradebook: The active Gradebook.
    """

    def sort_key_student_name(submission: Submission) -> Optional[tuple[str, str]]:
        """
        Sort key method for organizing submissions by student name (last, first).

        Args:
            submission: The Submission being sorted.

        Returns:
            A tuple (last name, first name), or None if the Student could not be found.
        """
        student = gradebook.find_student_by_uuid(submission.student_id)
        return (student.last_name, student.first_name) if student else None

    def format_submission_batch_preview(submission: Submission) -> str:
        """
        Formatter method for previewing a queued submission.

        Args:
            submission: The Submission being previewed.

        Returns:
            A string representing the Submission preview.

        Notes:
            Displays '[LATE]' and '[EXEMPT]' in reponse to flags, and '[MISSING STUDENT]' if the linked Student cannot be located.
        """
        student = gradebook.find_student_by_uuid(submission.student_id)
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
        Helper method necessary for narrowing submission variable.

        Args:
            submission: The Submission being narrowed from Optional[Submission] to Submission type.
            gradebook: The active Gradebook.

        Returns:
            Lambda expression that calls edit_queued_submission().
        """
        return lambda: edit_queued_submission(submission, gradebook)

    def make_delete_fn(
        queued_submissions: list[Submission],
        skipped_students: list[Student],
        submission: Submission,
        gradebook: Gradebook,
    ) -> Callable[[], None]:
        """
        Helper method necessary for narrowing submission variable.

        Args:
            submission: The Submission being narrowed from Optional[Submission] to Submission type.
            gradebook: The Active Gradebook.

        Returns:
            Lambda expression that calls delete_queued_submission().

        Raises:
            RuntimeError: If the menu response is unrecognized.
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

    helpers.returning_to("Submission batch entry review")


def review_skipped_students(
    assignment: Assignment,
    queued_submissions: list[Submission],
    skipped_students: list[Student],
    gradebook: Gradebook,
) -> None:
    """
    Initiates a loop prompting user to select a skipped student and either add a submission or mark them exempt from this assignment.

    Args:
        assignment: The Assignment targeted by the batch entry.
        skipped_students: The list of Students who were skipped during batch entry.
        queued_submissions: The list of Submissions created and queued during batch entry.
        gradebook: The active Gradebook.
    """

    def prompt_score_skipped_student(student: Student) -> None:
        """
        Wrapper method to solicit a new score, then update the queued submissions and skipped students lists.

        Args:
            student: The Student selected from the skipped students list.
        """
        new_submission = prompt_new_submission(assignment, student, gradebook)

        if new_submission is not None and preview_and_confirm_submission(
            new_submission, gradebook
        ):
            queued_submissions.append(new_submission)
            skipped_students.remove(student)
            print(
                f"\nSubmission for {student.full_name} to {assignment.name} successfully added."
            )

    def create_exempt_submission(student: Student) -> None:
        """
        Wrapper method to create an 'Exempt' Submission, then update the queued submissions and skipped students lists.

        Args:
            student: The Student selected from the skipped students list.
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
        Helper method necessary for narrowing student variable.

        Args:
            student: The Student being narrowed from Optional[Student] to Student type.

        Returns:
            Lambda expression that calls prompt_score_skipped_student().
        """
        return lambda: prompt_score_skipped_student(student)

    def make_mark_exempt_fn(student: Student) -> Callable[[], None]:
        """
        Helper method necessary for narrowing student variable.

        Args:
            student: The Student being narrowed from Optional[Student] to Student type.

        Returns:
            Lambda expression that calls create_exempt_submission().

        Raises:
            RuntimeError: If the menu response is unrecognized.
        """
        return lambda: create_exempt_submission(student)

    while skipped_students:
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

    helpers.returning_to("Submission batch entry review")


def handle_existing_submission(
    linked_assignment: Assignment, linked_student: Student, gradebook: Gradebook
) -> None:
    """
    If an existing Submission is found, the user may edit the Submission or delete and replace it.

    Args:
        linked_assignment: The Assignment object associated with the existing submission
        linked_student: The Student object associated with the existing submission
        gradebook: The active Gradebook

    Raises:
        RuntimeError: If the menu response is unrecognized.
    """
    existing_submission = gradebook.find_submission_by_assignment_and_student(
        linked_assignment.id, linked_student.id
    )

    if existing_submission is None:
        return None

    print("\nA submission from this student already exists for this assignment.")

    title = "What would you like to do?"
    options = [
        ("Edit the existing submission", edit_submission),
        ("Delete and create a new submission", delete_and_create_new_submission),
    ]
    zero_option = "Cancel and return"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response is MenuSignal.EXIT:
        helpers.returning_without_changes()
        return None
    elif callable(menu_response):
        menu_response(existing_submission, gradebook)
    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")


def delete_and_create_new_submission(
    existing_submission: Submission, gradebook: Gradebook
) -> None:
    """
    Allows the user to delete the existing submission and create a new one.

    Args:
        existing_submission: The Submission targeted for deletion and replacement.
        gradebook: The active Gradebook.

    Notes:
        It is permissible for the user to delete the existing Submission but not create a new submission.
        If the user opts to defer saving changes, the Gradebook is marked dirty.
    """
    try:
        assignment, student = gradebook.get_assignment_and_student(existing_submission)
    except KeyError as e:
        print(f"Error: {e}")
        return None

    caution_banner = formatters.format_banner_text("CAUTION!")
    print(f"\n{caution_banner}")
    print("You are about to permanently delete the following submission:")
    print(formatters.format_submission_multiline(existing_submission, gradebook))

    confirm_deletion = helpers.confirm_action(
        "Are you sure you want to permanently delete this submission? This action cannot be undone."
    )

    if not confirm_deletion:
        helpers.returning_without_changes()
        return None
    else:
        gradebook.remove_submission(existing_submission)
        print("\nSubmission successfully removed from Gradebook.")

    new_submission = prompt_new_submission(assignment, student, gradebook)

    if new_submission is not None and preview_and_confirm_submission(
        new_submission, gradebook
    ):
        gradebook.add_submission(new_submission)
        print(
            f"\nNew submission for {student.full_name} to {assignment.name} successfully created and added."
        )
    else:
        print("Existing submission deleted, but no new submission created.")

    if helpers.confirm_unsaved_changes():
        gradebook.save(gradebook.path)
    else:
        gradebook.mark_dirty()


# === data input helpers ===


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


def edit_submission(submission: Submission, gradebook: Gradebook) -> None:
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


def edit_queued_submission(submission: Submission, gradebook: Gradebook) -> None:
    """
    Dispatch method for the edit menu that does not track changes, since the edited Submission has not yet been added to the Gradebook.

    Args:
        submission: A Submission not yet added to the Gradebook and targeted for editing.
        gradebook: The active Gradebook.

    Raises:
        RuntimeError: If the menu response is unrecognized.
    """
    print("\nYou are editing the following submission:")
    print(formatters.format_submission_multiline(submission, gradebook))

    title = formatters.format_banner_text("Editable Fields")
    options = get_editable_fields()
    zero_option = "Finish editing and return"

    while True:
        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response is MenuSignal.EXIT:
            break
        elif callable(menu_response):
            menu_response(submission, gradebook)
        else:
            raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

        if not helpers.confirm_action(
            "Would you like to continue editing this submission?"
        ):
            break

    helpers.returning_to("Submission preview")


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
