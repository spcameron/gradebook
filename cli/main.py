# cli/main.py

from cli.menu_helpers import display_menu
from models.gradebook import Gradebook


def run_cli():
    title = "===== GRADEBOOK APP ====="
    options = {
        "Create a new Gradebook": lambda: create_gradebook(),
        "Load an existing Gradebook": lambda: load_gradebook(),
        "Exit Program": lambda: exit_program(),
    }

    display_menu(title, options)


def create_gradebook() -> Gradebook:
    name = input("Enter the course name: ")
    term = input("Enter the course term: ")
    return Gradebook.create(name, term)


def load_gradebook() -> Gradebook:
    pass


def exit_program():
    pass
