"""
pycaniuse.exceptions
-----------------------
All exceptions used in the code base are defined here.
"""


class CaniuseException(Exception):
    """
    Base exception. All other exceptions
    inherit from here.
    """

    detail = "An error occurred."

    def __init__(self, extra_detail=None):
        super().__init__()
        self.extra_detail = extra_detail

    def __str__(self):
        if self.extra_detail:
            return f"{self.detail} :: {self.extra_detail}"
        return self.detail
