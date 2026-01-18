"""Sphinx configuration."""

from datetime import datetime

project = "QBox"
author = "Greg Twohig"
copyright = f"{datetime.now().year}, {author}"  # noqa: A001
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.doctest",
    "sphinx_rtd_theme",
    "myst_parser",
]
autodoc_typehints = "description"
html_theme = "sphinx_rtd_theme"
