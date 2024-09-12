# https://github.com/pyautoml/GmailPy

import inspect
from functools import wraps
from googleapiclient.errors import HttpError


"""
This module contains custom exception classes for handling various errors and exceptions related to the Gmail API, token management, 
and utility functions.

[Links]: Gmail API Python exceptions: https://googleapis.github.io/google-api-python-client/docs/epy/googleapiclient-module.html
"""


# ---------------
# token
# ---------------
class TokenSaveException(Exception):
    """Custom exception class for token save operations."""

    def __init__(self, message: str) -> None:
        """
        Initializes the exception with a custom error message.

        Parameters:
        message (str): The error message associated with the exception.

        Returns:
        None
        """
        self.message = message

    def __str__(self) -> str:
        """
        Returns a string representation of the exception.

        Parameters:
        None

        Returns:
        str: The error message associated with the exception.
        """
        return f"Error saving token: {self.message}"


class TokenFileOpenException(TokenSaveException):
    """
    Custom exception class for token file open operations.
    Inherits from TokenSaveException.
    """
    pass


class TokenSerializationException(TokenSaveException):
    """
    Custom exception class for token serialization operations.
    Inherits from TokenSaveException.
    """
    pass


# ---------------
# Gmail
# ---------------
class GmailServiceError(Exception):
    """Base exception for GmailService errors."""

    def __init__(self, message: str) -> None:
        """
        Initializes the exception with a custom error message.

        Parameters:
        message (str): The error message associated with the exception.

        Returns:
        None
        """
        self.message = message

    def __str__(self) -> str:
        """
        Returns a string representation of the exception.

        Parameters:
        None

        Returns:
        str: The error message associated with the exception.
        """
        return f"{self.message}"
    

class GmailSetupError(GmailServiceError):
    """Custom exception class for gmail service setup errors."""
    pass


class GmailHttpError(GmailServiceError):
    """Custom exception class for gmail service HTTP errors."""
    pass


class GmailApiCallTimeoutError(GmailServiceError):
    """Custom exception class for gmail service Api Call errors."""
    pass


class GmailEmailError(GmailServiceError):
    """
    Custom exception class for gmail service email errors.
    This exception is raised when there are issues with email addresses, such as empty or invalid addresses.
    """
    pass

class GmailPayloadError(GmailServiceError):
    """Custom exception class for gmail service Payload errors."""
    pass

class GmailInstanceError(GmailServiceError):
    """Custom exception class for gmail service Payload errors."""
    pass


class GmailEncodingError(GmailEmailError):
    """Custom exception class for email encoding errors."""
    pass


# ---------------
# utils
# ---------------
class UtilsException(Exception):
    """Custom exception class for utils methods."""

    def __init__(self, message: str) -> None:
        """
        Initializes the exception with a custom error message.

        Parameters:
        message (str): The error message associated with the exception.

        Returns:
        None
        """
        self.message = message

    def __str__(self) -> str:
        """
        Returns a string representation of the exception.

        Parameters:
        None

        Returns:
        str: The error message associated with the exception.
        """
        return f"Error saving token: {self.message}"


class UtilsFileError(UtilsException):
    """
    Custom exception class for utils file check (open/find) operations.
    Inherits from UtilsException.
    """
    pass

class UtilsCallableError(UtilsException):
    """
    Custom exception class for handling errors related to callable objects in the utils module.
    This exception is raised when a callable object is expected but not found or when an error 
    occurs during the execution of the callable object.
    """
    pass

class UtilsTextFormattingError(UtilsException):
    """
    Custom exception class for handling errors related to callable objects in the utils module.
    This exception is raised when a callable object is expected but not found or when an error 
    occurs during the execution of the callable object.
    """
    pass

class UtilsEmailError(UtilsException):
    """Custom exception class for handling errors related to email addresses in the utils module."""
    pass

# ---------------
# method based
# ---------------
def gmail_api_exceptions(func):
    """
    A decorator function that wraps around a Gmail API function and handles specific exceptions.

    Parameters:
    func (function): The Gmail API function to be decorated.

    Returns:
    function: The decorated function that handles exceptions.

    Raises:
    GmailHttpError: If an HTTP error occurs during the API call.
    GmailApiCallTimeoutError: If the API call times out.
    GmailPayloadError: If a key is missing in email/data payload.
    GmailServiceError: If an unhandled exception occurs during the API call.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            if inspect.ismethod(func):
                instance = args[0]
                return func(instance, *args[1:], **kwargs)
            else:
                return func(*args, **kwargs)
        except HttpError as e:
            raise GmailHttpError(f"HTTP error occurred: {e}")
        except KeyError as e:
            raise GmailPayloadError(f"Missing key in data: {e}")
        except TimeoutError as e:
            raise GmailApiCallTimeoutError(f"API call timed out: {e}")
        except GmailSetupError as e:
            raise GmailSetupError(f"Setup error: {e}")
        except Exception as e:
            raise GmailServiceError(f"General error: {e}")
    return wrapper


def non_empty_string(string: str) -> None:
    """
    This function checks if the input string is not empty and of string type.

    Parameters:
    string (str): The input string to be checked.

    Returns:
    None: If the input string is not empty and of string type.

    Raises:
    TypeError: If the input is not of string type.
    ValueError: If the input string is empty.
    """
    if not isinstance(string, str):
        raise TypeError("This parameter must be a string type.")

    if not string:
        raise ValueError("String parameter value cannot be empty.")


def non_empty_dict(dictionary: dict) -> None:
    """
    This function checks if the input dict is not empty and of dict type.

    Parameters:
    dictionary (dict): The input dict to be checked.

    Returns:
    None: If the input dict is not empty and of dict type.

    Raises:
    TypeError: If the input is not of dict type.
    ValueError: If the input dict is empty.
    """
    if not isinstance(dictionary, dict):
        raise TypeError("This parameter must be a dict type.")

    if not dictionary:
        raise ValueError("Dict parameter value cannot be empty.")
