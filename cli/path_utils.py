# cli/path_utils.py

import os


def sanitize_name(name: str) -> str:
    return name.strip().replace(" ", "_")


def get_save_dir(course_name: str, course_term: str, user_input: str | None) -> str:
    if user_input is not None:
        return os.path.expanduser(user_input.strip())
    else:
        documents = os.path.join(os.path.expanduser("~"), "Documents")
        return os.path.join(documents, "Gradebooks", course_term, course_name)


def resolve_save_dir(course_name: str, course_term: str, dir_input: str | None) -> str:
    course = sanitize_name(course_name)
    term = sanitize_name(course_term)
    save_dir = get_save_dir(course, term, dir_input)
    os.makedirs(save_dir, exist_ok=True)

    return save_dir


def dir_is_empty(dir_path: str) -> bool:
    return os.path.isdir(dir_path) and not os.listdir(dir_path)
