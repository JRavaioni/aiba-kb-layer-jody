"""Helpers to keep directories tracked in Git via .keepme files."""

from __future__ import annotations

from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar


KEEPME_FILENAME = ".keepme"
KEEPME_CONTENT = "# This file ensures Git tracks this empty directory\n"

F = TypeVar("F", bound=Callable[..., Any])


def ensure_keepme_file(directory_path: Path) -> None:
    """
    Ensure a .keepme file exists in the given directory.

    Args:
        directory_path: Path to the directory

    Returns:
        None
    """
    directory = Path(directory_path)
    if not directory.exists() or not directory.is_dir():
        return

    keepme_path = directory / KEEPME_FILENAME
    if keepme_path.exists():
        return

    keepme_path.write_text(KEEPME_CONTENT, encoding="utf-8")


def auto_keepme(func: F) -> F:
    """Decorator that ensures .keepme files for directory Path arguments/results."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = func(*args, **kwargs)

        candidate_paths: list[Path] = []
        for value in (*args, *kwargs.values()):
            if isinstance(value, Path):
                candidate_paths.append(value)

        if isinstance(result, Path):
            candidate_paths.append(result)
        elif isinstance(result, (list, tuple, set)):
            for item in result:
                if isinstance(item, Path):
                    candidate_paths.append(item)

        for path in candidate_paths:
            if path.exists() and path.is_dir():
                ensure_keepme_file(path)

        return result

    return wrapper  # type: ignore[return-value]
