"""The settings.

The storage path is the one that matters here: the server, the scripts and the
tests are started from different directories, so a relative path must not point
at a different folder in each of them.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import ROOT_DIR, Settings


def test_a_relative_storage_path_is_resolved_against_the_repository() -> None:
    settings = Settings(storage_dir=Path("storage"))
    assert settings.storage_dir == (ROOT_DIR / "storage").resolve()
    assert settings.storage_dir.is_absolute()


def test_an_absolute_storage_path_is_left_alone() -> None:
    target = Path("C:/example/storage")
    settings = Settings(storage_dir=target)
    assert settings.storage_dir == target


def test_the_default_storage_path_is_the_repository_one() -> None:
    settings = Settings()
    assert settings.storage_dir == (ROOT_DIR / "storage").resolve()
