# cli/menu_helpers.py

"""
Helper functions for CLI menus and user interaction in the Gradebook application.

This module provides utilities for:
- Displaying interactive menus and result lists
- Prompting for and validating user input
- Handling user selections and confirmation flows
- Displaying standard system messages and error feedback

These functions are shared across all menu modules to maintain consistent behavior and reduce duplication.
"""

import datetime
from enum import Enum
from typing import Any, Callable, Iterable

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
    """
    Displays a numbered CLI menu and returns the selected action.

    Args:
        title (str): The heading displayed above the menu options.
        options (list[tuple[str, Callable[..., Any]]]): A list of (label, action) pairs to present.
        zero_option (str, optional): The label for the "cancel" or "exit" option. Defaults to "Return".

    Returns:
        MenuSignal.EXIT if the user selects the zero option.
        Callable[..., Any]: The function associated with the selected menu item.

    Raises:
        ValueError, IndexError: Handled internally if user input is not a valid option.

    Notes:
        - Menu selection is repeated until a valid choice is made.
        - User input is matched by menu index, not by label.
    """
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
    """
    Prints a list of results to the console, optionally numbered and formatted.

    Args:
        results (Iterable[Any]): A sequence of results to display.
        show_index (bool, optional): If True, prepends a numbered index to each result. Defaults to False.
        formatter (Callable[[Any], str], optional): A function to convert each result to a display string. Defaults to str().
    """
    for i, result in enumerate(results, 1):
        prefix = f"{i:>2}. " if show_index else ""
        print(f"{prefix}{formatter(result)}")


def sort_and_display_records(
    records: Iterable[RecordType],
    show_index: bool = False,
    formatter: Callable[[Any], str] = lambda x: str(x),
    sort_key: Callable[[RecordType], Any] = lambda x: x,
) -> None:
    """
    Sorts and prints a list of records using a display formatter.

    Args:
        records (Iterable[RecordType]): The records to be sorted and displayed.
        show_index (bool, optional): If True, displays a numbered index alongside each record. Defaults to False.
        formatter (Callable[[Any], str], optional): Formats each record for output. Defaults to str().
        sort_key (Callable[[RecordType], Any], optional): Function used to sort records. Defaults to identity function.

    Notes:
        - Records are sorted before display.
        - Output is delegated to `display_results()`.
    """
    sorted_records = sorted(records, key=sort_key)
    display_results(sorted_records, show_index, formatter)


def display_submission_results(
    results: Iterable[Submission],
    gradebook: Gradebook,
    show_index: bool = False,
    formatter: Callable[[Submission, Gradebook], str] = lambda s, _: str(s),
) -> None:
    """
    Prints a list of `Submission` records with optional numbering and gradebook-aware formatting.

    Args:
        results (Iterable[Submission]): The submissions to display.
        gradebook (Gradebook): The active `Gradebook` used for context-aware formatting.
        show_index (bool, optional): If True, displays a numbered index alongside each result. Defaults to False.
        formatter (Callable[[Submission, Gradebook], str], optional): A formatting function that receives each submission and the gradebook. Defaults to str().
    """
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
    """
    Sorts and prints a list of `Submission` records using a gradebook-aware formatter.

    Args:
        submissions (Iterable[Submission]): The submissions to be sorted and displayed.
        gradebook (Gradebook): The active `Gradebook` used for context-aware formatting.
        show_index (bool, optional): If True, displays a numbered index alongside each submission. Defaults to False.
        formatter (Callable[[Submission, Gradebook], str], optional): Formats each submission with access to the gradebook. Defaults to str().
        sort_key (Callable[[Submission], Any], optional): Function used to sort submissions. Defaults to identity function.

    Notes:
        - Output is delegated to `display_submission_results()`.
    """
    sorted_submissions = sorted(submissions, key=sort_key)
    display_submission_results(sorted_submissions, gradebook, show_index, formatter)


def sort_and_display_course_dates(
    calendar_dates: set[datetime.date] | list[datetime.date],
    calendar_name: str = "Calendar View",
) -> None:
    """
    Prints a sorted list of course dates, grouped by month and labeled with a banner.

    Args:
        calendar_dates (set[datetime.date] | list[datetime.date]): The dates to display.
        calendar_name (str, optional): A custom title for the banner heading. Defaults to "Calendar View".

    Notes:
        - Dates are grouped by (month, year) and printed in ascending order.
        - Formatting is handled via `formatters.format_banner_text()`, `format_month_and_year()`, and `format_class_date_short()`.
    """
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
    """
    Displays the attendance summary for a specific class date.

    Args:
        class_date (datetime.date): The target date to summarize attendance for.
        gradebook (Gradebook): The active `Gradebook` containing attendance and student records.

    Notes:
        - If no attendance has been recorded, a message is shown.
        - If student lookups fail, those entries are skipped silently.
        - Output includes student names and their corresponding attendance status.
    """
    gradebook_response = gradebook.get_attendance_for_date(class_date)

    if not gradebook_response.success:
        display_response_failure(gradebook_response)
        print(
            f"Could not display attendance summary for {formatters.format_class_date_long(class_date)}"
        )
        return

    attendance_summary = gradebook_response.data["attendance"]

    print(f"\nAttendance summary for {formatters.format_class_date_long(class_date)}:")

    if attendance_summary == {}:
        print(
            f"Attendance has not been recorded yet for {formatters.format_class_date_short(class_date)}."
        )

    for id, attendance in attendance_summary:
        student_response = gradebook.find_student_by_uuid(id)

        student = student_response.data["record"] if student_response.success else None

        if student is not None:
            print(f"... {student.full_name:<20} | {attendance}")


# === prompt user input methods ===


# Prompt Helpers
#
# These functions provide a consistent way to handle user input and confirmation prompts.
#
# Conventions:
# - `prompt_user_input()` is the base function, used by all others to standardize the UI format.
# - Empty string responses are overloaded for control signals:
#     - `prompt_user_input_or_cancel()` returns `MenuSignal.CANCEL` on blank input.
#     - `prompt_user_input_or_default()` returns `MenuSignal.DEFAULT`.
#     - `prompt_user_input_or_none()` returns `None`.
# - `confirm_action()` and its variants loop until the user enters a valid yes/no response.
#
# These methods are intentionally concise and self-documenting. No individual docstrings are necessary.


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
) -> RecordType | None:
    """
    Prompts the user to select an item from a list of records.

    Args:
        list_data (list[RecordType]): The records to choose from.
        list_description (str): A short description used in prompts and headings (e.g. "students").
        sort_key (Callable[[RecordType], Any], optional): Sort function for ordering the list. Defaults to identity.
        formatter (Callable[[RecordType], str], optional): Function to convert each record to a display string. Defaults to str().

    Returns:
        RecordType: The selected record if a valid index is chosen.
        None: If the list is empty or the user cancels with "0".

    Notes:
        - Records are sorted before display.
        - Menu is repeated until a valid selection is made or canceled.
    """
    if not list_data:
        print(f"\nThere are no {list_description.lower()}.")
        return

    print(f"\nThere are {len(list_data)} {list_description.lower()}.")

    sorted_list = sorted(list_data, key=sort_key)

    while True:
        print(f"\n{formatters.format_banner_text(list_description)}")

        display_results(sorted_list, True, formatter)

        choice = prompt_user_input("Select an option (0 to cancel):")

        if choice == "0":
            return

        try:
            index = int(choice) - 1
            return sorted_list[index]

        except (ValueError, IndexError):
            print("\nInvalid selection. Please try again.")


def prompt_selection_from_search(
    search_results: list[RecordType],
    sort_key: Callable[[RecordType], Any] = lambda x: x,
    formatter: Callable[[RecordType], str] = lambda x: str(x),
) -> RecordType | None:
    """
    Prompts the user to select a record from a set of search results.

    Args:
        search_results (list[RecordType]): The search result records.
        sort_key (Callable[[RecordType], Any], optional): Sort function for ordering results. Defaults to identity.
        formatter (Callable[[RecordType], str], optional): Function to convert each record to a display string. Defaults to str().

    Returns:
        RecordType: The selected record, if chosen.
        None:
            - If the search returned no results.
            - If the user cancels with "0".

    Notes:
        - If a single result is found, it is returned automatically.
        - Otherwise, a numbered selection prompt is shown.
    """
    if not search_results:
        print("\nYour search returned no results.")
        return

    if len(search_results) == 1:
        return search_results[0]

    print(f"\nYour search returned {len(search_results)}:")

    sorted_results = sorted(search_results, key=sort_key)

    while True:
        display_results(sorted_results, True, formatter)

        choice = prompt_user_input("Select an option (0 to cancel):")

        if choice == "0":
            return

        try:
            index = int(choice) - 1
            return sorted_results[index]

        except (ValueError, IndexError):
            print("\nInvalid selection. Please try again.")


# --- students ---

# ---
# These functions support finding and selecting `Student` records by
# search query or active/inactive status. All return either a selected
# `Student` or `MenuSignal.CANCEL` if the user backs out or the lookup fails.
#
# Failures from the `Gradebook` are silently handled as "no results" to maintain a smooth UX.
# ---


def search_students(gradebook: Gradebook) -> list[Student]:
    query = prompt_user_input("Search for a student by name or email:").lower()

    gradebook_response = gradebook.find_student_by_query(query)

    return gradebook_response.data["records"] if gradebook_response.success else []


def prompt_student_selection_from_search(
    search_results: list[Student],
) -> Student | None:
    return prompt_selection_from_search(
        search_results,
        lambda x: (x.last_name, x.first_name),
        formatters.format_student_oneline,
    )


def prompt_student_selection_from_list(
    list_data: list[Student], list_description: str
) -> Student | None:
    return prompt_selection_from_list(
        list_data,
        list_description,
        lambda x: (x.last_name, x.first_name),
        formatters.format_student_oneline,
    )


def find_student_by_search(gradebook: Gradebook) -> Student | MenuSignal:
    """
    Prompts the user to search for and select a `Student`.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        - The selected `Student` if search and selection succeed.
        - `MenuSignal.CANCEL` if no match is found or the user cancels.

    Notes:
        - Internal search failures are treated as empty results.
    """
    search_results = search_students(gradebook)

    student = prompt_student_selection_from_search(search_results)

    return MenuSignal.CANCEL if student is None else student


def find_active_student_from_list(gradebook: Gradebook) -> Student | MenuSignal:
    """
    Prompts the user to select from active `Student` records.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        - The selected `Student`, if available.
        - `MenuSignal.CANCEL` if the list is empty, the user cancels, or the record lookup fails.

    Notes:
        - Records are sorted by last name, then first name.
    """
    gradebook_response = gradebook.get_records(
        gradebook.students, lambda x: x.is_active
    )

    active_students = (
        gradebook_response.data["records"] if gradebook_response.success else []
    )

    student = prompt_student_selection_from_list(active_students, "Active Students")

    return MenuSignal.CANCEL if student is None else student


def find_inactive_student_from_list(gradebook: Gradebook) -> Student | MenuSignal:
    """
    Prompts the user to select from inactive `Student` records.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        - The selected `Student`, if available.
        - `MenuSignal.CANCEL` if the list is empty, the user cancels, or the record lookup fails.

    Notes:
        - Records are sorted by last name, then first name.
    """
    gradebook_response = gradebook.get_records(
        gradebook.students, lambda x: not x.is_active
    )

    inactive_students = (
        gradebook_response.data["records"] if gradebook_response.success else []
    )

    student = prompt_student_selection_from_list(inactive_students, "Inactive Students")

    return MenuSignal.CANCEL if student is None else student


# --- categories ---

# ---
# These functions support finding and selecting `Category` records by
# search query or active/inactive status. All return either a selected
# `Category` or `MenuSignal.CANCEL` if the user backs out or the lookup fails.
#
# Failures from the `Gradebook` are silently handled as "no results" to maintain a smooth UX.
# ---


def search_categories(gradebook: Gradebook) -> list[Category]:
    query = prompt_user_input("Search for a category by name:").lower()

    gradebook_response = gradebook.find_category_by_query(query)

    return gradebook_response.data["records"] if gradebook_response.success else []


def prompt_category_selection_from_search(
    search_results: list[Category],
) -> Category | None:
    return prompt_selection_from_search(
        search_results, lambda x: x.name, formatters.format_category_oneline
    )


def prompt_category_selection_from_list(
    list_data: list[Category], list_description: str
) -> Category | None:
    return prompt_selection_from_list(
        list_data,
        list_description,
        lambda x: x.name,
        formatters.format_category_oneline,
    )


def find_category_by_search(gradebook: Gradebook) -> Category | MenuSignal:
    """
    Prompts the user to search for and select a `Category`.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        - The selected `Category` if search and selection succeed.
        - `MenuSignal.CANCEL` if no match is found or the user cancels.

    Notes:
        - Internal search failures are treated as empty results.
    """
    search_results = search_categories(gradebook)

    category = prompt_category_selection_from_search(search_results)

    return MenuSignal.CANCEL if category is None else category


def find_active_category_from_list(gradebook: Gradebook) -> Category | MenuSignal:
    """
    Prompts the user to select from active `Category` records.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        - The selected `Category`, if available.
        - `MenuSignal.CANCEL` if the list is empty, the user cancels, or the record lookup fails.

    Notes:
        - Records are sorted by name.
    """
    gradebook_response = gradebook.get_records(
        gradebook.categories, lambda x: x.is_active
    )

    active_categories = (
        gradebook_response.data["records"] if gradebook_response.success else []
    )

    category = prompt_category_selection_from_list(
        active_categories, "Active Categories"
    )

    return MenuSignal.CANCEL if category is None else category


def find_inactive_category_from_list(gradebook: Gradebook) -> Category | MenuSignal:
    """
    Prompts the user to select from inactive `Category` records.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        - The selected `Category`, if available.
        - `MenuSignal.CANCEL` if the list is empty, the user cancels, or the record lookup fails.

    Notes:
        - Records are sorted by name.
    """
    gradebook_response = gradebook.get_records(
        gradebook.categories, lambda x: not x.is_active
    )

    inactive_categories = (
        gradebook_response.data["records"] if gradebook_response.success else []
    )

    category = prompt_category_selection_from_list(
        inactive_categories, "Inactive Categories"
    )

    return MenuSignal.CANCEL if category is None else category


# --- assignments ---

# ---
# These functions support finding and selecting `Assignment` records by
# search query or active/inactive status. All return either a selected
# `Assignment` or `MenuSignal.CANCEL` if the user backs out or the lookup fails.
#
# Failures from the `Gradebook` are silently handled as "no results" to maintain a smooth UX.
# ---


def search_assignments(gradebook: Gradebook) -> list[Assignment]:
    query = prompt_user_input("Search for an assignment by name:").lower()

    gradebook_response = gradebook.find_assignment_by_query(query)

    return gradebook_response.data["records"] if gradebook_response.success else []


def prompt_assignment_selection_from_search(
    search_results: list[Assignment],
) -> Assignment | None:
    return prompt_selection_from_search(
        search_results, lambda x: x.name, formatters.format_assignment_oneline
    )


def prompt_assignment_selection_from_list(
    list_data: list[Assignment], list_description: str
) -> Assignment | None:
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
    Prompts the user to search for and select an `Assignment`.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        - The selected `Assignment` if search and selection succeed.
        - `MenuSignal.CANCEL` if no match is found or the user cancels.

    Notes:
        - Internal search failures are treated as empty results.
    """
    search_results = search_assignments(gradebook)

    assignment = prompt_assignment_selection_from_search(search_results)

    return MenuSignal.CANCEL if assignment is None else assignment


def find_active_assignment_from_list(
    gradebook: Gradebook,
) -> Assignment | MenuSignal:
    """
    Prompts the user to select from active `Assignment` records.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        - The selected `Assignment`, if available.
        - `MenuSignal.CANCEL` if the list is empty, the user cancels, or the record lookup fails.

    Notes:
        - Records are sorted by category first, then by due date.
    """
    gradebook_response = gradebook.get_records(
        gradebook.assignments, lambda x: x.is_active
    )

    active_assignments = (
        gradebook_response.data["records"] if gradebook_response.success else []
    )

    assignment = prompt_assignment_selection_from_list(
        active_assignments, "Active Assignments"
    )

    return MenuSignal.CANCEL if assignment is None else assignment


def find_inactive_assignment_from_list(
    gradebook: Gradebook,
) -> Assignment | MenuSignal:
    """
    Prompts the user to select from inactive `Assignment` records.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        - The selected `Assignment`, if available.
        - `MenuSignal.CANCEL` if the list is empty, the user cancels, or the record lookup fails.

    Notes:
        - Records are sorted by category first, then by due date.
    """
    gradebook_response = gradebook.get_records(
        gradebook.assignments, lambda x: not x.is_active
    )

    inactive_assignments = (
        gradebook_response.data["records"] if gradebook_response.success else []
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
    """
    Displays a formatted error message based on a failed `Response`.

    Args:
        response (Response): The response object to inspect.
        debug (bool, optional): If True, prints the trace field when present. Defaults to False.

    Notes:
        - Does nothing if the response was successful.
        - Enum error codes are printed by name; string errors are printed as-is.
    """
    if response.success:
        return

    error_label = (
        response.error.name if isinstance(response.error, Enum) else str(response.error)
    )

    print(f"\n[ERROR: {error_label}] {response.detail}")

    if debug and hasattr(response, "trace"):
        print(f"\nDebug Trace: {response.trace}")
