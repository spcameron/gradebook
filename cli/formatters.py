# cli/formatters.py


from models.category import Category
from models.student import Student
from typing import Optional


def format_banner_text(title: str, width: int = 40) -> str:
    line = "=" * width
    centered_title = f"{title:^{width}}"
    return f"{line}\n{centered_title}\n{line}"


# === Student formatters ===


def format_student_oneline(student: Student) -> str:
    return f"{student.full_name:<20} | {student.email}"


# === Category formatters ===


# TODO: handle weighted and unweighted gracefully
def format_category_oneline(category: Category) -> str:
    return f"{category.name:<20} | {category.weight} %"


# === Assignment formatters ===


def format_assignment_due_date(
    due_date_str: Optional[str], due_time_str: Optional[str]
) -> str:
    return (
        f"{due_date_str} at {due_time_str}"
        if due_date_str and due_time_str
        else "No due date"
    )


# === Submission formatters ===
