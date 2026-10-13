import pathlib

from setuptools import find_packages, setup

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
    python_requires='>=3.12',
    install_requires=['aiohttp>=3.14.5,<4', 'pydantic>=2.14.1,<3', 'SQLAlchemy>=2.1.4,<2.2'],
    extras_require={
        'mysql': ['PyMySQL>=1.2.3,<2'],
        'postgresql': ['psycopg[binary]>=3.3.6,<4'],
        'dev': [
            'pytest>=9.1.1,<10', 'ruff>=0.17.0,<1', 'pyright>=1.1.414,<2',
            'setuptools>=84.0.0,<85', 'build>=1.6.1,<2', 'wheel>=0.48.0,<1',
        ],
    },
    packages=find_packages(exclude=['examples']),
)
