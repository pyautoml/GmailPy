# https://github.com/pyautoml/GmailPy

import re

"""This module stores precompiled regexes."""

# find email addresses in a string
BASIC_LINK = re.compile(r"https?://[^/]+")
DETAILED_LINK = re.compile(r"https?://[^\s]+")
EMAIL_ADDRESS = re.compile(r"[\w\.-]+@[\w\.-]+")
HTTP_HTTPS_URL = re.compile(r"(?:https?://|www\.)\S+")