# cli/main.py

"""
Start Menu for the Gradebook CLI.

Provides functions for creating or loading a Gradebook.
"""

import os
from textwrap import dedent
from typing import cast

import cli.menu_helpers as helpers
import core.formatters as formatters
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

            if gradebook is not None:
                course_menu.run(gradebook)

        else:
            raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")


def create_gradebook() -> Gradebook | None:
    """
    Prompts the user to create a new `Gradebook` by collecting course name, term, and optional save directory.

    Returns:
        Gradebook: A new `Gradebook` instance if successfully created.
        None: If the user cancels during input or if `Gradebook` creation fails.

    Notes:
        - The course name and term inputs are cancellable.
        - If the save directory input is left blank, the `Gradebook` will be stored in `~/Documents/Gradebooks/<term>/<course>`, where both course and term are sanitized (spaces replaced with underscores).
        - If the resolved directory exists and is not empty, the user must explicitly confirm before continuing.
        - Filesystem operations such as directory creation and emptiness checks are handled via `cli.path_utils`.
        - Gradebook instantiation and validation are delegated to `Gradebook.create()`, which returns a structured `Response`.
    """
    while True:
        name = helpers.prompt_user_input_or_cancel(
            "Enter the course name (e.g. THTR 274A, leave blank to cancel):"
        )

        if name is MenuSignal.CANCEL:
            return None
        name = cast(str, name)

        term = helpers.prompt_user_input_or_cancel(
            "Enter the course term (e.g. FALL 2025, leave blank to cancel):"
        )

        if term is MenuSignal.CANCEL:
            return None
        term = cast(str, term)

        dir_input = helpers.prompt_user_input_or_none(
            "Enter directory to save the Gradebook (leave blank to use default):"
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

            if not helpers.confirm_action("\nDo you wish to continue?"):
                continue

        print("\nCreating Gradebook ...")

        gradebook_response = Gradebook.create(name, term, dir_path)

        if not gradebook_response.success:
            helpers.display_response_failure(gradebook_response)
            continue

        print("... Gradebook created successfully.")

        return gradebook_response.data["gradebook"]


def load_gradebook() -> Gradebook | None:
    """
    Prompts the user to load a `Gradebook` from a specified directory path.

    Returns:
        Gradebook: A `Gradebook` instance if loading succeeds.
        None: If the user cancels or if loading fails.

    Notes:
        - The directory input is cancellable.
        - Relative paths and `~` are expanded to absolute paths using `os.path.expanduser()` and `os.path.abspath()`.
        - The target path must be an existing directory; otherwise, the user will be prompted again.
        - Gradebook deserialization and validation are handled by `Gradebook.load()`, which returns a structured `Response`.
    """
    while True:
        dir_path = helpers.prompt_user_input_or_cancel(
            "Enter path to Gradebook directory (leave blank to cancel):"
        )

        if dir_path is MenuSignal.CANCEL:
            return None
        dir_path = cast(str, dir_path)

        dir_path = os.path.expanduser(dir_path)
        dir_path = os.path.abspath(dir_path)

        if not os.path.isdir(dir_path):
            print(f"\nDirectory not found: {dir_path}. Please try again.")
            continue

        print("\nLoading Gradebook ...")

        gradebook_response = Gradebook.load(dir_path)

        if not gradebook_response.success:
            helpers.display_response_failure(gradebook_response)
            continue

        print("... Gradebook loaded successfully.")

        return gradebook_response.data["gradebook"]


def exit_program():
    """
    Displays an exit banner and terminates the CLI program.

    Raises:
        SystemExit: Always raised to immediately terminate execution.

    Notes:
        - Should only be called after any necessary cleanup or save operations have been handled.
    """
    exit_banner = formatters.format_banner_text("Exiting Program")
    print(f"\n{exit_banner}\n")

    raise SystemExit


# TODO: [MVP] autocomplete dir path entry (path_utils) w/ readline and completer
# TODO: [post-MVP] recent gradebooks workflow
