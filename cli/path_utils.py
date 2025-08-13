# cli/path_utils.py

import os


def sanitize_name(name: str) -> str:
    """
    Sanitizes a course name or term string for use in file paths.

    Args:
        name (str): The input string to sanitize.

    Returns:
        A string with leading and trailing whitespace removed and internal spaces replaced with underscores.
    """
    return name.strip().replace(" ", "_")


def get_save_dir(course_name: str, course_term: str, user_input: str | None) -> str:
    """
    Resolves a save directory path for a new `Gradebook` based on user input or default location.

    Args:
        course_name (str): The course name string (unsanitized).
        course_term (str): The course term string (unsanitized).
        user_input (str | None): An optional user-specified directory path. If None or blank, the default path is used.

    Returns:
        A resolved path string. If user input is provided, it is expanded and returned directly.
        Otherwise, defaults to: `~/Documents/Gradebooks/<course_term>/<course_name>` with sanitized components.
    """
    if user_input is not None:
        return os.path.expanduser(user_input.strip())
    else:
        documents = os.path.join(os.path.expanduser("~"), "Documents")
        return os.path.join(documents, "Gradebooks", course_term, course_name)


def resolve_save_dir(course_name: str, course_term: str, dir_input: str | None) -> str:
    """
    Produces and ensurses a valid save directory path for a new `Gradebook`.

    Args:
        course_name (str): The course name string (may contain spaces).
        course_term (str): The course term string (may contain spaces).
        dir_input (str | None): An optional directory path string. If None, the default path is used.

    Returns:
        A fully resolved, sanitized, and created directory path for storing `Gradebook` files.

    Notes:
        - Sanitizes the course name and term.
        - Creates the directory path on disk (including parent directories) if it does not exist.
    """
    course = sanitize_name(course_name)
    term = sanitize_name(course_term)
    save_dir = get_save_dir(course, term, dir_input)

    os.makedirs(save_dir, exist_ok=True)

    return save_dir


def dir_is_empty(dir_path: str) -> bool:
    """
    Checks whether a directory exists and contains no files.

    Args:
        dir_path (str): A string path to the target directory.

    Returns:
        True if the path exists, is a directory, and contains no files or subdirectories. False otherwise.
    """
    return os.path.isdir(dir_path) and not os.listdir(dir_path)


# TODO: add auto-complete, readline, and completer enabled input
