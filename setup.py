from platform import python_branch
from setuptools import setup, find_packages

from midea_beautiful_dehumidifier import __version__ 

setup(
    name='midea-beautiful-dehumidifier',
    version=__version__ ,

    url='https://github.com/nbogojevic/midea-beautiful-dehumidifier',
    author='Nenad Bogojevic',
    author_email='nenad.bogojevic@gmail.com',

    packages=find_packages(),

    install_requires=[
        'pycryptodome>=3.12.0',
        "requests>=2.26.0",
    ],
)
