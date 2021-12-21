import os

from setuptools import find_packages, setup


def read(rel_path: str) -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    # intentionally *not* adding an encoding option to open, See:
    #   https://github.com/pypa/virtualenv/issues/201#issuecomment-3145690
    with open(os.path.join(here, rel_path)) as fp:
        return fp.read()


def get_version(relative_path: str) -> str:
    package_root = os.path.abspath(os.path.dirname(__file__))
    version = {}
    with open(os.path.join(package_root, relative_path)) as version_fp:
        exec(version_fp.read(), version)
        return version['__version__']


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="midea-beautiful-dehumidifier",
    version=get_version("midea_beautiful_dehumidifier/version.py"),
    url="https://github.com/nbogojevic/midea-beautiful-dehumidifier",
    author="Nenad Bogojević",
    author_email="nenad.bogojevic@gmail.com",
    license="MIT",
    description=(
        "A library to control Midea dehumidifiers"
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
