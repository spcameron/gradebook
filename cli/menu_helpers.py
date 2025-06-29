# cli/menu_helpers.py

from typing import Callable, Any


def display_menu(title: str, options: dict[str, Callable[[], Any]]) -> Any:
    while True:
        print(f"\n{title}")
        for i, key in enumerate(options, 1):
            print(f"{i}. {key}")
        print("0. Return")

        choice = input("\nSelect an option: ").strip()
        if choice == "0":
            return
        try:
            index = int(choice) - 1
            return list(options.values())[index]()
        except (ValueError, IndexError):
            print("Invalid selection. Please try again.")


def confirm_action(prompt: str) -> bool:
    while True:
        choice = input(f"{prompt} (y/n)").strip().lower()

        if choice == "y" or choice == "yes":
            return True
        elif choice == "n" or choice == "no":
            return False
        else:
            print("Invalid selection. Please try again.")


# TODO
def clear_screen() -> None:
    pass
