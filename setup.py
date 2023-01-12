"""The setup script."""
import os
from io import open

from setuptools import setup, find_packages

REQUIREMENTS = [
    "click>=8.1.1",
    "click-default-group>=1.2.2"
]

curr_dir = os.path.abspath(os.path.dirname(__file__))


def get_file_text(file_name):
    with open(os.path.join(curr_dir, file_name), "r", encoding="utf-8") as in_file:
        return in_file.read()


_init = {}
_init_file = os.path.join(curr_dir, "pycaniuse", "__init__.py")
with open(_init_file) as fp:
    exec(fp.read(), _init)
name = _init["__name__"]
version = _init["__version__"]
author = _init["__author__"]
email = _init["__email__"]

setup(
    name=name,
    version=version,
    description="CLI tool to search caniuse.com from your shell",
    long_description=get_file_text("README.rst")
    + "\n\n"
    + get_file_text("CHANGELOG.rst"),
    long_description_content_type="text/x-rst",
    author=author,
    author_email=email,
    maintainer=author,
    maintainer_email=email,
    license="MIT license",
    packages=find_packages(include=["pycaniuse"]),
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    url="https://github.com/viseshrp/pycaniuse",
    project_urls={
        "Documentation": "https://github.com/viseshrp/pycaniuse",
        "Changelog": "https://github.com/viseshrp/pycaniuse/blob/main/CHANGELOG.rst",
        "Bug Tracker": "https://github.com/viseshrp/pycaniuse/issues",
        "Source Code": "https://github.com/viseshrp/pycaniuse",
    },
    python_requires=">=3.7",
    keywords="pycaniuse caniuse javascript css html js browser compatibility",
    test_suite="tests",
    tests_require=[
        "pytest",
    ],
    install_requires=REQUIREMENTS,
    entry_points={
        "console_scripts": [
            "caniuse=pycaniuse.__main__:main",
        ],
    },
)
