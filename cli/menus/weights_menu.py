# cli/weights_menu.py

"""
Category Weights Management Menu for the Gradebook CLI.

This module provides interactive functionality for enabling or disabling category weighting,
assigning and validating weights across active categories, viewing the current weight configuration,
and resetting all weights to start fresh or safely disable weighting.

Features include:
- Toggling weighted grading on or off, with enforced validation and reset flows
- Assigning weights via a guided input process that ensures totals sum to 100.0%
- Detecting and resolving incomplete or invalid weighting states with user-led recovery
- Viewing current active category weights
- Structured responses for all state mutations via the Gradebook API

This menu enforces safe user interaction, clear feedback, and complete separation between
state mutation (handled by the `Gradebook`) and user input/flow control (handled here).
"""

import math
from typing import cast

import cli.menu_helpers as helpers
import cli.model_formatters as model_formatters
import core.formatters as formatters
from cli.menu_helpers import MenuSignal
from models.category import Category
from models.gradebook import Gradebook


# complete
def run(gradebook: Gradebook) -> None:
    """
    Top-level loop with dispatch for the Manage Category Weights menu.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Raises:
        RuntimeError: If the menu response is unrecognized.

    Notes:
        - The finally block guarantees a check for unsaved changes before returning.
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


# complete
def edit_weighting_status_and_confirm(gradebook: Gradebook) -> None:
    """
    Activates or deactivates category weighting in the Gradebook.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - If activating, this method validates current weights before proceeding.
        - If deactivating, this method prompts the user to confirm and reset all category weights.
        - State mutation is handled by `gradebook.toggle_is_weighted()`, which returns a structured `Response`.
    """
    print(
        f"\nWeighted categories for this Gradebook are currently: {gradebook.weighting_status}."
    )

    if not helpers.confirm_action(
        f"Are you sure you want to {'deactivate' if gradebook.uses_weighting else 'activate'} weighted categories?"
    ):
        helpers.returning_without_changes()
        return

    if gradebook.uses_weighting:
        if not confirm_and_reset_weights(gradebook):
            print(
                "\nCategory weights must be reset in order to proceed. Deactivation canceled."
            )
            return

    else:
        if not validate_weights(gradebook):
            print(
                "\nCategory Weights must be validated in order to proceed. Activation canceled."
            )
            return

    gradebook_response = gradebook.toggle_is_weighted()

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)

    else:
        print(f"\n{gradebook_response.detail}")

    if gradebook.has_unsaved_changes:
        helpers.prompt_if_dirty(gradebook)

    else:
        helpers.returning_without_changes()

    helpers.returning_to("Manage Category Weights menu")


# complete
def assign_weights(gradebook: Gradebook) -> bool:
    """
    Guides the user through resetting and reassigning weights for all active categories.

    This process displays current weights, prompts for full reassignment, and validates
    new values before applying them. If the operation is confirmed, all existing weights
    are reset and replaced with the new assignments.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        bool:
            - True if all weights were reassigned successfully and the process completed.
            - False if the user cancels or if any operation fails.
    """
    categories_response = gradebook.get_records(
        gradebook.categories, lambda x: x.is_active
    )

    if not categories_response.success:
        helpers.display_response_failure(categories_response)
        print("\nWeight assignment canceled.")
        return False

    active_categories = categories_response.data["records"]

    if not active_categories:
        print("\nThere are no active categories yet.")
        return False

    banner = formatters.format_banner_text("Current Category Weights")
    print(f"\n{banner}")
    for category in active_categories:
        print(f"... {model_formatters.format_category_oneline(category)}")

    if not helpers.confirm_action(
        "Would you like to remove these values and reassign weights for all categories?"
    ):
        helpers.returning_without_changes()
        return False

    pending_weights = prompt_weights_input_or_cancel(active_categories)

    if pending_weights is MenuSignal.CANCEL:
        return False
    pending_weights = cast(list[tuple[Category, float]], pending_weights)

    print(
        "\nYou are about to update the Gradebook to use the following weighting assignments:"
    )
    for category, weight in pending_weights:
        print(f"... {category.name:<20} | {weight:>5.1f} %")

    if not helpers.confirm_make_change():
        helpers.returning_without_changes()
        return False

    print("\nResetting category weights ...")

    reset_response = gradebook.reset_category_weights()

    if not reset_response.success:
        helpers.display_response_failure(reset_response)
        print("\nWeight assignment canceled.")
        return False

    print("\nUpdating category weights with new values ...")
    for category, weight in pending_weights:
        gradebook_response = gradebook.update_category_weight(category, weight)

        if not gradebook_response.success:
            helpers.display_response_failure(gradebook_response)
            print("\nWeight assignment canceled. Resetting all weights to None.")
            gradebook.reset_category_weights()
            return False

        print(f"... {gradebook_response.detail}")

    print("\nProcess complete. All categories successfully updated.")

    helpers.prompt_if_dirty(gradebook)

    return True


# complete
def prompt_weights_input_or_cancel(
    active_categories: list[Category],
) -> list[tuple[Category, float]] | MenuSignal:
    """
    Prompts the user to assign weights to all active categories, ensuring the total equals 100.0%.

    The user is shown the remaining percentage available at each step and may cancel at any time.
    If the total assigned does not sum to 100%, the user will be prompted to try again or cancel.

    Args:
        active_categories (list[Category]): The list of active `Category` objects to assign weights for.

    Returns:
        list[tuple[Category, float]]: A list of (Category, weight) tuples if successful.
        MenuSignal.CANCEL: If the user cancels the process at any point.
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
                    print(f"\n[ERROR] {e}")
                    print("Please try again.")
                    continue

                if weight is None:
                    print(
                        "Empty input is not allowed. Enter a number between 0 and 100."
                    )
                    print("Please try again.")
                    continue

                if weight > remaining_percentage:
                    print(
                        f"\nThe weight {weight} exceeds the remaining {remaining_percentage:.1f} %. Try again with a smaller value."
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


# complete
def view_current_weights(gradebook: Gradebook) -> None:
    """
    Displays the current weights for all active categories in the Gradebook.

    This method fetches all active `Category` records, sorts them alphabetically,
    and prints a summary line for each including its name and weight.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Notes:
        - If no active categories are found, a message is printed and no list is shown.
        - If category retrieval fails, a formatted error is displayed.
    """
    categories_response = gradebook.get_records(
        gradebook.categories, lambda x: x.is_active
    )

    if not categories_response.success:
        helpers.display_response_failure(categories_response)
        print("\nCannot display category weights.")
        return

    active_categories = categories_response.data["records"]

    if not active_categories:
        print("\nThere are no active categories yet.")
        return

    active_categories = sorted(active_categories, key=lambda x: x.name)

    banner = formatters.format_banner_text("Category Weights")
    print(f"\n{banner}")

    for category in active_categories:
        print(model_formatters.format_category_oneline(category))


# complete
def validate_weights(gradebook: Gradebook) -> bool:
    """
    Validates that all active categories have assigned weights and that their total equals 100.0.

    Guides the user through resolving incomplete or invalid weighting configurations via
    interactive prompts. This method is designed to be resilient: it will recursively re-validate
    after successful resolution steps.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        bool:
            - True if validation completes successfully and weights are valid.
            - False if the user cancels or if any blocking issues remain unresolved.

    Notes:
        - Weights of `0.0` are allowed, but `None` is not.
        - If any active categories are missing weights, the user will be prompted to assign them.
        - If the total of all weights does not equal 100.0 (within tolerance), the user will be prompted to reassign.
        - Categories with weight `0.0` are permitted and surfaced to the user with a warning, but do not block validation.
    """
    print("\nBeginning validation process ...")

    categories_response = gradebook.get_records(
        gradebook.categories, lambda x: x.is_active
    )

    if not categories_response.success:
        helpers.display_response_failure(categories_response)
        print("\nValidation canceled.")
        return False

    active_categories = categories_response.data["records"]

    if not active_categories:
        print("\nThere are no active categories yet.")
        return False

    if any(category.weight is None for category in active_categories):
        print("\nSome active categories are missing weight values.")
        print("Launching guided resolution process ...")

        if handle_missing_weights(active_categories, gradebook):
            return validate_weights(gradebook)

        else:
            return False

    weights_total = 0.0

    for category in active_categories:
        weights_total += category.weight if category.weight else 0.0

    if not math.isclose(weights_total, 100.0, abs_tol=0.01):
        print(
            f"\nThe total of all active category weights is {weights_total:.2f}, which does not equal 100.0."
        )

        print(
            "You can resolve this issue and continue the validation process by reassigning weights for all categories."
        )

        if not helpers.confirm_action(
            "Would you like to reassign weights for all categories?"
        ):
            print("\nValidation canceled.")
            return False

        print("Launching re-assignment process ...")

        if assign_weights(gradebook):
            return validate_weights(gradebook)

        else:
            return False

    zero_weights = [c for c in active_categories if c.weight == 0.0]

    if zero_weights:
        print("\nActive categories with a '0.0' weight will still show up in reports,")
        print("but will not have any impact on final grade calculations.")
        print(
            "You can always reassign weights by selecting 'Assign Weights' from the menu."
        )

        print("\nThe following categories have a '0.0' weight.")
        for category in zero_weights:
            print(model_formatters.format_category_oneline(category))

    print("\nValidation check completed successfully.")
    return True


# complete
def handle_missing_weights(
    active_categories: list[Category], gradebook: Gradebook
) -> bool:
    """
    Guides the user through resolving missing weights for active categories.

    For each category with no assigned weight, the user may:
    - Set the weight to 0.0%
    - Archive the category
    - Reassign weights for all active categories

    This method is called during the validation process when missing weights are detected.

    Args:
        active_categories (list[Category]): A list of currently active categories.
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        bool:
            - True if all missing weights are resolved successfully.
            - False if the user cancels or if resolution is incomplete.
    """

    def set_to_zero(category: Category) -> None:
        """
        Assigns a weight of 0.0 to the given `Category` after user confirmation.

        Args:
            category (Category): The `Category` targeted for zero-weighting.

        Notes:
            - This keeps the `Category` active and visible in reports, but it will not affect final grade calculations.
        """
        print(f"\nSetting '{category.name}' to 0.0% will keep it visible in reports,")
        print("but it will have no effect on final grade calculations.")

        if not helpers.confirm_action(
            "Do you want to proceed with assigning a weight of 0.0%?"
        ):
            helpers.returning_without_changes()
            return

        gradebook_response = gradebook.update_category_weight(category, 0.0)

        if not gradebook_response.success:
            helpers.display_response_failure(gradebook_response)
            print("\nCould not update category weight.")
            helpers.returning_without_changes()
            return

        print(f"\n{gradebook_response.detail}")

    def confirm_and_archive(category: Category) -> None:
        """
        Archives the given `Category` after user confirmation.

        Args:
            category (Category): The `Category` targeted for archiving.

        Notes:
            - This removes the `Category` from active lists and grade calculations, but preserves its data for later use.
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
            return

        gradebook_response = gradebook.toggle_category_active_status(category)

        if not gradebook_response.success:
            helpers.display_response_failure(gradebook_response)
            print("\nCould not archive category.")
            helpers.returning_without_changes()
            return

        print(f"\n{gradebook_response.detail}")

        if not category.is_active:
            active_categories.remove(category)

    categories_missing_weights = [
        c for c in active_categories if c.weight is None and c.is_active
    ]

    print("\nThe following active categories are missing assigned weights:")
    for category in categories_missing_weights:
        print(model_formatters.format_category_oneline(category))
    print("\nAll active categories must have a defined weight to proceed.")

    banner = "Resolving Missing Weights"
    print(f"\n{banner}")

    while categories_missing_weights:
        category = categories_missing_weights[0]

        title = f"Resolve {category.name}"
        options = [
            ("Set weight to 0.0", lambda c=category: set_to_zero(c)),
            ("Archive this category", lambda c=category: confirm_and_archive(c)),
            ("Reassign weights for all", lambda: assign_weights(gradebook)),
        ]
        zero_option = "Cancel validation and return"

        menu_response = helpers.display_menu(title, options, zero_option)

        if menu_response is MenuSignal.EXIT:
            if gradebook.has_unsaved_changes:
                print("\nValidation canceled, but changes have been made.")
                helpers.prompt_if_dirty(gradebook)

            else:
                print("\nValidation canceled. No changes were made.")

            return False

        elif callable(menu_response):
            menu_response()

        else:
            raise RuntimeError(f"Unexpected MenuResponse received: {menu_response}")

        categories_missing_weights = [
            c for c in active_categories if c.weight is None and c.is_active
        ]

    helpers.prompt_if_dirty(gradebook)

    return True


# complete
def confirm_and_reset_weights(gradebook: Gradebook) -> bool:
    """
    Prompts the user to confirm and reset all active category weights to `None`.

    This action is typically performed before disabling weighted grading. It removes all
    assigned weights but preserves the categories themselves.

    Args:
        gradebook (Gradebook): The active `Gradebook`.

    Returns:
        bool:
            - True if the reset is confirmed and completes successfully.
            - False if the user cancels or if the reset operation fails.
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

    gradebook_response = gradebook.reset_category_weights()

    if not gradebook_response.success:
        helpers.display_response_failure(gradebook_response)
        return False

    print(f"\n{gradebook_response.detail}")

    if gradebook.has_unsaved_changes:
        helpers.prompt_if_dirty(gradebook)

    else:
        helpers.returning_without_changes()

    return True


# TODO:
def weighting_help():
    print("STUB: User-facing help for Category Weights menu")
