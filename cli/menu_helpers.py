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


def confirm_action(prompt: str) -> bool:
    while True:
        choice = prompt_user_input(f"{prompt} (y/n): ").lower()

        if choice == "y" or choice == "yes":
            return True
        elif choice == "n" or choice == "no":
            return False
        else:
            print("Invalid selection. Please try again.")


def display_results(
    results: Iterable[Any],
    show_index: bool = False,
    formatter: Callable[[Any], str] = lambda x: str(x),
) -> None:
    for i, result in enumerate(results, 1):
        prefix = f"{i:>2}. " if show_index else ""
        print(f"{prefix}{formatter(result)}")


def format_banner_text(title: str, width: int = 40) -> str:
    line = "=" * width
    centered_title = f"{title:^{width}}"
    return f"{line}\n{centered_title}\n{line}"


def prompt_user_input(prompt: str) -> str:
    return input(f"\n{prompt}\n  >> ").strip()
