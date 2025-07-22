# cli/categories_menu.py

"""
Manage Categories menu for the Gradebook CLI.

Provides functions for adding, editing, removing, and viewing Categories.
"""

from typing import Callable, Optional, cast

import cli.formatters as formatters
import cli.menu_helpers as helpers
import cli.weights_menu as weights_menu
from cli.menu_helpers import MenuSignal
from models.category import Category
from models.gradebook import Gradebook
from utils.utils import generate_uuid


def run(gradebook: Gradebook) -> None:
    """
    Top-level loop with dispatch for the Manage Categories menu.

    Args:
        gradebook: the active Gradebook.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        The finally block guarantees a check for unsaved changes before returning.
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
    Loops a prompt to create a new Category and add to the Gradebook.

    Args:
        gradebook: the active Gradebook.

    Notes:
        New Categories are added to the Gradebook but not saved. Gradebook is marked dirty instead.
    """
    while True:
        new_category = prompt_new_category(gradebook)

        if new_category is not None and preview_and_confirm_category(
            new_category, gradebook
        ):
            gradebook.add_category(new_category)
            gradebook.mark_dirty()
            print(f"\n{new_category.name} successfully added.")

        if not helpers.confirm_action(
            "Would you like to continue adding new categories?"
        ):
            break

    helpers.returning_to("Manage Categories menu")


def prompt_new_category(gradebook: Gradebook) -> Optional[Category]:
    """
    Creates a new Category.

    Args:
        gradebook: the active Gradebook.

    Returns:
        A new Category object, or None.
    """
    name = prompt_name_input_or_cancel(gradebook)

    if name is MenuSignal.CANCEL:
        return None
    else:
        name = cast(str, name)

    try:
        category_id = generate_uuid()
        new_category = Category(
            id=category_id,
            name=name,
        )
        return new_category
    except (TypeError, ValueError) as e:
        print(f"\nError: Could not create category ... {e}")
        return None


def preview_and_confirm_category(category: Category, gradebook: Gradebook) -> bool:
    """
    Previews Category details, offers opportunity to edit details, and prompts user for confirmation.

    Args:
        category: the Category under review.
        gradebook: the active Gradebook.

    Returns:
        True if user confirm the Category details, and False otherwise.

    Notes:
        Uses edit_queued_category() since this Category has not yet been added to the Gradebook.
    """
    print("\nYou are about to create the following category:")
    print(formatters.format_category_multiline(category, gradebook))

    if helpers.confirm_action(
        "Would you like to edit this category first (change the name or mark as archived)?"
    ):
        edit_queued_category(category, gradebook)

    if helpers.confirm_action("Would you like to create this category?"):
        return True
    else:
        print("Discarding category.")
        return False


# === data input helpers ===


def prompt_name_input_or_cancel(gradebook: Gradebook) -> str | MenuSignal:
    """
    Solicits user input for Category name, validates uniqueness, and treats a blank input as 'cancel'.

    Args:
        gradebook: the active Gradebook, required for the unique-name check.

    Returns:
        User input, or MenuSignal.CANCEL if input is "".

    Notes:
        The only validation is the call to require_unique_category_name. Defensive validation against malicious input is missing.
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
            print(f"\nError: {e}")


# === edit category ===


def get_editable_fields() -> list[tuple[str, Callable[[Category, Gradebook], bool]]]:
    """
    Helper method to organize the list of editable fields and their related functions.

    Returns:
        A list of tuples - pairs of strings and function names.
    """
    return [
        ("Name", edit_name_and_confirm),
        ("Archived Status", edit_active_status_and_confirm),
    ]


def find_and_edit_category(gradebook: Gradebook) -> None:
    """
    Prompts user to search for a Category and then passes the result to edit_category().

    Args:
        gradebook: the active Gradebook.
    """
    category = prompt_find_category(gradebook)

    if category is MenuSignal.CANCEL:
        return None
    else:
        category = cast(Category, category)
        edit_category(category, gradebook)


def edit_category(category: Category, gradebook: Gradebook) -> None:
    """
    Dispatch method for selecting an editable field and using boolean return values to monitor whether changes have been made.

    Args:
        category: the Category being edited.
        gradebook: the active Gradebook.

    Raise:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        Uses a function scoped variable to flag whether the edit_* methods have manipulated the Category at all.
        If so, the user is prompted to either save changes now, or defer and mark the Gradebook dirty for saving upstream.
    """
    print("\nYou are editing the following category:")
    print(formatters.format_category_multiline(category, gradebook))

    title = formatters.format_banner_text("Editable Fields")
    options = get_editable_fields()
    zero_option = "Finish editing and return"

    unsaved_changes = False

    while True:
        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response is MenuSignal.EXIT:
            break
        elif callable(menu_response):
            if menu_response(category, gradebook):
                unsaved_changes = True
        else:
            raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

        if not helpers.confirm_action(
            "Would you like to continue editing this category?"
        ):
            break

    if unsaved_changes:
        if helpers.confirm_unsaved_changes():
            gradebook.save(gradebook.path)
        else:
            gradebook.mark_dirty()
    else:
        helpers.returning_without_changes()

    helpers.returning_to("Manage Categories menu")


def edit_queued_category(category: Category, gradebook: Gradebook) -> None:
    """
    Dispatch method for the edit menu that does not track changes, since the edited Category has not yet been added to the Gradebook.

    Args:
        category: a Category not yet added to the Gradebook and targeted for editing.
        gradebook: the active Gradebook.

    Raises:
        RuntimeError: If the menu response is unrecognized.
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

    helpers.returning_to("Category creation")


def edit_name_and_confirm(category: Category, gradebook: Gradebook) -> bool:
    """
    Edit the name field of a Category.

    Args:
        category: the Category targeted for editing.
        gradebook: the active Gradebook.

    Returns:
        True if the name was changed, and False otherwise.
    """
    current_name = category.name
    new_name = prompt_name_input_or_cancel(gradebook)

    if new_name is MenuSignal.CANCEL:
        helpers.returning_without_changes()
        return False
    else:
        new_name = cast(str, new_name)

    print(f"\nCurrent category name: {current_name} ... New category name: {new_name}")

    if not helpers.confirm_make_change():
        helpers.returning_without_changes()
        return False

    try:
        category.name = new_name
        print(f"\nName successfully updated to {category.name}.")
        return True
    except Exception as e:
        print(f"\nError: Could not update category ... {e}")
        helpers.returning_without_changes()
        return False


def edit_active_status_and_confirm(category: Category, gradebook: Gradebook) -> bool:
    """
    Toggles the is_active field of a Category via calls to confirm_and_archive() or confirm_and_reactivate().

    Args:
        category: the Category targeted for editing.
        gradebook: the active Gradebook.

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
        gradebook: the active Gradebook.
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
        category: the Category targeted for deletion/archiving.
        gradebook: the active Gradebook.

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
        category: the Category targeted for deletion.
        gradebook: the active Gradebook.

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
        category: the Category targeted for archiving.
        gradebook: the active Gradebook.

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
    Toggle the is_active field of an inactive Category, after preview and confirmation.

    Args:
        category: the Category targeted for reactivation.
        gradebook: the active Gradebook.

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
        gradebook: the active Gradebook.

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
        gradebook: the active Gradebook.
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
        gradebook: the active Gradebook.
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
        gradebook: the active Gradebook.
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
        gradebook: the active Gradebook.
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
        gradebook: the active Gradebook.

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
