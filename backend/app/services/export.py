"""Helpers for safe export of user-provided document content."""

from typing import Any


def safe_csv_value(value: Any) -> Any:
    """Prevent spreadsheet applications from evaluating untrusted text as a formula."""
    if not isinstance(value, str):
        return value
    if value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value
