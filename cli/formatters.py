# cli/formatters.py


from models.assignment import Assignment
from models.category import Category
from models.student import Student
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
