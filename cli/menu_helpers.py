# cli/menu_helpers.py

import cli.formatters as formatters
from enum import Enum, auto
from models.assignment import Assignment
from models.category import Category
from models.gradebook import Gradebook
from models.student import Student
from models.types import RecordType
from typing import Any, Callable, Iterable, Optional


class MenuSignal(Enum):
    CANCEL = auto()
    DEFAULT = auto()
    EXIT = auto()


def confirm_action(prompt: str) -> bool:
    while True:
        choice = prompt_user_input(f"{prompt} (y/n): ").lower()

        if choice == "y" or choice == "yes":
            return True
        elif choice == "n" or choice == "no":
            return False
        else:
            print("Invalid selection. Please try again.")


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


def prompt_user_input(prompt: str) -> str:
    return input(f"\n{prompt}\n  >> ").strip()


def prompt_user_input_or_cancel(prompt: str) -> str | MenuSignal:
    response = input(f"\n{prompt}\n  >> ").strip()
    return MenuSignal.CANCEL if response == "" else response


def prompt_user_input_or_default(prompt: str) -> str | MenuSignal:
    response = input(f"\n{prompt}\n  >> ").strip()
    return MenuSignal.DEFAULT if response == "" else response


def prompt_user_input_or_none(prompt: str) -> str | None:
    response = input(f"\n{prompt}\n  >> ").strip()
    return None if response == "" else response


def returning_without_changes() -> None:
    print("\nReturning without changes.")


# === search and select methods ===


def prompt_record_selection(
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


def prompt_student_selection(search_results: list[Student]) -> Optional[Student]:
    return prompt_record_selection(
        search_results,
        lambda x: (x.last_name, x.first_name),
        formatters.format_student_oneline,
    )


def search_categories(gradebook: Gradebook) -> list[Category]:
    query = prompt_user_input("Search for a category by name:").lower()
    return gradebook.find_category_by_query(query)


def prompt_category_selection(search_results: list[Category]) -> Optional[Category]:
    return prompt_record_selection(
        search_results, lambda x: x.name, formatters.format_category_oneline
    )


def search_assignments(gradebook: Gradebook) -> list[Assignment]:
    query = prompt_user_input("Search for an assignment by name:").lower()
    return gradebook.find_assignment_by_query(query)


def prompt_assignment_selection(
    search_results: list[Assignment],
) -> Optional[Assignment]:
    # TODO: add formmatter when it's written
    return prompt_record_selection(search_results, lambda x: x.name)
