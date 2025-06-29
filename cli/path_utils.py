# cli/path_utils.py

import os


def sanitize_name(name: str) -> str:
    return name.strip().replace(" ", "_")


def get_save_dir(course_name: str, course_term: str, user_input: str | None) -> str:
    if user_input:
        return os.path.expanduser(user_input.strip())
    else:
        return os.path.join("Gradebooks", course_term, course_name)


def get_save_file(course_name: str, course_term: str, user_input: str | None) -> str:
    if user_input is None:
        filename = f"{course_term}_{course_name}.json"
    else:
        filename = user_input.strip()

    if not filename.endswith(".json"):
        filename += ".json"

    return filename


def build_file_path(
    course_name: str, course_term: str, dir_input: str | None, file_input: str | None
) -> str:
    course = sanitize_name(course_name)
    term = sanitize_name(course_term)
    save_dir = get_save_dir(course, term, dir_input)
    save_filename = get_save_file(course, term, file_input)

    os.makedirs(save_dir, exist_ok=True)
    return os.path.join(save_dir, save_filename)
