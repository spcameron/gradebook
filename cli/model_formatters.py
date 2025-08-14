# cli/model_formatters.py

# anything that renders domain objects or performs Gradebook read-only operations
from textwrap import dedent

import core.formatters as formatters
from models.assignment import Assignment
from models.category import Category
from models.gradebook import Gradebook
from models.student import Student
from models.submission import Submission

# === student formatters ===


def format_student_oneline(student: Student) -> str:
    status = " [ARCHIVED]" if not student.is_active else ""

    return f"{student.full_name:<20} | {student.email}{status}"


def format_student_multiline(student: Student, gradebook: Gradebook) -> str:
    return dedent(
        f"""\
        Student in {gradebook.name}:
        ... Name: {student.full_name}
        ... Email: {student.email}
        ... Status: {student.status}"""
    )


# === category formatters ===


def format_category_oneline(category: Category) -> str:
    status = " [ARCHIVED]" if not category.is_active else ""
    weight = f"{category.weight:>5.1f} %" if category.weight else "[UNWEIGHTED]"

    return f"{category.name:<20} | {weight}{status}"


def format_category_multiline(category: Category, gradebook: Gradebook) -> str:
    weight = f"{category.weight:>5.1f} %" if category.weight else "[UNWEIGHTED]"

    return dedent(
        f"""\
        Category in {gradebook.name}:
        ... Name: {category.name}
        ... Weight: {weight}
        ... Status: {category.status}"""
    )


# === assignment formatters ===


def format_assignment_oneline(assignment: Assignment) -> str:
    status = " [ARCHIVED]" if not assignment.is_active else ""
    due_date = formatters.format_due_date_from_strings(
        assignment.due_date_str,
        assignment.due_time_str,
    )

    return f"{assignment.name:<20} | Due: {due_date}{status}"


def format_assignment_multiline(assignment: Assignment, gradebook: Gradebook) -> str:
    if assignment.category_id:
        gradebook_response = gradebook.find_category_by_uuid(assignment.category_id)

        category = (
            gradebook_response.data["record"] if gradebook_response.success else None
        )

    else:
        category = None

    due_date = formatters.format_due_date_from_strings(
        assignment.due_date_str,
        assignment.due_time_str,
    )

    extra_credit = " [EXTRA CREDIT]" if assignment.is_extra_credit else ""

    return dedent(
        f"""\
        Assignment in {gradebook.name}:
        ... Name: {assignment.name}
        ... Category: {category.name if category else '[UNCATEGORIZED]'}
        ... Points Possible: {assignment.points_possible}{extra_credit}
        ... Due: {due_date}
        ... Status: {assignment.status}"""
    )


# === submission formatters ===


def format_submission_oneline(submission: Submission, gradebook: Gradebook) -> str:
    gradebook_response = gradebook.get_assignment_and_student(submission)

    if not gradebook_response.success:
        return f"\nFormatter error: {gradebook_response.detail}"

    assignment = gradebook_response.data["assignment"]
    student = gradebook_response.data["student"]

    late_status = " [LATE]" if submission.is_late else ""

    score_or_exempt = (
        "[EXEMPT]"
        if submission.is_exempt
        else f"{submission.points_earned} / {assignment.points_possible}"
    )

    return f"{assignment.name:<20} | {student.full_name:<20} | {score_or_exempt}{late_status}"


def format_submission_multiline(submission: Submission, gradebook: Gradebook) -> str:
    gradebook_response = gradebook.get_assignment_and_student(submission)

    if not gradebook_response.success:
        return f"\nFormatter error: {gradebook_response.detail}"

    assignment = gradebook_response.data["assignment"]
    student = gradebook_response.data["student"]

    return dedent(
        f"""\
        Submission from {student.full_name} to {assignment.name}:
        ... Score: {submission.points_earned} / {assignment.points_possible}
        ... Late: {submission.late_status}
        ... Exempt: {submission.exempt_status}"""
    )
