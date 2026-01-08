"""
IO Board Communication Library Setup
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_path = Path(__file__).parent / 'README.md'
long_description = ""
if readme_path.exists():
    long_description = readme_path.read_text(encoding='utf-8')

setup(
    name='io_board',
    version='1.0.0',
    author='CRK',
    author_email='',
    description='IO Board Serial Communication Library for Nvidia Jetson Orin',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='',
    license='MIT',

    # Package configuration
    package_dir={'': 'src'},
    packages=find_packages(where='src'),
    python_requires='>=3.8',

    # Dependencies
    install_requires=[
        'pyserial>=3.5',
        'pyyaml>=6.0',
    ],

    # Optional dependencies
    extras_require={
        'dev': [
            'pytest>=7.0',
            'pytest-cov>=4.0',
            'black>=23.0',
            'mypy>=1.0',
            'types-pyserial>=3.5',
        ],
    },

    # Entry points (optional CLI commands)
    entry_points={
        'console_scripts': [
            'io-board-test=io_board.scripts.test_connection:main',
        ],
    },

    # Classifiers
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Operating System :: POSIX :: Linux',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: System :: Hardware',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],

    # Keywords
    keywords='io-board serial communication jetson orin loadcell deadbolt',
)
