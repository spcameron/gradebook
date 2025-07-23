# cli/weights_menu.py

"""
Category Weights Management Menu for the Gradebook CLI.

This module provides interactive functionality for enabling or disabling category weighting globally,
assigning and validating weights across active categories, displaying the current weight configuration,
resetting all weights to start fresh or disable weighting safely, and explaining how weighting works.
"""

import cli.formatters as formatters
import cli.menu_helpers as helpers
from cli.menu_helpers import MenuSignal
from models.category import Category
from models.gradebook import Gradebook


def run(gradebook: Gradebook) -> None:
    """
    Top-level loop with dispatch for the Manage Category Weights menu.

    Args:
        gradebook: The active Gradebook.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        The finally block guarantees a check for unsaved changes before returning.
    """
    title = formatters.format_banner_text("Manage Category Weights")
    options = [
        ("Toggle Weighting On/Off", edit_weighting_status_and_confirm),
        ("Assign Weights", assign_weights),
        ("View Current Weights", view_current_weights),
        ("Validate Weights", validate_weights),
        ("Reset All Weights", reset_weights),
        ("Explain Weighting Policy", weighting_help),
    ]
    zero_option = "Return to Manage Categories menu"

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

    helpers.returning_to("Manage Categories menu")


def edit_weighting_status_and_confirm(gradebook: Gradebook) -> None:
    action = "deactivate" if gradebook.is_weighted else "activate"

    print(
        f"\nWeighted categories for this Gradebook are currently: {gradebook.weighting_status}."
    )

    if not helpers.confirm_action(
        f"Are you sure you want to {action} weighted categories?"
    ):
        helpers.returning_without_changes()
        return None

    # TODO:
    # action fork: validate and activate, or reset and deactivate

    try:
        # TODO: validation check goes here
        gradebook.toggle_is_weighted()
        gradebook.mark_dirty()
        print(
            f"Gradebook successfully updated. Weighted categories are currently: {gradebook.weighting_status}."
        )
    except Exception as e:
        print(f"\nError: Could not update Gradebook ... {e}")
        helpers.returning_without_changes()


# TODO:
def assign_weights():
    pass


# TODO:
def view_current_weights():
    pass


# TODO:
def validate_weights(gradebook: Gradebook) -> bool:
    # 1. aggregate active categories only
    active_categories = gradebook.get_records(
        gradebook.categories, lambda x: x.is_active
    )

    # 2. detect missing weights (None) and divert
    if any(category.weight is None for category in active_categories):
        return handle_missing_weights(active_categories, gradebook)

    # 3. detect invalid weights (mostly redundant)

    # 4. verify total weight == 100.0

    # 5. flag 0.0 weights (informational)

    # 6. success / ready to enable


# TODO:
def handle_missing_weights(
    active_categories: list[Category], gradebook: Gradebook
) -> bool:
    def set_to_zero(category: Category) -> None:
        # TODO: include messaging
        try:
            category.weight = 0.0
            print(f"\nCategory weight successfully updated to: {category.weight}")
        except Exception as e:
            print(f"\nError: Could not update category ... {e}")

    def confirm_and_archive(category: Category) -> None:
        # TODO: include messaging
        try:
            category.toggle_archived_status()
            print(f"\nCategory status successfully updated to: {category.status}")
            if not category.is_active:
                active_categories.remove(category)
        except Exception as e:
            print(f"\nError: Could not update category ... {e}")

    categories_missing_weights = [
        c for c in active_categories if c.weight is None and c.is_active
    ]
    # 1. intro and context
    print("\nThe following active categories are missing assigned weights:")
    for category in categories_missing_weights:
        print(formatters.format_category_oneline(category))
    print("\nAll active categories must have a defined weight to proceed.")

    # 2. iterate over missing categories
    while categories_missing_weights:
        category = categories_missing_weights[0]

        title = f"Resolve {category.name}"
        options = [
            ("Set weight to 0.0", lambda: set_to_zero(category)),
            ("Archive this category", lambda: confirm_and_archive(category)),
            ("Reassign weights for all", assign_weights),
        ]
        zero_option = "Cancel validation and return"

        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response is MenuSignal.EXIT:
            return False
        elif callable(menu_response):
            result = menu_response()
        else:
            raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

        # TODO: revisit after writing assign_weights(), needs to guarantee no None weights, a current assumption
        if result is True:
            return True

        categories_missing_weights = [c for c in active_categories if c.weight is None]

    return True


# TODO:
def reset_weights():
    pass


# TODO:
def weighting_help():
    pass
