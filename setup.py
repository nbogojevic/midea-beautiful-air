import os

from setuptools import find_packages, setup


def read(rel_path: str) -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    # intentionally *not* adding an encoding option to open, See:
    #   https://github.com/pypa/virtualenv/issues/201#issuecomment-3145690
    with open(os.path.join(here, rel_path)) as fp:
        return fp.read()


def get_version(rel_path: str) -> str:
    for line in read(rel_path).splitlines():
        if line.startswith("__version__"):
            # __version__ = "0.9"
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    raise RuntimeError("Unable to find version string.")


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="midea-beautiful-dehumidifier",
    version=get_version("midea_beautiful_dehumidifier/__version__.py"),
    url="https://github.com/nbogojevic/midea-beautiful-dehumidifier",
    author="Nenad Bogojevic",
    author_email="nenad.bogojevic@gmail.com",
    license="MIT",
    description=(
        "A library to control Midea Dehumidifiers"
        " via the Local area network"
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Topic :: Home Automation",
    ],
    install_requires=[
        "cryptography>=3.4",
        "requests>=2.25.1",
        "ifaddr>=0.1.7",
    ],
)
