# cli/formatters.py


from models.assignment import Assignment
from models.category import Category
from models.gradebook import Gradebook
from models.student import Student
from models.submission import Submission
from textwrap import dedent
from typing import Optional


def format_banner_text(title: str, width: int = 40) -> str:
    line = "=" * width
    centered_title = f"{title:^{width}}"
    return f"{line}\n{centered_title}\n{line}"


# === Student formatters ===


def format_student_oneline(student: Student) -> str:
    status = "[ARCHIVED]" if not student.is_active else ""
    return f"{student.full_name:<20} {status} | {student.email}"


# === Category formatters ===


# TODO: handle weighted and unweighted gracefully
def format_category_oneline(category: Category) -> str:
    status = "[ARCHIVED]" if not category.is_active else ""
    weight = f"{category.weight} %" if category.weight else "Unweighted"
    return f"{category.name:<20} {status} | {weight}"


# === Assignment formatters ===


def format_assignment_due_date(
    due_date_str: Optional[str], due_time_str: Optional[str]
) -> str:
    return (
        f"{due_date_str} at {due_time_str}"
        if due_date_str and due_time_str
        else "No due date"
    )


def format_assignment_oneline(assignment: Assignment) -> str:
    status = "[ARCHIVED]" if not assignment.is_active else ""
    due_date = format_assignment_due_date(
        assignment.due_date_str,
        assignment.due_time_str,
    )
    return f"{assignment.name:<20} {status}| Due: {due_date}"


# === Submission formatters ===


def format_submission_oneline(submission: Submission, gradebook: Gradebook) -> str:
    linked_assignment = gradebook.find_assignment_by_uuid(submission.assignment_id)
    linked_student = gradebook.find_student_by_uuid(submission.student_id)

    if linked_assignment is None or linked_student is None:
        return "Error: Submission is missing either the linked student or assignment record"

    late_status = "[LATE] " if submission.is_late else ""
    score_or_exempt = (
        "[EXEMPT]"
        if submission.is_exempt
        else f"{submission.points_earned} / {linked_assignment.points_possible}"
    )

    return f"{late_status}{linked_assignment.name:<20} | {linked_student.full_name:<20} | {score_or_exempt}"


def format_submission_multiline(submission: Submission, gradebook: Gradebook) -> str:
    linked_assignment = gradebook.find_assignment_by_uuid(submission.assignment_id)
    linked_student = gradebook.find_student_by_uuid(submission.student_id)

    if linked_assignment is None or linked_student is None:
        return (
            "Error: Submission is missing either the inked student or assignment record"
        )

    return dedent(
        f"""\
        Submission from {linked_student.full_name} in {linked_assignment.name}:
        ... Score: {submission.points_earned} / {linked_assignment.points_possible}
        ... Late: {'Yes' if submission.is_late else 'No'}
        ... Exempt: {'Yes' if submission.is_exempt else 'No'}
        """
    )
