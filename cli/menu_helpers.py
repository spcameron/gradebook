# cli/menu_helpers.py

from enum import Enum, auto
from typing import Any, Callable, Iterable


class MenuSignal(Enum):
    EXIT = auto()


def display_menu(
    title: str,
    options: list[tuple[str, Callable[..., Any]]],
    zero_option: str = "Return",
) -> MenuSignal | Callable[..., Any]:
    while True:
        print(f"\n{title}")
        for i, label in enumerate(options, 1):
            print(f"{i}. {label}")
        print(f"0. {zero_option}")

        choice = input("\nSelect an option: ").strip()

        if choice == "0":
            return MenuSignal.EXIT
        try:
            # slightly verbose for clarity, can be one-liner
            # return options[int(choice) - 1][1]
            index = int(choice) - 1
            option = options[index]
            action = option[1]
            return action
        except (ValueError, IndexError):
            print("Invalid selection. Please try again.")


def confirm_action(prompt: str) -> bool:
    while True:
        choice = input(f"{prompt} (y/n): ").strip().lower()

        if choice == "y" or choice == "yes":
            return True
        elif choice == "n" or choice == "no":
            return False
        else:
            print("Invalid selection. Please try again.")


# TODO
def clear_screen() -> None:
    pass


def display_results(
    results: Iterable[Any],
    show_index: bool = False,
    formatter: Callable[[Any], str] = lambda x: str(x),
) -> None:
    for i, result in enumerate(results, 1):
        prefix = f"{i:>2}. " if show_index else ""
        print(f"{prefix}{formatter(result)}")
