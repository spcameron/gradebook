# cli/menu_helpers.py

import cli.formatters as formatters
from enum import Enum, auto
from models.assignment import Assignment
from models.category import Category
from models.gradebook import Gradebook
from models.student import Student
from models.submission import Submission
from models.types import RecordType
from typing import Any, Callable, Iterable, Optional


class MenuSignal(Enum):
    CANCEL = auto()
    DEFAULT = auto()
    EXIT = auto()


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
    formatter: Callable[[Submission, Gradebook], str] = lambda s, g: str(s),
) -> None:
    for i, result in enumerate(results, 1):
        prefix = f"{i:>2}. " if show_index else ""
        print(f"{prefix}{formatter(result, gradebook)}")


def sort_and_display_submissions(
    submissions: Iterable[Submission],
    gradebook: Gradebook,
    show_index: bool = False,
    formatter: Callable[[Submission, Gradebook], str] = lambda s, g: str(s),
    sort_key: Callable[[Submission], Any] = lambda x: x,
) -> None:
    sorted_submissions = sorted(submissions, key=sort_key)
    display_submission_results(sorted_submissions, gradebook, show_index, formatter)


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


def confirm_save_change() -> bool:
    return confirm_action("Do you want to save this change?")


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


# === search and select methods ===


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


def get_assignment_and_student(
    submission: Submission, gradebook: Gradebook
) -> tuple[Assignment, Student]:
    linked_assignment = gradebook.find_assignment_by_uuid(submission.assignment_id)
    linked_student = gradebook.find_student_by_uuid(submission.student_id)

    if linked_assignment is None:
        raise KeyError("No linked assignment could be found.")

    if linked_student is None:
        raise KeyError("No linked student could be found.")

    return (linked_assignment, linked_student)


# === often used messages ===


def returning_without_changes() -> None:
    print("\nReturning without changes.")
