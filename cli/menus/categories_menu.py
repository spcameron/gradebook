# cli/categories_menu.py

"""
Manage Categories menu for the Gradebook CLI.

This module defines the full interface for managing `Category` records, including:
- Adding new categories
- Editing category attributes (name, archival status)
- Archiving or permanently removing categories
- Viewing category records (individual, filtered, or all)

All operations are routed through the `Gradebook` API for consistency, validation, and state tracking.
Control flow adheres to structured CLI menu patterns with clear terminal-level feedback.
"""

from collections.abc import Callable
from typing import cast

import cli.menu_helpers as helpers
import cli.menus.weights_menu as weights_menu
import cli.model_formatters as model_formatters
import core.formatters as formatters
from cli.menu_helpers import MenuSignal
from core.utils import generate_uuid
from models.category import Category
from models.gradebook import Gradebook


def run(gradebook: Gradebook) -> None:
    """
    Top-level loop with dispatch for the Manage Categories menu.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        - The finally block guarantees a check for unsaved changes before returning.
    """
    title = formatters.format_banner_text("Manage Categories")
    options = [
        ("Add Category", add_category),
        ("Edit Category", find_and_edit_category),
        ("Remove Category", find_and_remove_category),
        ("View Categories", view_categories_menu),
        ("Manage Category Weights", weights_menu.run),
    ]
    zero_option = "Return to Course Manager menu"

    try:
        while True:
            menu_response = helpers.display_menu(title, options, zero_option)

            if menu_response is MenuSignal.EXIT:
                break
            elif callable(menu_response):
                menu_response(gradebook)
            else:
                raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

    finally:
        helpers.prompt_if_dirty(gradebook)

    helpers.returning_to("Course Manager menu")


# === add category ===


def add_category(gradebook: Gradebook) -> None:
    """
    Loops a prompt to create a new `Category` object and add it to the gradebook.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Additions are not saved automatically. If the gradebook is marked dirty after adding, the user will be prompted to save before returning to the previous menu.
    """
    while True:
        new_category = prompt_new_category(gradebook)

        if new_category is not None and preview_and_confirm_category(
            new_category, gradebook
        ):
            gradebook_response = gradebook.add_category(new_category)

            if not gradebook_response.success:
                helpers.display_response_failure(gradebook_response)
                print(f"\n{new_category.name} was not added.")
            else:
                print(f"\n{gradebook_response.detail}")

        if not helpers.confirm_action(
            "Would you like to continue adding new categories?"
        ):
            break

    helpers.prompt_if_dirty(gradebook)
    helpers.returning_to("Manage Categories menu")


def prompt_new_category(gradebook: Gradebook) -> Category | None:
    """
    Creates a new `Category` object.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        A new `Category` object, or None.
    """
    name_input = prompt_name_input_or_cancel(gradebook)

    if name_input is MenuSignal.CANCEL:
        return None

    name = cast(str, name_input)

    try:
        return Category(
            id=generate_uuid(),
            name=name,
        )

    except (TypeError, ValueError) as e:
        print(f"\n[ERROR] Could not create category: {e}")
        return None


def preview_and_confirm_category(category: Category, gradebook: Gradebook) -> bool:
    """
    Previews new `Category` details, offers opportunity to edit details, and prompts user for confirmation.

    Args:
        category (Category): The `Category` object under review.
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        True if user confirms the `Category` details, and False otherwise.
    """
    print("\nYou are about to create the following category:")
    print(model_formatters.format_category_multiline(category, gradebook))

    if helpers.confirm_action(
        "Would you like to edit this category first (change the name or mark as archived)?"
    ):
        edit_category(category, gradebook, "Category creation preview")

    if helpers.confirm_action("Would you like to create this category?"):
        return True
    else:
        print(f"\nDiscarding category: {category.name}")
        return False


# === data input helpers ===


def prompt_name_input_or_cancel(gradebook: Gradebook) -> str | MenuSignal:
    """
    Solicits user input for category name, validates uniqueness, and treats a blank input as 'cancel'.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        User input unmodified, or `MenuSignal.CANCEL` if input is "".

    Notes:
        - The only validation is the call to `require_unique_category_name()`. Defensive validation against malicious input is missing.
    """
    while True:
        name_input = helpers.prompt_user_input_or_cancel(
            "Enter category name (leave blank to cancel):"
        )

        if isinstance(name_input, MenuSignal):
            return name_input

        try:
            gradebook.require_unique_category_name(name_input)
            return name_input

        except ValueError as e:
            print(f"\n[ERROR] {e}")
            print("Please try again.")


# === edit category ===


def get_editable_fields() -> list[tuple[str, Callable[[Category, Gradebook], None]]]:
    """
    Helper method to organize the list of editable fields and their related functions.

    Returns:
        A list of `(field_name, edit_function)` tuples used to prompt and edit `Category` attributes.
    """
    return [
        ("Name", edit_name_and_confirm),
        ("Archived Status", edit_active_status_and_confirm),
    ]


def find_and_edit_category(gradebook: Gradebook) -> None:
    """
    Prompts user to search for a `Category` and then passes the result to `edit_category()`.

    Args:
        gradebook (Gradebook): The active `Gradebook`.
    """
    category_input = prompt_find_category(gradebook)

    if category_input is MenuSignal.CANCEL:
        return

    category = cast(Category, category_input)

    edit_category(category, gradebook)


def edit_category(
    category: Category,
    gradebook: Gradebook,
    return_context: str = "Manage Categories menu",
) -> None:
    """
    Interface for editing fields of a `Category` record.

    Args:
        category (Category): The `Category` object being edited.
        gradebook (Gradebook): The active `Gradebook`.
        return_context (str): An optional description of the call site, uses "Manage Categories menu" by default.

    Raise:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        - All edit operations are dispatched through `Gradebook` to ensure proper mutation and state tracking.
        - Changes are not saved automatically. If the gradebook is marked dirty after edits, the user will be prompted to save before returning to the previous menu.
        - The `return_context` label is used to display a confirmation message when exiting the edit menu.
    """
    print("\nYou are editing the following category:")
    print(model_formatters.format_category_multiline(category, gradebook))

    title = formatters.format_banner_text("Editable Fields")
    options = get_editable_fields()
    zero_option = "Finish editing and return"

    while True:
        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response is MenuSignal.EXIT:
            break
        elif callable(menu_response):
            menu_response(category, gradebook)
        else:
            raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

        if not helpers.confirm_action(
            "Would you like to continue editing this category?"
        ):
            break

    if gradebook.has_unsaved_changes:
        helpers.prompt_if_dirty(gradebook)
    else:
        helpers.returning_without_changes()

    helpers.returning_to(return_context)


def edit_name_and_confirm(category: Category, gradebook: Gradebook) -> None:
    """
    Prompts for a new name and updates the `Category` record via `Gradebook`.

    Args:
        category (Category): The `Category` object targeted for editing.
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Cancels early if the user enters nothing or declines the confirmation.
        - Uses `Gradebook.update_category_name()` to perform the update and track changes.
    """
    current_name = category.name
    name_input = prompt_name_input_or_cancel(gradebook)

    if name_input is MenuSignal.CANCEL:
        helpers.returning_without_changes()
        return

    new_name = cast(str, name_input)

    print(f"\nCurrent category name: {current_name} -> New category name: {new_name}")

    if not helpers.confirm_make_change():
        helpers.returning_without_changes()
        return

    gradebook_response = gradebook.update_category_name(category, new_name)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print("\nCategory name was not updated.")
        helpers.returning_without_changes()
        return

    print(f"\n{gradebook_response.detail}")


def edit_active_status_and_confirm(category: Category, gradebook: Gradebook) -> None:
    """
    Toggles the `is_active` field of a `Category` record via calls to `confirm_and_archive()` or `confirm_and_reactivate()`.

    Args:
        category (Category): The `Category` object targeted for editing.
        gradebook (Gradebook): The active `Gradebook`.
    """
    print(f"\nThis category is currently {category.status}.")

    if not helpers.confirm_action("Would you like to edit the archived status?"):
        helpers.returning_without_changes()
        return

    if category.is_active:
        confirm_and_archive(category, gradebook)
    else:
        confirm_and_reactivate(category, gradebook)


# === remove category ===


def find_and_remove_category(gradebook: Gradebook) -> None:
    """
    Prompts user to search for a `Category` and then passes the result to `remove_category()`.

    Args:
        gradebook (Gradebook): The active `Gradebook`.
    """
    category_input = prompt_find_category(gradebook)

    if category_input is MenuSignal.CANCEL:
        return

    category = cast(Category, category_input)

    remove_category(category, gradebook)


def remove_category(category: Category, gradebook: Gradebook) -> None:
    """
    Interface for removing, archiving, or editing a `Category` record.

    Args:
        category (Category): The `Category` object targeted for deletion/archiving.
        gradebook (Gradebook): The active `Gradebook`.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        - All remove and edit operations are dispatched through `Gradebook` to ensure proper mutation and state tracking.
        - Changes are not saved automatically. If the gradebook is marked dirty, the user will be prompted to save before returning to the previous menu.
    """
    print("\nYou are viewing the following category:")
    print(model_formatters.format_category_oneline(category))

    title = "What would you like to do?"
    options = [
        (
            "Remove this category (permanently delete the category and all linked assignments and submissions)",
            confirm_and_remove,
        ),
        (
            "Archive this category (preserve all linked assignments and submissions)",
            confirm_and_archive,
        ),
        (
            "Edit this category instead",
            edit_category,
        ),
    ]
    zero_option = "Return to Manage Categories menu"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response is MenuSignal.EXIT:
        helpers.returning_without_changes()
        return
    elif callable(menu_response):
        menu_response(category, gradebook)
    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

    if gradebook.has_unsaved_changes:
        helpers.prompt_if_dirty(gradebook)
    else:
        helpers.returning_without_changes()

    helpers.returning_to("Manage Categories menu")


def confirm_and_remove(category: Category, gradebook: Gradebook) -> None:
    """
    Deletes the `Category` record and all linked `Assignments` and `Submissions` from the `Gradebook` after preview and user confirmation.

    Args:
        category (Category): The `Category` object targeted for deletion.
        gradebook (Gradebook): The active `Gradebook`.
    """
    helpers.caution_banner()
    print("You are about to permanently delete the following category:")
    print(model_formatters.format_category_multiline(category, gradebook))
    print("\nThis will also delete all linked assignments and submissions.")

    confirm_deletion = helpers.confirm_action(
        "Are you sure you want to permanently delete this category? This action cannot be undone."
    )

    if not confirm_deletion:
        helpers.returning_without_changes()
        return

    gradebook_response = gradebook.remove_category(category)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print("\nCategory was not removed.")
        helpers.returning_without_changes()
        return

    print(f"\n{gradebook_response.detail}")


def confirm_and_archive(category: Category, gradebook: Gradebook) -> None:
    """
    Archives an active `Category` after preview and confirmation.

    Args:
        category (Category): The `Category` object targeted for archiving.
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Archiving preserves all linked `Assignment` and `Submission` records but excludes the category from reports and calculations.
        - If the `Category` is already archived, the method exits early.
    """
    if not category.is_active:
        print("\nThis category has already been archived.")
        return

    print(
        "\nArchiving a category is a safe way to deactivate a category without losing data."
    )
    print("\nYou are about to archive the following category:")
    print(model_formatters.format_category_multiline(category, gradebook))
    print("\nThis will preserve all linked assignments and submissions,")
    print("but they will no longer appear in reports or grade calculations.")

    confirm_archiving = helpers.confirm_action(
        "Are you sure you want to archive this category?"
    )

    if not confirm_archiving:
        helpers.returning_without_changes()
        return

    gradebook_response = gradebook.toggle_category_active_status(category)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print("\nCategory status was not changed.")
        helpers.returning_without_changes()
        return

    print(f"\n{gradebook_response.detail}")


def confirm_and_reactivate(category: Category, gradebook: Gradebook) -> None:
    """
    Reactivates an inactive `Category` after preview and confirmation.

    Args:
        category (Category): The `Category` object targeted for reactivation.
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - If the `Category` is already active, the method exits early.
    """
    if category.is_active:
        print("\nThis category is already active.")
        return

    print("\nYou are about to reactivate the following category:")
    print(model_formatters.format_category_multiline(category, gradebook))

    confirm_reactivate = helpers.confirm_action(
        "Are you sure you want to reactivate this category?"
    )

    if not confirm_reactivate:
        helpers.returning_without_changes()
        return

    gradebook_response = gradebook.toggle_category_active_status(category)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print("\nCategory status was not changed.")
        helpers.returning_without_changes()
        return

    print(f"\n{gradebook_response.detail}")


# === view category ===


def view_categories_menu(gradebook: Gradebook) -> None:
    """
    Displays the category view menu and dispatches selected view options.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        - Options include viewing individual, active, inactive, or all categories.
    """
    title = "View Categories"
    options = [
        ("View Individual Category", view_individual_category),
        ("View Active Categories", view_active_categories),
        ("View Inactive Categories", view_inactive_categories),
        ("View All Categories", view_all_categories),
    ]
    zero_option = "Return to Manage Categories menu"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response is MenuSignal.EXIT:
        return
    elif callable(menu_response):
        menu_response(gradebook)
    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

    helpers.returning_to("Manage Categories menu")


def view_individual_category(gradebook: Gradebook) -> None:
    """
    Display a one-line summary of a selected `Category` record, with the option to view full details.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Uses `prompt_find_category()` to search for a record.
        - Prompts the user before displaying the multi-line format.
    """
    category_input = prompt_find_category(gradebook)

    if category_input is MenuSignal.CANCEL:
        return

    category = cast(Category, category_input)

    print("\nYou are viewing the following category:")
    print(model_formatters.format_category_oneline(category))

    if helpers.confirm_action(
        "Would you like to see an expanded view of this category?"
    ):
        print(model_formatters.format_category_multiline(category, gradebook))


def view_active_categories(gradebook: Gradebook) -> None:
    """
    Displays a sorted list of active `Category` records.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Uses `Gradebook.get_records()` with a filter for active categories.
        - Records are sorted by name.
    """
    banner = formatters.format_banner_text("Active Categories")
    print(f"\n{banner}")

    gradebook_response = gradebook.get_records(
        gradebook.categories, lambda x: x.is_active
    )

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        return

    active_categories = gradebook_response.data["records"]

    if not active_categories:
        print("There are no active categories.")
        return

    helpers.sort_and_display_records(
        records=active_categories,
        sort_key=lambda x: x.name,
        formatter=model_formatters.format_category_oneline,
    )


def view_inactive_categories(gradebook: Gradebook) -> None:
    """
    Displays a sorted list of inactive `Category` records.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Uses `Gradebook.get_records()` with a filter for inactive students.
        - Records are sorted by name.
    """
    banner = formatters.format_banner_text("Inactive Categories")
    print(f"\n{banner}")

    gradebook_response = gradebook.get_records(
        gradebook.categories, lambda x: not x.is_active
    )

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        return

    inactive_categories = gradebook_response.data["records"]

    if not inactive_categories:
        print("There are no inactive categories.")
        return

    helpers.sort_and_display_records(
        records=inactive_categories,
        sort_key=lambda x: x.name,
        formatter=model_formatters.format_category_oneline,
    )


def view_all_categories(gradebook: Gradebook) -> None:
    """
    Displays a list of all `Category` records.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - Uses `Gradebook.get_records()` to retrieve all categories, active and inactive.
        - Records are sorted by name.
    """
    banner = formatters.format_banner_text("All Categories")
    print(f"\n{banner}")

    gradebook_response = gradebook.get_records(gradebook.categories)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        return

    all_categories = gradebook_response.data["records"]

    if not all_categories:
        print("There are no categories yet.")
        return

    helpers.sort_and_display_records(
        records=all_categories,
        sort_key=lambda x: x.name,
        formatter=model_formatters.format_category_oneline,
    )


# === finder methods ===


def prompt_find_category(gradebook: Gradebook) -> Category | MenuSignal:
    """
    Prompts the user to locate a `Category` record by search or list selection.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        Category | MenuSignal: The selected `Category`, or `MenuSignal.CANCEL` if canceled or no matches are found.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        - Offers search, active list, and inactive list as selection methods.
        - Returns early if the user chooses to cancel or if no selection is made.
    """
    title = formatters.format_banner_text("Category Selection")
    options = [
        ("Search for a category", helpers.find_category_by_search),
        ("Select from active categories", helpers.find_active_category_from_list),
        ("Select from inactive categories", helpers.find_inactive_category_from_list),
    ]
    zero_option = "Return and cancel"

    while True:
        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response is MenuSignal.EXIT:
            return MenuSignal.CANCEL

        elif callable(menu_response):
            category = menu_response(gradebook)

            if category is MenuSignal.CANCEL:
                print("\nCategory selection canceled.")

                if not helpers.confirm_action("Would you like to try again?"):
                    return MenuSignal.CANCEL
                else:
                    continue

            return category

        else:
            raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")
