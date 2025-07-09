# cli/main.py

import os
import json
from cli import course_menu
from cli.menu_helpers import (
    confirm_action,
    display_menu,
    format_banner_text,
    prompt_user_input,
    MenuSignal,
)
from cli.path_utils import resolve_save_dir, dir_is_empty
from models.gradebook import Gradebook
from textwrap import dedent
from typing import Optional


def run_cli() -> None:
    title = format_banner_text("GRADEBOOK MANAGER")
    options = [
        ("Create a new Gradebook", lambda: create_gradebook()),
        ("Load an existing Gradebook", lambda: load_gradebook()),
    ]
    zero_option = "Exit Program"

    while True:
        menu_response = display_menu(title, options, zero_option)

        if menu_response == MenuSignal.EXIT:
            exit_program()

        if callable(menu_response):
            gradebook = menu_response()
            course_menu.run(gradebook)


def create_gradebook() -> Gradebook:
    while True:
        name = prompt_user_input("Enter the course name (e.g. THTR 274A):")
        term = prompt_user_input("Enter the course term (e.g. FALL 2025):")
        dir_input = (
            prompt_user_input(
                "Enter directory to save the Gradebook (leave blank to use default):"
            )
            or None
        )

        dir_path = resolve_save_dir(name, term, dir_input)

        if os.path.exists(dir_path) and not dir_is_empty(dir_path):
            warning_banner = format_banner_text("WARNING!")
            print(f"\n{warning_banner}")
            print(
                dedent(
                    """\
                    The selected directory is not empty and may contain existing data.
                    It is recommended to store new Gradebooks in an empty directory.
                    Writing to this directory may result in the loss of existing data."""
                )
            )
            if confirm_action("\nDo you wish to continue?"):
                return Gradebook.create(name, term, dir_path)
            else:
                continue

        return Gradebook.create(name, term, dir_path)


# TODO: verify gradebook data (or at least metadata) exists before loading
def load_gradebook() -> Optional[Gradebook]:
    dir_path = prompt_user_input("Enter path to Gradebook directory:")
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


def exit_program():
    exit_banner = format_banner_text("Exiting Program")
    print(f"\n{exit_banner}\n")
    raise SystemExit
