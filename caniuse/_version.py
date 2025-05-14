from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pycaniuse")
except PackageNotFoundError:  # pragma: no cover
    # Fallback for local dev or editable installs
    __version__ = "0.0.0"
