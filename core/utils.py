# core/utils.py

"""
Repository for program-wide utilities.
"""

import uuid


def generate_uuid() -> str:
    return str(uuid.uuid4())
