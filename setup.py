#!/usr/bin/env python
import pathlib

from setuptools import setup, find_packages

here = pathlib.Path(__file__).parent.resolve()
long_description = (here / "README.md").read_text(encoding="utf-8")

setup(
    name='code-simplify',
    version='1.2.4',
    description='A python tool library that covers a wide range of common tools to simplify your work and reduce '
                'repetitive code.',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Yaocool/code-simplify",
    keywords="python, http utils, logger utils",
    author='Ozzy',
    author_email='ozzycharon@gmail.com',
    license='MIT',
    install_requires=['aiohttp', 'pydantic', 'SQLAlchemy'],
    packages=find_packages(exclude=['examples']),
)
