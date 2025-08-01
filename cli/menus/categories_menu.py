# cli/categories_menu.py

"""
Manage Categories menu for the Gradebook CLI.

TODO copy from student_menu.py
"""

from typing import Callable, cast

import cli.formatters as formatters
import cli.menu_helpers as helpers
import cli.menus.weights_menu as weights_menu
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

    helpers.returning_to("Manage Categories menu")


def prompt_new_category(gradebook: Gradebook) -> Category | None:
    """
    Creates a new `Category` object.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        A new `Category` object, or None.
    """
    name = prompt_name_input_or_cancel(gradebook)

    if name is MenuSignal.CANCEL:
        return None
    name = cast(str, name)

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
    print(formatters.format_category_multiline(category, gradebook))

    if helpers.confirm_action(
        "Would you like to edit this category first (change the name or mark as archived)?"
    ):
        edit_category(category, gradebook, "Category creation preview")

    if helpers.confirm_action("Would you like to create this category?"):
        return True

    else:
        print(f"Discarding category: {category.name}")
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
        user_input = helpers.prompt_user_input_or_cancel(
            "Enter category name (leave blank to cancel):"
        )

        if isinstance(user_input, MenuSignal):
            return user_input

        try:
            gradebook.require_unique_category_name(user_input)

            return user_input

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
    category = prompt_find_category(gradebook)

    if category is MenuSignal.CANCEL:
        return
    category = cast(Category, category)

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
    print(formatters.format_category_multiline(category, gradebook))

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
    new_name = prompt_name_input_or_cancel(gradebook)

    if new_name is MenuSignal.CANCEL:
        helpers.returning_without_changes()
        return
    new_name = cast(str, new_name)

    print(f"\nCurrent category name: {current_name} -> New category name: {new_name}")

    if not helpers.confirm_make_change():
        helpers.returning_without_changes()
        return

    gradebook_response = gradebook.update_category_name(category, new_name)

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        print("\nCategory name was not updated.")
        helpers.returning_without_changes()

    else:
        print(f"\n{gradebook_response.detail}")


# TODO: resume refactor from here
def edit_active_status_and_confirm(category: Category, gradebook: Gradebook) -> bool:
    """
    Toggles the is_active field of a Category via calls to confirm_and_archive() or confirm_and_reactivate().

    Args:
        category: The Category targeted for editing.
        gradebook: The active Gradebook.

    Returns:
        True if the active status was changed, and False otherwise.
    """
    print(f"\nThis category is currently {category.status}.")

    if not helpers.confirm_action("Would you like to edit the archived status?"):
        helpers.returning_without_changes()
        return False

    if category.is_active:
        return confirm_and_archive(category, gradebook)
    else:
        return confirm_and_reactivate(category, gradebook)


# === remove category ===


def find_and_remove_category(gradebook: Gradebook) -> None:
    """
    Prompts user to search for a Category and then passes the result to remove_category().

    Args:
        gradebook: The active Gradebook.
    """
    category = prompt_find_category(gradebook)

    if category is MenuSignal.CANCEL:
        return None
    else:
        category = cast(Category, category)
        remove_category(category, gradebook)


def remove_category(category: Category, gradebook: Gradebook) -> None:
    """
    Dispatch method to either delete, archive, or edit the Category, or return without changes.

    Args:
        category: The Category targeted for deletion/archiving.
        gradebook: The active Gradebook.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        Uses a function scoped variable to detect if any function calls report data manipulation.
        If so, the user is prompted to either save now or defer, in which case the Gradebook is marked dirty.
    """
    print("\nYou are viewing the following category:")
    print(formatters.format_category_oneline(category))

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

    unsaved_changes = False

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response is MenuSignal.EXIT:
        helpers.returning_without_changes()
        return None
    elif callable(menu_response):
        if menu_response(category, gradebook):
            unsaved_changes = True
    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

    if unsaved_changes:
        if helpers.confirm_unsaved_changes():
            gradebook.save(gradebook.path)
        else:
            gradebook.mark_dirty()

    helpers.returning_to("Manage Categories menu")


def confirm_and_remove(category: Category, gradebook: Gradebook) -> bool:
    """
    Deletes the Category from the Gradebook after preview and confirmation.

    Args:
        category: The Category targeted for deletion.
        gradebook: The active Gradebook.

    Returns:
        True if the Category was removed, and False otherwise.
    """
    caution_banner = formatters.format_banner_text("CAUTION!")
    print(f"\n{caution_banner}")
    print("You are about to permanently delete the following category:")
    print(formatters.format_category_multiline(category, gradebook))
    print("\nThis will also delete all linked assignments and submissions.")

    confirm_deletion = helpers.confirm_action(
        "Are you sure you want to permanently delete this category? This action cannot be undone."
    )

    if not confirm_deletion:
        helpers.returning_without_changes()
        return False

    try:
        gradebook.remove_category(category)
        print("\nCategory successfully removed from Gradebook.")
        return True
    except Exception as e:
        print(f"\nError: Could not remove submission ... {e}")
        helpers.returning_without_changes()
        return False


def confirm_and_archive(category: Category, gradebook: Gradebook) -> bool:
    """
    Toggles the is_active field of an active Category, after preview and confirmation.

    Args:
        category: The Category targeted for archiving.
        gradebook: The active Gradebook.

    Returns:
        True if the active status was changed, and False otherwise.
    """
    if not category.is_active:
        print("\nThis category has already been archived.")
        return False

    print(
        "\nArchiving a category is a safe way to deactivate a category without losing data."
    )
    print("\nYou are about to archive the following category:")
    print(formatters.format_category_multiline(category, gradebook))
    print("\nThis will preserve all linked assignments and submissions,")
    print("but they will no longer appear in reports or grade calculations.")

    confirm_archiving = helpers.confirm_action(
        "Are you sure you want to archive this category?"
    )

    if not confirm_archiving:
        helpers.returning_without_changes()
        return False

    try:
        category.toggle_archived_status()
        print(f"\nCategory status successfully updated to: {category.status}")
        return True
    except Exception as e:
        print(f"\nError: Could not update category ... {e}")
        helpers.returning_without_changes()
        return False


def confirm_and_reactivate(category: Category, gradebook: Gradebook) -> bool:
    """
    Toggles the is_active field of an inactive Category, after preview and confirmation.

    Args:
        category: The Category targeted for reactivation.
        gradebook: The active Gradebook.

    Returns:
        True if the active status was changed, and False otherwise.
    """
    if category.is_active:
        print("\nThis category is already active.")
        return False

    print("\nYou are about to reactivate the following category:")
    print(formatters.format_category_multiline(category, gradebook))

    confirm_reactivate = helpers.confirm_action(
        "Are you sure you want to reactivate this category?"
    )

    if not confirm_reactivate:
        helpers.returning_without_changes()
        return False

    try:
        category.toggle_archived_status()
        print(f"\nCategory status successfully updated to: {category.status}")
        return True
    except Exception as e:
        print(f"\nError: Could not update category ... {e}")
        helpers.returning_without_changes()
        return False


# === view category ===


def view_categories_menu(gradebook: Gradebook) -> None:
    """
    Dispatch method for the various view options (individual, active, inactive, all).

    Args:
        gradebook: The active Gradebook.

    Raises:
        RuntimeError: If the menu response is unrecognized.
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
        return None
    elif callable(menu_response):
        menu_response(gradebook)
    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")


def view_individual_category(gradebook: Gradebook) -> None:
    """
    Calls find_category() and then displays a one-line view of that Category, followed by a prompt to view the multi-line view or return.

    Args:
        gradebook: The active Gradebook.
    """
    category = prompt_find_category(gradebook)

    if category is MenuSignal.CANCEL:
        return None
    else:
        category = cast(Category, category)

    print("\nYou are viewing the following category:")
    print(formatters.format_category_oneline(category))

    if helpers.confirm_action(
        "Would you like to see an expanded view of this category?"
    ):
        print(formatters.format_category_multiline(category, gradebook))


def view_active_categories(gradebook: Gradebook) -> None:
    """
    Displays a list of active Categories.

    Args:
        gradebook: The active Gradebook.
    """
    banner = formatters.format_banner_text("Active Categories")
    print(f"\n{banner}")

    active_categories = gradebook.get_records(
        gradebook.categories, lambda x: x.is_active
    )

    if not active_categories:
        print("There are no active categories.")
        return None

    helpers.sort_and_display_records(
        records=active_categories,
        sort_key=lambda x: x.name,
        formatter=formatters.format_category_oneline,
    )


def view_inactive_categories(gradebook: Gradebook) -> None:
    """
    Displays a list of inactive Categories.

    Args:
        gradebook: The active Gradebook.
    """
    banner = formatters.format_banner_text("Inactive Categories")
    print(f"\n{banner}")

    inactive_categories = gradebook.get_records(
        gradebook.categories, lambda x: not x.is_active
    )

    if not inactive_categories:
        print("There are no inactive categories.")
        return None

    helpers.sort_and_display_records(
        records=inactive_categories,
        sort_key=lambda x: x.name,
        formatter=formatters.format_category_oneline,
    )


def view_all_categories(gradebook: Gradebook) -> None:
    """
    Displays a list of all Categories.

    Args:
        gradebook: The active Gradebook.
    """
    banner = formatters.format_banner_text("All Categories")
    print(f"\n{banner}")

    all_categories = gradebook.get_records(gradebook.categories)

    if not all_categories:
        print("There are no categories yet.")
        return None

    helpers.sort_and_display_records(
        records=all_categories,
        sort_key=lambda x: x.name,
        formatter=formatters.format_category_oneline,
    )


# === finder methods ===


def prompt_find_category(gradebook: Gradebook) -> Category | MenuSignal:
    """
    Menu dispatch for either finding a Category by search or from a list of Categories (separate lists for active and inactive).

    Args:
        gradebook: The active Gradebook.

    Returns:
        The selected Category, or MenuSignal.CANCEL if either the user cancels or the search yields no hits.

    Raises:
        RuntimeError: If the menu response is unrecognized.
    """
    title = formatters.format_banner_text("Category Selection")
    options = [
        ("Search for a category", helpers.find_category_by_search),
        ("Select from active categories", helpers.find_active_category_from_list),
        ("Select from inactive categories", helpers.find_inactive_category_from_list),
    ]
    zero_option = "Return and cancel"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response is MenuSignal.EXIT:
        return MenuSignal.CANCEL
    elif callable(menu_response):
        return menu_response(gradebook)
    else:
        raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")
