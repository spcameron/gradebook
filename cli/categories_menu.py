# cli/categories_menu.py

import cli.formatters as formatters
import cli.menu_helpers as helpers
import cli.weights_menu as weights_menu
from cli.menu_helpers import MenuSignal
from models.category import Category
from models.gradebook import Gradebook
from typing import cast, Callable, Optional
from utils.utils import generate_uuid


def run(gradebook: Gradebook) -> None:
    title = formatters.format_banner_text("Manage Categories")
    options = [
        ("Add Category", add_category),
        ("Edit Category", edit_category),
        ("Remove Category", remove_category),
        ("View Categories", view_categories_menu),
        ("Manage Category Weights", weights_menu.run),
    ]
    zero_option = "Return to Course Manager menu"

    while True:
        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response == MenuSignal.EXIT:
            if helpers.confirm_action("Would you like to save before returning?"):
                gradebook.save(gradebook.path)
            return None

        if callable(menu_response):
            menu_response(gradebook)


# === add category ===


def add_category(gradebook: Gradebook) -> None:
    while True:
        new_category = prompt_new_category()

        if new_category is not None:
            gradebook.add_category(new_category)
            print(f"\n{new_category.name} successfully added to {gradebook.name}.")

        if not helpers.confirm_action(
            "Would you like to continue adding new categories?"
        ):
            print(f"\nReturning to Manage Categories menu.")
            return None


def prompt_new_category() -> Optional[Category]:
    # collect user input
    name = helpers.prompt_user_input_or_cancel(
        "Enter category name (leave blank to cancel):"
    )
    if name == MenuSignal.CANCEL:
        return None
    else:
        name = cast(str, name)

    # preview and confirm
    print("\nYou are about to create the following category:")
    print(f"... Name: {name}")

    if not helpers.confirm_action("\nConfirm creation?"):
        return None

    # attempt object instantiation
    try:
        category_id = generate_uuid()
        new_category = Category(
            id=category_id,
            name=name,
        )
    except (TypeError, ValueError) as e:
        print(f"\nError: Could not create category ... {e}")
        return None

    return new_category


# === edit category ===


def get_editable_fields() -> (
    list[tuple[str, Callable[[Category, Gradebook], Optional[MenuSignal]]]]
):
    return [
        ("Name", edit_name_and_confirm),
        ("Archived Status", edit_status_and_confirm),
    ]


def edit_category(gradebook: Gradebook) -> None:
    search_results = helpers.search_categories(gradebook)
    category = helpers.prompt_category_selection(search_results)

    if not category:
        return None

    title = formatters.format_banner_text("Editable Fields")
    options = get_editable_fields()
    zero_option = "Return without changes"

    while True:
        print("\nYou are viewing the following category:")
        print(formatters.format_category_oneline(category))

        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response == MenuSignal.EXIT:
            helpers.returning_without_changes()
            return None

        if callable(menu_response):
            menu_response(category, gradebook)

        if not helpers.confirm_action(
            "Would you like to continue editing this category?"
        ):
            print("\nReturning to Manage Categories menu.")
            return None


def edit_name_and_confirm(category: Category, gradebook: Gradebook) -> None:
    current_name = category.name
    new_name = helpers.prompt_user_input("Enter a new name (leave blank to cancel):")

    if new_name == "":
        helpers.returning_without_changes()
        return None

    print(f"\nCurrent category name: {current_name} ... New category name: {new_name}")

    save_change = helpers.confirm_action("Do you want to save this change?")

    if not save_change:
        helpers.returning_without_changes()
        return None

    category.name = new_name
    gradebook.save(gradebook.path)
    print("\nName successfully updated.")


def edit_status_and_confirm(category: Category, gradebook: Gradebook) -> None:
    print(f"\nThis category is currently {category.status}.")

    if not helpers.confirm_action("Would you like to edit the archived status?"):
        helpers.returning_without_changes()
        return None

    if category.is_active:
        confirm_and_archive(category, gradebook)
    else:
        confirm_and_reactivate(category, gradebook)


# === remove category ===


def remove_category(gradebook: Gradebook) -> None:
    search_results = helpers.search_categories(gradebook)
    category = helpers.prompt_category_selection(search_results)

    if not category:
        return None

    print("\nYou are viewing the following category:")
    print(formatters.format_category_oneline(category))

    title = "What would you like to do?"
    options = [
        (
            "Permanently remove this category (deletes all linked assignments and submissions)",
            confirm_and_remove,
        ),
        (
            "Archive category instead (preserves all linked assignments and submissions)",
            confirm_and_archive,
        ),
    ]
    zero_option = "Return to Manage Categories menu"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response == MenuSignal.EXIT:
        helpers.returning_without_changes()
        return None

    if callable(menu_response):
        menu_response(category, gradebook)


def confirm_and_remove(category: Category, gradebook: Gradebook) -> None:
    caution_banner = formatters.format_banner_text("CAUTION!")
    print(f"\n{caution_banner}")
    print("You are about to permanently delete the following category:")
    print(f"{category.name}")
    print(f"\nThis will also delete all linked assignments and submissions.")

    confirm_deletion = helpers.confirm_action(
        "Are you sure you want to permanently remove this category? This action cannot be undone."
    )

    if not confirm_deletion:
        helpers.returning_without_changes()
        return None

    gradebook.remove_category(category)
    gradebook.save(gradebook.path)
    print("\nCategory successfully removed from Gradebook.")


def confirm_and_archive(category: Category, gradebook: Gradebook) -> None:
    print(
        f"\nArchiving a category is safe way to deactivate a category without losing data."
    )
    print("You are about to archive the following category:")
    print(f"{category.name}")
    print(
        f"\nThis will preserve all linked assignments and submissions,\nbut they will no longer appear in reports or grade calculation."
    )

    confirm_archiving = helpers.confirm_action(
        "Are you sure you want to archive this category and all linked assignments and submissions?"
    )

    if not confirm_archiving:
        helpers.returning_without_changes()
        return None

    category.toggle_archived_status()
    gradebook.save(gradebook.path)
    print(f"\nCategory successfully archived.")


def confirm_and_reactivate(category: Category, gradebook: Gradebook) -> None:
    print(
        f"\nReactivating a category will also restore any linked assignments and submissions."
    )
    print("You are about to reactivate the following category:")
    print(f"{category.name}")

    confirm_reactivate = helpers.confirm_action(
        "Are you sure you want to reactivate this category and all linked assignments and submissions?"
    )

    if not confirm_reactivate:
        helpers.returning_without_changes()
        return None

    category.toggle_archived_status()
    gradebook.save(gradebook.path)
    print(f"\nCategory successfully reactivated.")


# === view category ===


def view_categories_menu(gradebook: Gradebook) -> None:
    title = "View Categories"
    options = [
        ("View Individual Category", view_individual_category),
        ("View Active Categories", view_active_categories),
        ("View Inactive Categories", view_inactive_categories),
        ("View All Categories", view_all_categories),
    ]
    zero_option = "Return to Manage Categories menu"

    menu_response = helpers.display_menu(title, options, zero_option)

    if menu_response == MenuSignal.EXIT:
        return None

    if callable(menu_response):
        menu_response(gradebook)


# TODO: display "short" report first, prompt for "long" report second
def view_individual_category(gradebook: Gradebook) -> None:
    search_results = helpers.search_categories(gradebook)
    category = helpers.prompt_category_selection(search_results)

    if not category:
        return None

    print("\nYou are viewing the following category:")
    print(formatters.format_category_oneline(category))


def view_active_categories(gradebook: Gradebook) -> None:
    print(f"\n{formatters.format_banner_text("Active Categories")}")

    active_categories = gradebook.get_records(
        gradebook.categories, lambda x: x.is_active
    )

    if not active_categories:
        print("There are no active categories.")
        return None

    sort_and_display_categories(active_categories)


def view_inactive_categories(gradebook: Gradebook) -> None:
    print(f"\n{formatters.format_banner_text("Inactive Categories")}")

    inactive_categories = gradebook.get_records(
        gradebook.categories, lambda x: not x.is_active
    )

    if not inactive_categories:
        print("There are no inactive categories.")
        return None

    sort_and_display_categories(inactive_categories)


def view_all_categories(gradebook: Gradebook) -> None:
    print(f"\n{formatters.format_banner_text("All Categories")}")

    all_categories = gradebook.get_records(gradebook.categories)

    if not all_categories:
        print("There are no categories yet.")
        return None

    sort_and_display_categories(all_categories)


def sort_and_display_categories(categories: list[Category]) -> None:
    sorted_categories = sorted(categories, key=lambda c: c.name)
    helpers.display_results(
        sorted_categories, False, formatters.format_category_oneline
    )
