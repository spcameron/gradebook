# cli/menu_helpers.py

import datetime
from enum import Enum
from typing import Any, Callable, Iterable, Optional

import cli.formatters as formatters
from core.response import Response
from models.assignment import Assignment
from models.category import Category
from models.gradebook import Gradebook
from models.student import Student
from models.submission import Submission
from models.types import RecordType


class MenuSignal(Enum):
    CANCEL = "CANCEL"
    DEFAULT = "DEFAULT"
    EXIT = "EXIT"


# === display methods ===


def display_menu(
    title: str,
    options: list[tuple[str, Callable[..., Any]]],
    zero_option: str = "Return",
) -> MenuSignal | Callable[..., Any]:
    while True:
        print(f"\n{title}")
        for i, (label, _) in enumerate(options, 1):
            print(f"{i}. {label}")
        print(f"0. {zero_option}")

        choice = prompt_user_input("\nSelect an option: ")

        if choice == "0":
            return MenuSignal.EXIT
        try:
            # casts choice to int and adjusts for zero-index, retrieves action from tuple
            return options[int(choice) - 1][1]
        except (ValueError, IndexError):
            print("Invalid selection. Please try again.")


def display_results(
    results: Iterable[Any],
    show_index: bool = False,
    formatter: Callable[[Any], str] = lambda x: str(x),
) -> None:
    for i, result in enumerate(results, 1):
        prefix = f"{i:>2}. " if show_index else ""
        print(f"{prefix}{formatter(result)}")


def sort_and_display_records(
    records: Iterable[RecordType],
    show_index: bool = False,
    formatter: Callable[[Any], str] = lambda x: str(x),
    sort_key: Callable[[RecordType], Any] = lambda x: x,
) -> None:
    sorted_records = sorted(records, key=sort_key)
    display_results(sorted_records, show_index, formatter)


def display_submission_results(
    results: Iterable[Submission],
    gradebook: Gradebook,
    show_index: bool = False,
    formatter: Callable[[Submission, Gradebook], str] = lambda s, _: str(s),
) -> None:
    for i, result in enumerate(results, 1):
        prefix = f"{i:>2}. " if show_index else ""
        print(f"{prefix}{formatter(result, gradebook)}")


def sort_and_display_submissions(
    submissions: Iterable[Submission],
    gradebook: Gradebook,
    show_index: bool = False,
    formatter: Callable[[Submission, Gradebook], str] = lambda s, _: str(s),
    sort_key: Callable[[Submission], Any] = lambda x: x,
) -> None:
    sorted_submissions = sorted(submissions, key=sort_key)
    display_submission_results(sorted_submissions, gradebook, show_index, formatter)


def sort_and_display_course_dates(
    calendar_dates: set[datetime.date] | list[datetime.date],
    calendar_name: str = "Calendar View",
) -> None:
    banner = formatters.format_banner_text(calendar_name)
    print(f"\n{banner}")

    last_month_printed = (None, None)

    for current_date in sorted(calendar_dates):
        current_month_and_year = (current_date.month, current_date.year)
        if current_month_and_year != last_month_printed:
            formatted_month = formatters.format_month_and_year(current_date)
            print(f"\n{formatted_month}\n")
            last_month_printed = current_month_and_year

        print(f"   {formatters.format_class_date_short(current_date)}")


def display_attendance_summary(class_date: datetime.date, gradebook: Gradebook) -> None:
    attendance_summary = gradebook.get_attendance_for_date(class_date)

    print(f"\nAttendance summary for {formatters.format_class_date_long(class_date)}:")

    if class_date not in gradebook.class_dates:
        print(
            f"Error: {formatters.format_class_date_short(class_date)} is not in the course schedule."
        )
        return None

    if attendance_summary == {}:
        print(
            f"Error: Attendance has not been recorded for {formatters.format_class_date_short(class_date)}."
        )

    for id, attendance in attendance_summary:
        student = gradebook.find_student_by_uuid(id)
        if student is not None:
            print(f"... {student.full_name:<20} | {attendance}")


# === prompt user input methods ===


def confirm_action(prompt: str) -> bool:
    while True:
        choice = prompt_user_input(f"{prompt} (y/n): ").lower()

        if choice == "y" or choice == "yes":
            return True
        elif choice == "n" or choice == "no":
            return False
        else:
            print("Invalid selection. Please try again.")


def confirm_make_change() -> bool:
    return confirm_action("Do you want to make this change?")


def confirm_unsaved_changes() -> bool:
    return confirm_action(
        "There are unsaved changes to the Gradebook. Do you want to save now?"
    )


def prompt_if_dirty(gradebook: Gradebook) -> None:
    if gradebook.has_unsaved_changes and confirm_unsaved_changes():
        gradebook.save()


def prompt_user_input(prompt: str) -> str:
    return input(f"\n{prompt}\n  >> ").strip()


def prompt_user_input_or_cancel(prompt: str) -> str | MenuSignal:
    response = prompt_user_input(prompt)
    return MenuSignal.CANCEL if response == "" else response


def prompt_user_input_or_default(prompt: str) -> str | MenuSignal:
    response = prompt_user_input(prompt)
    return MenuSignal.DEFAULT if response == "" else response


def prompt_user_input_or_none(prompt: str) -> str | None:
    response = prompt_user_input(prompt)
    return None if response == "" else response


# === finder, search, and select methods ===

# --- abstractions ---


def prompt_selection_from_list(
    list_data: list[RecordType],
    list_description: str,
    sort_key: Callable[[RecordType], Any] = lambda x: x,
    formatter: Callable[[RecordType], str] = lambda x: str(x),
) -> Optional[RecordType]:
    if not list_data:
        print(f"\nThere are no {list_description.lower()}.")
        return None

    print(f"\nThere are {len(list_data)} {list_description.lower()}.")
    sorted_list = sorted(list_data, key=sort_key)

    while True:
        print(f"\n{formatters.format_banner_text(list_description)}")
        display_results(sorted_list, True, formatter)
        choice = prompt_user_input("Select an option (0 to cancel):")

        if choice == "0":
            return None
        try:
            index = int(choice) - 1
            return sorted_list[index]
        except (ValueError, IndexError):
            print("\nInvalid selection. Please try again.")


def prompt_selection_from_search(
    search_results: list[RecordType],
    sort_key: Callable[[RecordType], Any] = lambda x: x,
    formatter: Callable[[RecordType], str] = lambda x: str(x),
) -> Optional[RecordType]:
    if not search_results:
        print("\nYour search returned no results.")
        return None

    if len(search_results) == 1:
        return search_results[0]

    print(f"\nYour search returned {len(search_results)}:")
    sorted_results = sorted(search_results, key=sort_key)

    while True:
        display_results(sorted_results, True, formatter)
        choice = prompt_user_input("Select an option (0 to cancel):")

        if choice == "0":
            return None
        try:
            index = int(choice) - 1
            return sorted_results[index]
        except (ValueError, IndexError):
            print("\nInvalid selection. Please try again.")


# --- students ---


def search_students(gradebook: Gradebook) -> list[Student]:
    query = prompt_user_input("Search for a student by name or email:").lower()
    return gradebook.find_student_by_query(query)


def prompt_student_selection_from_search(
    search_results: list[Student],
) -> Optional[Student]:
    return prompt_selection_from_search(
        search_results,
        lambda x: (x.last_name, x.first_name),
        formatters.format_student_oneline,
    )


def prompt_student_selection_from_list(
    list_data: list[Student], list_description: str
) -> Optional[Student]:
    return prompt_selection_from_list(
        list_data,
        list_description,
        lambda x: (x.last_name, x.first_name),
        formatters.format_student_oneline,
    )


def find_student_by_search(gradebook: Gradebook) -> Student | MenuSignal:
    """
    Wrapper method to compose searching and selecting a Student into one call.

    Args:
        gradebook: The active Gradebook.

    Returns:
        Either the selected Student, or MenuSignal.CANCEL if the search returns None.
    """
    search_results = search_students(gradebook)
    student = prompt_student_selection_from_search(search_results)
    return MenuSignal.CANCEL if student is None else student


def find_active_student_from_list(gradebook: Gradebook) -> Student | MenuSignal:
    """
    Wrapper method to compose generating a list of active Students and then choosing one from the list.

    Args:
        gradebook: The active Gradebook.

    Returns:
        Either the selected Student, or MenuSignal.CANCEL if the list is empty or the user cancels.
    """
    active_students = gradebook.get_records(gradebook._students, lambda x: x.is_active)
    student = prompt_student_selection_from_list(active_students, "Active Students")
    return MenuSignal.CANCEL if student is None else student


def find_inactive_student_from_list(gradebook: Gradebook) -> Student | MenuSignal:
    """
    Wrapper method to compose generating a list of inactive Students and then choosing one from the list.

    Args:
        gradebook: The active Gradebook.

    Returns:
        Either the selected Student, or MenuSignal.CANCEL if the list is empty or the user cancels.
    """
    inactive_students = gradebook.get_records(
        gradebook._students, lambda x: not x.is_active
    )
    student = prompt_student_selection_from_list(inactive_students, "Inactive Students")
    return MenuSignal.CANCEL if student is None else student


# --- categories ---


def search_categories(gradebook: Gradebook) -> list[Category]:
    query = prompt_user_input("Search for a category by name:").lower()
    return gradebook.find_category_by_query(query)


def prompt_category_selection_from_search(
    search_results: list[Category],
) -> Optional[Category]:
    return prompt_selection_from_search(
        search_results, lambda x: x.name, formatters.format_category_oneline
    )


def prompt_category_selection_from_list(
    list_data: list[Category], list_description: str
) -> Optional[Category]:
    return prompt_selection_from_list(
        list_data,
        list_description,
        lambda x: x.name,
        formatters.format_category_oneline,
    )


def find_category_by_search(gradebook: Gradebook) -> Category | MenuSignal:
    """
    Wrapper method to compose searching and selecting a Category into one call.

    Args:
        gradebook: The active Gradebook.

    Returns:
        The selected Category, or MenuSignal.CANCEL if the search yields no hits.
    """
    search_results = search_categories(gradebook)
    category = prompt_category_selection_from_search(search_results)
    return MenuSignal.CANCEL if category is None else category


def find_active_category_from_list(gradebook: Gradebook) -> Category | MenuSignal:
    """
    Wrapper method to compose generating a list of active Categories and selecting one from the list.

    Args:
        gradebook: The active Gradebook.

    Returns:
        Either the selected Category, or MenuSignal.CANCEL if the list is empty or the user cancels.
    """
    active_categories = gradebook.get_records(
        gradebook.categories, lambda x: x.is_active
    )
    category = prompt_category_selection_from_list(
        active_categories, "Active Categories"
    )
    return MenuSignal.CANCEL if category is None else category


def find_inactive_category_from_list(gradebook: Gradebook) -> Category | MenuSignal:
    """
    Wrapper method to compose generating a list of inactive Categories and selecting one from the list.

    Args:
        gradebook: The active Gradebook.

    Returns:
        Either the selected Category, or MenuSignal.CANCEL if the list is empty or the user cancels.
    """
    inactive_categories = gradebook.get_records(
        gradebook.categories, lambda x: not x.is_active
    )
    category = prompt_category_selection_from_list(
        inactive_categories, "Inactive Categories"
    )
    return MenuSignal.CANCEL if category is None else category


# --- assignments ---


def search_assignments(gradebook: Gradebook) -> list[Assignment]:
    query = prompt_user_input("Search for an assignment by name:").lower()
    return gradebook.find_assignment_by_query(query)


def prompt_assignment_selection_from_search(
    search_results: list[Assignment],
) -> Optional[Assignment]:
    return prompt_selection_from_search(
        search_results, lambda x: x.name, formatters.format_assignment_oneline
    )


def prompt_assignment_selection_from_list(
    list_data: list[Assignment], list_description: str
) -> Optional[Assignment]:
    return prompt_selection_from_list(
        list_data,
        list_description,
        lambda x: (x.category_id, x.due_date_iso),
        formatters.format_assignment_oneline,
    )


def find_assignment_by_search(
    gradebook: Gradebook,
) -> Assignment | MenuSignal:
    """
    Wrapper method to compose searching and selecting an Assignment into one call.

    Args:
        gradebook: The active Gradebook.

    Returns:
        Either the selected Assignment, or MenuSignal.CANCEL if the search returns None.
    """
    search_results = search_assignments(gradebook)
    assignment = prompt_assignment_selection_from_search(search_results)
    return MenuSignal.CANCEL if assignment is None else assignment


def find_active_assignment_from_list(
    gradebook: Gradebook,
) -> Assignment | MenuSignal:
    """
    Wrapper method to compose generating a list of active Assignments and selecting one from the list.

    Args:
        gradebook: The active Gradebook.

    Returns:
        Either the selected Assignment, or MenuSignal.CANCEL if the list is empty or the user cancels.
    """
    active_assignments = gradebook.get_records(
        gradebook.assignments, lambda x: x.is_active
    )
    assignment = prompt_assignment_selection_from_list(
        active_assignments, "Active Assignments"
    )
    return MenuSignal.CANCEL if assignment is None else assignment


def find_inactive_assignment_from_list(
    gradebook: Gradebook,
) -> Assignment | MenuSignal:
    """
    Wrapper method to compose generating a list of inactive Assignments and selecting one from the list.

    Args:
        gradebook: The active Gradebook.

    Returns:
        Either the selected Assignment, or MenuSignal.CANCEL if the list is empty or the user cancels.
    """
    inactive_assignments = gradebook.get_records(
        gradebook.assignments, lambda x: not x.is_active
    )
    assignment = prompt_assignment_selection_from_list(
        inactive_assignments, "Inactive Assignments"
    )
    return MenuSignal.CANCEL if assignment is None else assignment


# === often used messages ===


def returning_without_changes() -> None:
    print("\nReturning without changes.")


def returning_to(destination: str) -> None:
    print(f"\nReturning to {destination}.")


def caution_banner() -> None:
    caution_banner = formatters.format_banner_text("CAUTION!")
    print(f"\n{caution_banner}")


def display_response_failure(response: Response, debug: bool = False) -> None:
    if response.success:
        return

    error_label = (
        response.error.name if isinstance(response.error, Enum) else str(response.error)
    )

    print(f"\n[ERROR: {error_label}] {response.detail}")

    if debug and hasattr(response, "trace"):
        print(f"\nDebug Trace: {response.trace}")
