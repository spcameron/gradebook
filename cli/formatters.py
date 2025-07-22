# cli/formatters.py


from datetime import datetime
from textwrap import dedent
from typing import Optional

import menu_helpers as helpers

from models.assignment import Assignment
from models.category import Category
from models.gradebook import Gradebook
from models.student import Student
from models.submission import Submission


def format_banner_text(title: str, width: int = 40) -> str:
    line = "=" * width
    centered_title = f"{title:^{width}}"
    return f"{line}\n{centered_title}\n{line}"


# === Student formatters ===


def format_student_oneline(student: Student) -> str:
    status = "[ARCHIVED]" if not student.is_active else ""
    return f"{student.full_name:<20} {status} | {student.email}"


def format_student_multiline(student: Student, gradebook: Gradebook) -> str:
    return dedent(
        f"""\
        Student in {gradebook.name}:
        ... Name: {student.full_name}
        ... Email: {student.email}
        ... Status: {student.status}
        """
    )


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


def format_due_date_from_datetime(due_date_dt: Optional[datetime]) -> str:
    due_date_str = due_date_dt.strftime("%Y-%m-%d") if due_date_dt else None
    due_time_str = due_date_dt.strftime("%H:%M") if due_date_dt else None
    return format_due_date_from_strings(due_date_str, due_time_str)


def format_due_date_from_strings(
    due_date_str: Optional[str], due_time_str: Optional[str]
) -> str:
    return (
        f"{due_date_str} at {due_time_str}"
        if due_date_str and due_time_str
        else "[NO DUE DATE]"
    )


def format_assignment_oneline(assignment: Assignment) -> str:
    status = "[ARCHIVED]" if not assignment.is_active else ""
    due_date = format_due_date_from_strings(
        assignment.due_date_str,
        assignment.due_time_str,
    )
    return f"{assignment.name:<20} {status}| Due: {due_date}"


def format_assignment_multiline(assignment: Assignment, gradebook: Gradebook) -> str:
    category = (
        gradebook.find_category_by_uuid(assignment.category_id)
        if assignment.category_id
        else None
    )
    due_date = format_due_date_from_strings(
        assignment.due_date_str, assignment.due_time_str
    )
    extra_credit = " [EXTRA CREDIT]" if assignment.is_extra_credit else ""

    return dedent(
        f"""\
        Assignment in {gradebook.name}:
        ... Name: {assignment.name}
        ... Category: {category.name if category else '[UNCATEGORIZED]'}
        ... Points Possible: {assignment.points_possible}{extra_credit}
        ... Due: {due_date}
        ... Status: {assignment.status}
        """
    )


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
