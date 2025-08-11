# core/formatters.py

# all pure utilities & date/datetime helpers
# must never import from models!

import datetime
from typing import Any

# === generic text formatters ===


def format_banner_text(title: str, width: int = 40) -> str:
    line = "=" * width
    centered_title = f"{title:^(width)}"

    return f"{line}\n{centered_title}\n{line}"


def format_list_with_and(items: list[Any]) -> str:
    if not items:
        return ""

    if len(items) == 1:
        return items[0]

    if len(items) == 2:
        return " and ".join(items)

    return ", ".join(items[:-1]) + ", and" + items[-1]


# === date formatters ===


def format_due_date_from_datetime(due_date_dt: datetime.datetime | None) -> str:
    due_date_str = due_date_dt.strftime("%Y-%m-%d") if due_date_dt else None
    due_time_str = due_date_dt.strftime("%H:%M") if due_date_dt else None

    return format_due_date_from_strings(due_date_str, due_time_str)


def format_due_date_from_strings(
    due_date_str: str | None,
    due_time_str: str | None,
) -> str:
    return (
        f"{due_date_str} at {due_time_str}"
        if due_date_str and due_time_str
        else "[NO DUE DATE]"
    )


def format_class_date_short(class_date: datetime.date) -> str:
    return f"{class_date.strftime('%a, %b %d')}"


def format_class_date_long(class_date: datetime.date) -> str:
    return f"{class_date.strftime('%A, %B %d, %Y')}"


def format_month_and_year(class_date: datetime.date) -> str:
    line = "-" * 20
    month_and_year = class_date.strftime("%B %Y")
    return f"{line}\n{month_and_year}\n{line}"
