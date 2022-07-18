"""Sphinx configuration."""
project = "Pycaniuse"
author = "Visesh Prasad"
copyright = "2022, Visesh Prasad"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_click",
    "myst_parser",
]
autodoc_typehints = "description"
html_theme = "furo"
