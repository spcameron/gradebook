# cli/formatters.py


import menu_helpers as helpers
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
    weight = f"{category.weight} %" if category.weight else "[UNWEIGHTED]"
    return f"{category.name:<20} {status} | {weight}"


def format_category_multiline(category: Category, gradebook: Gradebook) -> str:
    weight = f"{category.weight} %" if category.weight else "[UNWEIGHTED]"
    return dedent(
        f"""\
        Category in {gradebook.name}:
        ... Name: {category.name}
        ... Weight: {weight}
        ... Status: {category.status}
        """
    )


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
    try:
        assignment, student = gradebook.get_assignment_and_student(submission)
    except KeyError as e:
        return f"\nFormatter error: {e}"

    late_status = "[LATE] " if submission.is_late else ""
    score_or_exempt = (
        "[EXEMPT]"
        if submission.is_exempt
        else f"{submission.points_earned} / {assignment.points_possible}"
    )

    return f"{late_status}{assignment.name:<20} | {student.full_name:<20} | {score_or_exempt}"


def format_submission_multiline(submission: Submission, gradebook: Gradebook) -> str:
    try:
        assignment, student = gradebook.get_assignment_and_student(submission)
    except KeyError as e:
        return f"\nFormatter error: {e}"

    return dedent(
        f"""\
        Submission from {student.full_name} in {assignment.name}:
        ... Score: {submission.points_earned} / {assignment.points_possible}
        ... Late: {'Yes' if submission.is_late else 'No'}
        ... Exempt: {'Yes' if submission.is_exempt else 'No'}
        """
    )
