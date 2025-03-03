#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name="bc-crash-monitor",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "aiohttp==3.11.13",
        "python-dotenv==1.0.1",
        "psycopg2-binary==2.9.10",
        "SQLAlchemy==2.0.28",
        "pytz==2025.1",
        "alembic==1.14.1",
        "Mako==1.3.9",
        "typing_extensions==4.12.2",
    ],
    python_requires=">=3.11",
    description="A Python application that monitors BC Game's crash game",
    author="Bhaven",
    author_email="thisisbhavens@gmail.com",
)
