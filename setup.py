#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

from setuptools import find_packages, setup


def get_version(relative_path: str) -> str:
    package_root = os.path.abspath(os.path.dirname(__file__))
    version = {}
    with open(os.path.join(package_root, relative_path)) as version_fp:
        exec(version_fp.read(), version)
        return version["__version__"]


with open("README.md", "r", encoding="utf-8") as readme:
    long_description = readme.read()

setup(
    name="midea-beautiful-air",
    version=get_version("midea_beautiful/version.py"),
    url="https://github.com/nbogojevic/midea-beautiful-air",
    author="Nenad Bogojević",
    author_email="nenad.bogojevic@gmail.com",
    license="MIT",
    description=("A library to control Midea appliances via the local network"),
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.8",
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Topic :: Home Automation",
    ],
    entry_points="""
        [console_scripts]
        midea-beautiful-air-cli=midea_beautiful.cli:cli
    """,
    install_requires=["cryptography>=3.0", "requests>=2.0"],
)
