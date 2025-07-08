# cli/weights_menu.py

from cli.menu_helpers import (
    confirm_action,
    display_menu,
    format_banner_text,
    MenuSignal,
    returning_without_changes,
)
from models.gradebook import Gradebook


def run(gradebook: Gradebook) -> None:
    title = format_banner_text("Manage Category Weights")
    options = [
        ("Toggle Weighting On/Off", toggle_weights),
        ("Assign Weights", assign_weights),
        ("View Current Weights", view_current_weights),
        ("Validate Weights", validate_weights),
        ("Reset All Weights", reset_weights),
        ("Explain Weighting Policy", weighting_help),
    ]
    zero_option = "Return to Manage Categories menu"

    while True:
        menu_response = display_menu(title, options, zero_option)

        if menu_response == MenuSignal.EXIT:
            if confirm_action("Would you like to save before returning?"):
                gradebook.save(gradebook.path)
            return None

        if callable(menu_response):
            menu_response(gradebook)


def toggle_weights(gradebook: Gradebook) -> None:
    uses_weighting = "uses" if gradebook.uses_weighting else "does not use"
    on_or_off = "off" if gradebook.uses_weighting else "on"

    print(f"\nThis Gradebook currently {uses_weighting} weighted categories.")

    if not confirm_action(f"Do you want to turn weighted categories {on_or_off}?"):
        returning_without_changes()
        return None

    gradebook.toggle_uses_weighting()
    gradebook.save(gradebook.path)

    if gradebook.uses_weighting:
        print("Gradebook successfully updated. Weighted categories enabled.")
    else:
        print("Gradebook successfully updated. Weighted categories disabled.")


# TODO:
def assign_weights():
    pass


# TODO:
def view_current_weights():
    pass


# TODO:
def validate_weights():
    pass


# TODO:
def reset_weights():
    pass


# TODO:
def weighting_help():
    pass
