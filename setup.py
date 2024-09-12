from os import path
from setuptools import setup, find_packages

"""
A clear overview of the package's purpose and its target audience, 
making it easier for users to understand what the package is intended for.

Please report all bugs & errors.
"""


working_directory = path.abspath(path.dirname(__file__))

try:
    with open(path.join(working_directory, 'README.md'), 'r', encoding="utf-8") as f:
        long_description = f.read()
except (FileNotFoundError, IOError):
    long_description = "It looks like README.md file is missing. Pleaase report it to: pyautoml@outlook.com"
    

setup(
    name="private_gmail",
    version="0.1.0",
    author="Gabriel Rodewald",
    author_email="pyautoml@outlook.com",
    url="https://github.com/pyautoml/",
    license="MIT",
    description="GmailPy API Wrapper in Python for private Gmail mailbox.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[
        "bs4==0.0.2",
        "email-validator==2.2.0",
        "google-api-core==2.19.2",
        "google-api-python-client==2.144.0",
        "google-auth==2.34.0",
        "google-auth-httplib2==0.2.0",
        "google-auth-oauthlib==1.2.1",
        "googleapis-common-protos==1.65.0",
        "setuptools==74.0.0",
        "termcolor==2.4.0",
        "setuptools==74.0.0",
        "wheel==0.44.0"
    ]
)