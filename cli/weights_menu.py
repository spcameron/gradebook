# cli/weights_menu.py

"""
Category Weights Management Menu for the Gradebook CLI.

This module provides interactive functionality for enabling or disabling category weighting globally,
assigning and validating weights across active categories, displaying the current weight configuration,
resetting all weights to start fresh or disable weighting safely, and explaining how weighting works.
"""

import math
from typing import cast

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
        ("Reset All Weights", confirm_and_reset_weights),
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
    """
    Activates or deactivates weighted categories for the Gradebook, depending on current status.

    Args:
        gradebook: The active Gradebook.

    Notes:
        If activating, calls validate_weights() before toggling.
        If deactivating, calls confirm_and_reset_weights() before toggling.
    """
    action = "deactivate" if gradebook.is_weighted else "activate"

    print(
        f"\nWeighted categories for this Gradebook are currently: {gradebook.weighting_status}."
    )

    if not helpers.confirm_action(
        f"Are you sure you want to {action} weighted categories?"
    ):
        helpers.returning_without_changes()
        return None

    if gradebook.is_weighted:
        reset_success = confirm_and_reset_weights(gradebook)
        if not reset_success:
            print(
                "\nCategory Weights must be reset in order to proceed. Deactivation canceled."
            )
            return None
    else:
        validate_success = validate_weights(gradebook)
        if not validate_success:
            print(
                "\nCategory Weights must be validated in order to proceed. Activation canceled."
            )
            return None

    try:
        gradebook.toggle_is_weighted()
        print(
            f"Gradebook successfully updated. Weighted categories are currently: {gradebook.weighting_status}."
        )
    except Exception as e:
        print(f"\nError: Could not update Gradebook weighting status ... {e}")

    if helpers.confirm_unsaved_changes():
        gradebook.save(gradebook.path)
    else:
        gradebook.mark_dirty()


def assign_weights(gradebook: Gradebook) -> bool:
    """
    Prompts the user to reset and assign new weights to all active Categories.

    Args:
        gradebook: The active Gradebook.

    Returns:
        True if the weights were successfully assigned and confirmed, and False otherwise.
    """
    active_categories = gradebook.get_records(
        gradebook.categories, lambda x: x.is_active
    )

    if not active_categories:
        print("\nThere are no active categories yet.")
        return False

    banner = formatters.format_banner_text("Current Category Weights")
    print(f"\n{banner}")
    for category in active_categories:
        print(f"... {formatters.format_category_oneline(category)}")

    if not helpers.confirm_action(
        "Would you like to remove these values and reassign weights for all categories?"
    ):
        helpers.returning_without_changes()
        return False

    pending_weights = prompt_weights_input_or_cancel(active_categories)

    if pending_weights is MenuSignal.CANCEL:
        return False
    else:
        pending_weights = cast(list[tuple[Category, float]], pending_weights)

    print(
        "\nYou are about to update the Gradebook to use the following weighting assignments:"
    )
    for category, weight in pending_weights:
        print(f"... {category.name:<20} | {weight:>5.1f} %")

    if not helpers.confirm_make_change():
        helpers.returning_without_changes()
        return False

    gradebook.reset_category_weights()

    for category, weight in pending_weights:
        success = category.update_category_weight(weight)
        if not success:
            print(f"\nError: Could not update {category.name}.")
            gradebook.reset_category_weights()
            return False

    print("\nAll categories successfully updated.")

    if helpers.confirm_unsaved_changes():
        gradebook.save(gradebook.path)
    else:
        gradebook.mark_dirty()

    return True


def prompt_weights_input_or_cancel(
    active_categories: list[Category],
) -> list[tuple[Category, float]] | MenuSignal:
    """
    Prompts the user to assign weights to all active categories, ensuring the total equals 100.0.

    Args:
        active_categories: The list of active Categories to be assigned weights.

    Returns:
        A list of (Category, float) tuples representing the new weight assignments,
        or MenuSignal.CANCEL if the user cancels during input.
    """
    while True:
        pending_weights = []
        remaining_percentage = 100.0

        for category in active_categories:
            if pending_weights:
                banner = formatters.format_banner_text("Assigned Weights")
                print(f"\n{banner}")
            for c, w in pending_weights:
                print(f"... {c.name:<20} | {w:>5.1f} %")

            print(f"\nRemaining percentage to allocate: {remaining_percentage:.1f} %")

            while True:
                user_input = helpers.prompt_user_input_or_cancel(
                    f"Enter a weight for {category.name} (leave blank to cancel):"
                )

                if isinstance(user_input, MenuSignal):
                    helpers.returning_without_changes()
                    return user_input

                try:
                    weight = Category.validate_weight_input(user_input)
                except (TypeError, ValueError) as e:
                    print(f"\nInvalid input - please try again ... {e}")
                    continue

                if weight is None:
                    print(
                        f"\nInvalid input - please try again ... Weight cannot be None."
                    )
                    continue

                if weight > remaining_percentage:
                    print(
                        f"\nThat weight exceeds the remaining {remaining_percentage:.1f} %. Try a smaller value."
                    )
                    continue

                break

            pending_weights.append((category, weight))
            remaining_percentage -= weight

        if abs(remaining_percentage) > 0.01:
            print("\nThe total weights do not add up to 100%.")
            if helpers.confirm_action("Would you like to try again?"):
                continue
            else:
                helpers.returning_without_changes()
                return MenuSignal.CANCEL

        return pending_weights


def view_current_weights(gradebook: Gradebook) -> None:
    """
    Displays the current weights for all active categories in the Gradebook.

    Args:
        gradebook: The active Gradebook.
    """
    active_categories = gradebook.get_records(
        gradebook.categories, lambda x: x.is_active
    )

    if not active_categories:
        print("\nThere are no active categories yet.")
        return None

    active_categories = sorted(active_categories, key=lambda x: x.name)

    banner = formatters.format_banner_text("Category Weights")
    print(f"\n{banner}")

    for category in active_categories:
        print(formatters.format_category_oneline(category))


def validate_weights(gradebook: Gradebook) -> bool:
    """
    Validates that all active categories have assigned weights and that the total weight equals 100.0.

    Args:
        gradebook: The active Gradebook.

    Returns:
        True if validation passes, and False otherwise.

    Notes:
        - Weights of 0.0 are allowed, but None is not.
        - If handle_missing_weights() or assign_weights() is invoked and succeeds,
          validate_weights() is called again to complete validation.
    """
    print("\nBeginning weighting validation check ...")
    active_categories = gradebook.get_records(
        gradebook.categories, lambda x: x.is_active
    )

    if not active_categories:
        print("\nThere are no active categories yet.")
        return False

    if any(category.weight is None for category in active_categories):
        if handle_missing_weights(active_categories, gradebook):
            return validate_weights(gradebook)
        else:
            return False

    weights_total = 0.0

    for category in active_categories:
        weights_total += category.weight

    if not math.isclose(weights_total, 100.0, abs_tol=0.01):
        print(
            f"\nThe total of all active category weights is {weights_total:.2f}, which does not equal 100.0"
        )

        print(
            "You can resolve this and continue the validation process by reassigning weights for all categories."
        )

        if not helpers.confirm_action(
            "Would you like to reassign weights for all categories?"
        ):
            print("\nValidation canceled.")
            return False

        if assign_weights(gradebook):
            return validate_weights(gradebook)
        else:
            return False

    zero_weights = [c for c in active_categories if c.weight == 0.0]

    if zero_weights:
        print("\nActive categories with a '0.0' weight will still show up in reports,")
        print("but will not have any impact on final grade calculations.")
        print("You can assign new weights by selecting 'Assign Weights' from the menu.")

        print("\nThe following categories have a '0.0' weight.")
        for category in zero_weights:
            print(formatters.format_category_oneline(category))

    print("\nValidation check completed successfully.")
    return True


def handle_missing_weights(
    active_categories: list[Category], gradebook: Gradebook
) -> bool:
    """
    Resolves missing weights by prompting the user to assign 0.0, archive the category, or reassign all weights.

    Args:
        active_categories: The list of active Categories with unresolved weights.
        gradebook: The active Gradebook.

    Returns:
        True if all missing weights are handled correctly, and False otherwise.
    """

    def set_to_zero(category: Category) -> None:
        """
        Assigns a weight of 0.0 to the given Category after user confirmation.

        Args:
            category: The Category targeted for zero-weighting.

        Notes:
            This keeps the Category active and visible in reports, but it will not affect final grade calculations.
        """
        print(f"\nSetting '{category.name}' to 0.0% will keep it visible in reports,")
        print("but it will have no effect on final grade calculations.")

        if not helpers.confirm_action(
            "Do you want to proceed with assigning a weight of 0.0%?"
        ):
            helpers.returning_without_changes()
            return None

        try:
            category.weight = 0.0
            nonlocal unsaved_changes
            unsaved_changes = True
            print(f"\nCategory weight successfully updated to: {category.weight}")
        except Exception as e:
            print(f"\nError: Could not update category ... {e}")

    def confirm_and_archive(category: Category) -> None:
        """
        Archives the given category after user confirmation.

        Args:
            category: The Category targeted for archiving.

        Notes:
            This removes the Category from active lists and grade calculations, but preserves its data for later use.
        """
        print(
            f"\nArchiving '{category.name}' is a safe way to deactivate a category without losing data."
        )
        print(
            "It will exclude it from most reports and final grade calculations, but can be reactivated later."
        )

        if not helpers.confirm_action(
            "Do you want to proceed with archiving this category?"
        ):
            helpers.returning_without_changes()
            return None

        try:
            category.toggle_archived_status()
            nonlocal unsaved_changes
            unsaved_changes = True
            print(f"\nCategory status successfully updated to: {category.status}")
            if not category.is_active:
                active_categories.remove(category)
        except Exception as e:
            print(f"\nError: Could not update category ... {e}")

    unsaved_changes = False

    categories_missing_weights = [
        c for c in active_categories if c.weight is None and c.is_active
    ]

    print("\nThe following active categories are missing assigned weights:")
    for category in categories_missing_weights:
        print(formatters.format_category_oneline(category))
    print("\nAll active categories must have a defined weight to proceed.")

    banner = "Resolving Missing Weights"
    print(f"\n{banner}")

    while categories_missing_weights:
        category = categories_missing_weights[0]

        title = f"Resolve {category.name}"
        options = [
            ("Set weight to 0.0", lambda: set_to_zero(category)),
            ("Archive this category", lambda: confirm_and_archive(category)),
            ("Reassign weights for all", lambda: assign_weights(gradebook)),
        ]
        zero_option = "Cancel validation and return"

        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response is MenuSignal.EXIT:
            if unsaved_changes:
                print("\nValidation canceled, but changes have been made.")
                if helpers.confirm_unsaved_changes():
                    gradebook.save(gradebook.path)
                else:
                    gradebook.mark_dirty()
            else:
                print("\nValidation canceled. No changes were made.")
            return False
        elif callable(menu_response):
            assign_weights_result = menu_response()
            if assign_weights_result is True:
                return True
        else:
            raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

        categories_missing_weights = [c for c in active_categories if c.weight is None]

    if unsaved_changes:
        if helpers.confirm_unsaved_changes():
            gradebook.save(gradebook.path)
        else:
            gradebook.mark_dirty()

    return True


def confirm_and_reset_weights(gradebook: Gradebook) -> bool:
    """
    Prompts the user to reset all active Category weights to None.

    Args:
        gradebook: The active Gradebook.

    Returns:
        True if the reset succeeds, and False otherwise.
    """
    banner = formatters.format_banner_text("Reset Category Weights")
    print(f"\n{banner}")

    print(
        "\nThis will remove the weights currently assigned to your active categories."
    )
    print(
        "You can assign new weights later by selecting 'Assign Weights' from the menu."
    )

    if not helpers.confirm_action(
        "Do you want to proceed with resetting the category weights?"
    ):
        helpers.returning_without_changes()
        return False

    try:
        gradebook.reset_category_weights()
        print("\nAll category weights successfully reset.")
    except Exception as e:
        print(f"\nError: Could not reset all categories ... {e}")
        return False

    if helpers.confirm_unsaved_changes():
        gradebook.save(gradebook.path)
    else:
        gradebook.mark_dirty()

    return True


# TODO:
def weighting_help():
    print("STUB: User-facing help for Category Weights menu")
