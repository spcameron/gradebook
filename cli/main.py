# cli/main.py

import os
import json
from cli.menu_helpers import display_menu, confirm_action
from models.gradebook import Gradebook
from cli.path_utils import resolve_save_dir, dir_is_empty


def run_cli():
    title = "===== GRADEBOOK APP ====="
    options = {
        "Create a new Gradebook": lambda: create_gradebook(),
        "Load an existing Gradebook": lambda: load_gradebook(),
        "Exit Program": lambda: exit_program(),
    }

    gradebook = display_menu(title, options)


def create_gradebook() -> Gradebook:
    while True:
        name = input("Enter the course name (e.g. THTR 274A): ")
        term = input("Enter the course term (e.g. FALL 2025): ")
        dir_input = (
            input(
                "Enter directory to save the Gradebook (leave blank to use default): "
            )
            or None
        )

        dir_path = resolve_save_dir(name, term, dir_input)

        if os.path.exists(dir_path) and not dir_is_empty(dir_path):
            print(
                """=== WARNING! ===
            The selected directory is not empty and may contain existing data.
            It is recommended to store new Gradebooks in an empty directory.
            Writing to this directory may result in the loss of existing data."""
            )
            if confirm_action("Do you wish to continue?"):
                return Gradebook.create(name, term, dir_path)
            else:
                continue

        return Gradebook.create(name, term, dir_path)


# TODO verify gradebook data (or at least metadata) exists before loading
def load_gradebook() -> Gradebook | None:
    dir_path = input("Enter path to Gradebook directory: ").strip()
    dir_path = os.path.expanduser(dir_path)
    dir_path = os.path.abspath(dir_path)

    if not os.path.isdir(dir_path):
        print("Error: No directory found at that path.")
        return None

    try:
        return Gradebook.load(dir_path)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Failed to load Gradebook: {e}")
        return None


def exit_program():
    print("Exiting program.")
    raise SystemExit
