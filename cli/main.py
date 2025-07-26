# cli/main.py

"""
Start Menu for the Gradebook CLI.

Provides functions for creating or loading a Gradebook.
"""

import json
import os
from textwrap import dedent
from typing import Optional

import cli.formatters as formatters
import cli.menu_helpers as helpers
from cli.menu_helpers import MenuSignal
from cli.menus import course_menu
from cli.path_utils import dir_is_empty, resolve_save_dir
from models.gradebook import Gradebook


def run_cli() -> None:
    """
    Top-level loop with dispatch for the Start menu.

    Raises:
        RuntimeError: If the menu response is unrecognized.
    """
    title = formatters.format_banner_text("GRADEBOOK MANAGER")
    options = [
        ("Create a new Gradebook", create_gradebook),
        ("Load an existing Gradebook", load_gradebook),
    ]
    zero_option = "Exit Program"

    while True:
        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response is MenuSignal.EXIT:
            exit_program()
        elif callable(menu_response):
            gradebook = menu_response()
            course_menu.run(gradebook)


# TODO: needs review and doc
def create_gradebook() -> Gradebook:
    while True:
        name = helpers.prompt_user_input("Enter the course name (e.g. THTR 274A):")
        term = helpers.prompt_user_input("Enter the course term (e.g. FALL 2025):")
        dir_input = (
            helpers.prompt_user_input(
                "Enter directory to save the Gradebook (leave blank to use default):"
            )
            or None
        )

        dir_path = resolve_save_dir(name, term, dir_input)

        if os.path.exists(dir_path) and not dir_is_empty(dir_path):
            warning_banner = formatters.format_banner_text("WARNING!")
            print(f"\n{warning_banner}")
            print(
                dedent(
                    """\
                    The selected directory is not empty and may contain existing data.
                    It is recommended to store new Gradebooks in an empty directory.
                    Writing to this directory may result in the loss of existing data."""
                )
            )
            if helpers.confirm_action("\nDo you wish to continue?"):
                return Gradebook.create(name, term, dir_path)
            else:
                continue

        return Gradebook.create(name, term, dir_path)


# TODO: verify gradebook data (or at least metadata) exists before loading
# TODO: needs review and doc
def load_gradebook() -> Optional[Gradebook]:
    dir_path = helpers.prompt_user_input("Enter path to Gradebook directory:")
    dir_path = os.path.expanduser(dir_path)
    dir_path = os.path.abspath(dir_path)

    if not os.path.isdir(dir_path):
        print("\nError: No directory found at that path.")
        return None

    try:
        return Gradebook.load(dir_path)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"\nError: Failed to load Gradebook: {e}")
        return None


# TODO: needs review and doc
def exit_program():
    exit_banner = formatters.format_banner_text("Exiting Program")
    print(f"\n{exit_banner}\n")
    raise SystemExit
