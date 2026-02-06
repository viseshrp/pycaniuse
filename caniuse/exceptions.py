"""All exceptions used in the code base are defined here."""

from __future__ import annotations


class CustomError(Exception):
    """
    Base exception. All other exceptions
    inherit from here.
    """

    detail = "An error occurred."

    def __init__(self, extra_detail: str | None = None) -> None:
        super().__init__()
        self.extra_detail = extra_detail

    def __str__(self) -> str:
        if self.extra_detail:
            return f"{self.detail} :: {self.extra_detail}"
        return self.detail
