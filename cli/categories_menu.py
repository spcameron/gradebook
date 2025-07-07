# cli/categories_menu.py

from cli import weights_menu
from cli.menu_helpers import (
    confirm_action,
    display_menu,
    display_results,
    format_banner_text,
    prompt_user_input,
    returning_without_changes,
    MenuSignal,
)
from models.category import Category
from models.gradebook import Gradebook
from typing import Callable
from utils.utils import generate_uuid


def run(gradebook: Gradebook) -> None:
    title = format_banner_text("Manage Categories")
    options = [
        ("Add Category", add_category),
        ("Edit Category", edit_category),
        ("Remove Category", remove_category),
        ("View Category Details", view_category),
        ("View All Categories", view_all_categories),
        ("View Active Categories", view_active_categories),
        ("View Archived Categories", view_archived_categories),
        ("Manage Category Weights", weights_menu.run),
    ]
    zero_option = "Return to Course Manager menu"

    while True:
        menu_response = display_menu(title, options, zero_option)

        if menu_response == MenuSignal.EXIT:
            if confirm_action("Would you like to save before returning?"):
                gradebook.save(gradebook.path)
            return None

        if callable(menu_response):
            menu_response(gradebook)


def add_category(gradebook: Gradebook) -> None:
    while True:
        new_category = prompt_new_category()

        if new_category is not None:
            gradebook.add_category(new_category)
            print(f"\n{new_category.name} successfully added to {gradebook.name}")

        if not confirm_action("Would you like to continue adding new categories?"):
            print(f"\nReturning to Manage Categories menu.")
            return None


def prompt_new_category() -> Category | None:
    while True:
        name = prompt_user_input("Enter category name (leave blank to cancel):")
        if name == "":
            return None

        # TODO: data validation - bare minimum for now
        if name:
            break
        else:
            print("A name is required.")

    try:
        category_id = generate_uuid()
        new_category = Category(category_id, name)
    except (TypeError, ValueError) as e:
        print(f"\nError: Could not create category ... {e}")
        return None

    return new_category


def edit_category(gradebook: Gradebook) -> None:
    search_results = search_categories(gradebook)
    category = prompt_category_selection(search_results)

    if not category:
        return None

    title = format_banner_text("Editable Fields")
    options = get_editable_fields()
    zero_option = "Return without changes"

    while True:
        print("\nYou are viewing the following category:")
        print(format_name_and_weight(category))

        menu_response = display_menu(title, options, zero_option)

        if menu_response == MenuSignal.EXIT:
            returning_without_changes()
            return None

        if callable(menu_response):
            menu_response(category, gradebook)

        if not confirm_action("Would you like to continue editing this category?"):
            print("\nReturning to Manage Categories menu.")
            return None


def edit_name_and_confirm(category: Category, gradebook: Gradebook) -> None:
    current_name = category.name
    new_name = prompt_user_input("Enter a new name (leave blank to cancel):")

    if new_name == "":
        returning_without_changes()
        return None

    print(f"\nCurrent category name: {current_name} ... New category name: {new_name}")

    save_change = confirm_action("Do you want to save this change?")

    if not save_change:
        returning_without_changes()
        return None

    category.name = new_name
    gradebook.save(gradebook.path)
    print("\nName successfully updated.")


def edit_archive_and_confirm(category: Category, gradebook: Gradebook) -> None:
    print(f"\nThis category is currently {category.status}.")

    if not confirm_action("Would you like to edit the archived status?"):
        returning_without_changes()
        return None

    if category.is_archived:
        confirm_and_reactivate(category, gradebook)
    else:
        confirm_and_archive(category, gradebook)


def get_editable_fields() -> (
    list[tuple[str, Callable[[Category, Gradebook], MenuSignal | None]]]
):
    return [
        ("Name", edit_name_and_confirm),
        ("Archived Status", edit_archive_and_confirm),
    ]


def remove_category(gradebook: Gradebook) -> None:
    search_results = search_categories(gradebook)
    category = prompt_category_selection(search_results)

    if not category:
        return None

    print("\nYou are viewing the following category:")
    print(format_name_and_weight(category))

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

    menu_response = display_menu(title, options, zero_option)

    if menu_response == MenuSignal.EXIT:
        returning_without_changes()
        return None

    if callable(menu_response):
        menu_response(category, gradebook)


def confirm_and_remove(category: Category, gradebook: Gradebook) -> None:
    caution_banner = format_banner_text("CAUTION!")
    print(f"\n{caution_banner}")
    print("You are about to permanently delete the following category:")
    print(f"{category.name}")
    print(f"\nThis will also delete all linked assignments and submissions.")

    confirm_deletion = confirm_action(
        "Are you sure you want to permanently remove this category? This action cannot be undone."
    )

    if not confirm_deletion:
        returning_without_changes()
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

    confirm_archiving = confirm_action(
        "Are you sure you want to archive this category and all linked assignments and submissions?"
    )

    if not confirm_archiving:
        returning_without_changes()
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

    confirm_reactivate = confirm_action(
        "Are you sure you want to reactivate this category and all linked assignments and submissions?"
    )

    if not confirm_reactivate:
        returning_without_changes()
        return None

    category.toggle_archived_status()
    gradebook.save(gradebook.path)
    print(f"\nCategory successfully reactivated.")


# TODO: display "short" report first, prompt for "long" report second
def view_category(gradebook: Gradebook) -> None:
    search_results = search_categories(gradebook)
    category = prompt_category_selection(search_results)

    if not category:
        return None

    print("\nYou are viewing the following category:")
    print(format_name_and_weight(category))


def view_all_categories(gradebook: Gradebook) -> None:
    all_categories_banner = format_banner_text("All Categories")
    print(f"\n{all_categories_banner}")

    all_categories = list(gradebook.categories.values())
    if not all_categories:
        print("No categories created yet.")
        return None

    sort_and_display_results(all_categories)


def view_active_categories(gradebook: Gradebook) -> None:
    active_categories_banner = format_banner_text("Active Categories")
    print(f"\n{active_categories_banner}")

    active_categories = [c for c in gradebook.categories.values() if not c.is_archived]
    if not active_categories:
        print("No active categories yet.")
        return None

    sort_and_display_results(active_categories)


def view_archived_categories(gradebook: Gradebook) -> None:
    archived_categories_banner = format_banner_text("Archived Categories")
    print(f"\n{archived_categories_banner}")

    archived_categories = [c for c in gradebook.categories.values() if c.is_archived]
    if not archived_categories:
        print("No archived categories yet.")
        return None

    sort_and_display_results(archived_categories)


def sort_and_display_results(categories: list[Category]) -> None:
    sorted_categories = sorted(categories, key=lambda c: c.name)
    display_results(sorted_categories, False, format_name_and_weight)


def search_categories(gradebook: Gradebook) -> list[Category]:
    query = prompt_user_input("Search for a category by name:").lower()
    matches = [
        category
        for category in gradebook.categories.values()
        if query in category.name.lower()
    ]
    return matches


def prompt_category_selection(search_results: list[Category]) -> Category | None:
    if not search_results:
        print("\nNo matching categories found.")

    if len(search_results) == 1:
        return search_results[0]

    print(f"\nYour search returned {len(search_results)} categories:")

    while True:
        display_results(search_results, True, lambda c: f"{c.name}")
        choice = prompt_user_input("Select an option (0 to cancel): ")

        if choice == "0":
            return None
        try:
            index = int(choice) - 1
            return search_results[index]
        except (ValueError, IndexError):
            print("\nInvalid selection. Please try again.")


def format_name_and_weight(category: Category) -> str:
    return f"{category.name:<20} | {category.weight} %"
