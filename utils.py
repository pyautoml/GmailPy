# https://github.com/pyautoml/GmailPy

import os
import re
import json
import uuid
import pickle
import base64
import logging
from pathlib import Path
from datetime import datetime
from termcolor import colored, COLORS
from compiled_regexes import EMAIL_ADDRESS
from typing import Any, Final, List, Optional
from email_enumerators import AllowedAttachment
from email_validator import validate_email, EmailNotValidError
from exceptions import ( 
    UtilsException,
    UtilsFileError,
    UtilsEmailError,
    non_empty_string,
    UtilsCallableError,
    TokenFileOpenException,
    UtilsTextFormattingError,
    TokenSerializationException,
)


"""
This module is designed to provide reusable functions that are not specific to the Google Mail API. 
Itincludes various utility functions for file handling, text formatting, email validation, and more.
"""


LOGGER_NAME: Final[str] ="GmailPy"

MIME_TYPE_MAP = {
    "image/png": AllowedAttachment.PNG.value,
    "image/jpeg": AllowedAttachment.JPEG.value,
    "image/jpg": AllowedAttachment.JPG.value,
    "image/webp": AllowedAttachment.WEBM.value,
    "application/pdf": AllowedAttachment.PDF.value,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": AllowedAttachment.XLSX.value,
    "application/xml": AllowedAttachment.XML.value,
    "text/xml": AllowedAttachment.XML.value,
}


def loglevel_mapping(log_level: str = None) -> int:
    """
    This function maps a given log level string to its corresponding logging level.

    DEBUG: Detailed information for diagnosing problems; used during development.
    INFO: General information about program execution; confirms that things are working as expected.
    WARNING: Indications of potential issues; something unexpected happened but execution is not halted.
    ERROR: Serious problems that prevent specific functionality; errors that need fixing.
    CRITICAL: Severe errors that cause a program to stop; requires immediate attention.

    Parameters:
    log_level (str, optional): The log level string to be mapped. If not provided, the default log level is logging.INFO.

    Returns:
    int: The corresponding logging level for the given log level string. If the log level string is not recognized,
    the default log level is logging.INFO.
    """

    if not log_level:
        return logging.INFO

    log_level = log_level.lower()

    if "debug" in log_level:
        return logging.DEBUG
    elif "info" in log_level:
        return logging.INFO
    elif "warn" in log_level:
        return logging.WARNING
    elif "error" in log_level:
        return logging.ERROR
    elif "critic" in log_level:
        return logging.CRITICAL
    elif "exc" in log_level:
        return logging.EXCEPTION
    else:
        return logging.INFO



class ColorFormatter(logging.Formatter):
    """
    Custom logging formatter to add colors based on log level.
    """
    
    def format(self, record):
        if record.levelname == 'DEBUG':
            record.levelname = color_message(record.levelname, color='dark_grey')
        elif record.levelname == 'INFO':
            record.levelname = color_message(record.levelname, color='light_green')
        elif record.levelname == 'WARNING':
            record.levelname = color_message(record.levelname, color='light_yellow')
        elif record.levelname == 'ERROR':
            record.levelname = color_message(record.levelname, color='blue')
        if record.levelname == 'CRITICAL':
            record.levelname = color_message(record.levelname, color='red')
        elif record.levelname == 'EXCEPTION':
            record.levelname = color_message(record.levelname, color='red')
        return super().format(record)
    

def shared_library_logger():
    return logging.getLogger(LOGGER_NAME)

def setup_console_logger(name: Optional[str] = None, level: Optional[str] = None, colored: bool = False, handler=None) -> logging.Logger:
    """
    Sets up a console logger that can propagate its settings to the entire library.
    
    Parameters:
    name (Optional[str]): The name of the logger. Defaults to None for the root logger.
    level (Optional[str]): The logging level as string that is mapped to a proper logging level.
    colored (bool): Whether to use colorized output. Defaults to False.
    handler (Optional): Custom handler. Defaults to a StreamHandler.
    
    Returns:
    logging.Logger: The configured logger.
    """

    level = loglevel_mapping(level)
    logger = logging.getLogger(LOGGER_NAME) if not name else logging.getLogger(name)
    logger.setLevel(level)

    if handler is None:
        handler = logging.StreamHandler()

    formatter = ColorFormatter('[%(asctime)s] - %(name)s - %(levelname)s - %(module)s - %(message)s') if colored else logging.Formatter('[%(asctime)s] - %(name)s - %(levelname)s - %(module)s - %(message)s')

    handler.setLevel(level)
    handler.setFormatter(formatter)

    if not logger.hasHandlers():
        logger.addHandler(handler)

    return logger


def null_logger():
    """
    Return a logger that does nothing (NullHandler) to prevent logging errors.

    This function creates a logger with the name 'null_logger' and adds a NullHandler to it.
    The NullHandler does not perform any actions, which means it does not log any messages.
    This function is useful when you want to prevent logging errors or when you want to temporarily
    disable logging for a specific part of your code.

    Returns:
    logging.Logger: A logger with a NullHandler added to it.
    """
    null_logger = logging.getLogger('null_logger')
    null_logger.addHandler(logging.NullHandler())
    return null_logger


def file_exists(file: str, silent_error: bool = False) -> str:
    """
    Check if a file exists and raise an exception if it does not.

    This function takes a file path as input and checks if the file exists. If the file does not exist,
    it raises a UtilsFileError with a descriptive error message. If the file exists, the function does nothing.

    Parameters:
    file (str): The path to the file to be checked.
    silent_error (bool): return False if file not found.

    Returns:
    str: A validated path to a file.

    Raises:
    UtilsFileError: If the file does not exist.
    UtilsException: If any other exception occurs during the file existence check.
    """

    try:
        if not os.path.exists(file):
            file = os.path.abspath(file)
            if not os.path.exists(file):
                if silent_error:
                    return False
                raise UtilsFileError(f"File '{file}' doesn't exist.")
        return file
    except (FileNotFoundError, FileExistsError) as e:
        if silent_error:
            return False
        raise UtilsFileError(f"{e}")
    except Exception as e:
        if silent_error:
            return False
        raise UtilsException(f"{e}")
    
def remove_unicode(data: str, silent_error: bool = False) -> str:
    """
    This function removes non-ASCII characters from a given string.

    Parameters:
    data (str): The input string from which to remove non-ASCII characters.

    Returns:
    str: The input string with all non-ASCII characters removed. 
    If silent_error is True and an error occurs during the removal process,
    the original string is returned.

    Raises: 
    UtilsTextFormattingError: If silent_error is False inform about error during ASCII characters removal.
    """
    try:
        cleaned_body = re.sub(r'[\u200c\u200b\xa0]+', '', data)
        return re.sub(r'[^\w\s\u00C0-\u017F]', '', cleaned_body)
    except re.error as e:
        if silent_error:
            return data
        raise UtilsTextFormattingError(f"An error occurred while removing non-ASCII characters: {e}")

def show_message_colors() -> list:
    """
    This function prints out a list of available color options from the termcolor library.
    It iterates over all the color names in the COLORS dictionary and prints out an example message
    in each color, both in normal and reversed format.

    Parameters:
    None

    Returns:
    list: A list of color names available in the COLORS dictionary.

    Raises:
    None
    """
    for color in list(COLORS.keys()):
        print(f"{color}: {colored('Example', f'{str(color)}', attrs=['blink'])}")
        print(
            f"{color} (reverse): {colored('Example', f'{str(color)}', attrs=['reverse', 'blink'])}"
        )

def color_message(message: str, color: str = "red", reverse_color: bool = True) -> str:
    """
    This function takes a message and applies a color to it using the termcolor library.
    If the provided color is not valid, it defaults to 'red'. The color can be reversed if the reverse_color flag is set to True.

    Parameters:
    message (str): The message to be colored.
    color (str): The color to apply to the message. Defaults to 'red'.
    reverse_color (bool): Whether to reverse the color. Defaults to True.

    Returns:
    str: The colored message.

    Raises:
    TypeError (from non_empty_string): If the input is not of string type.
    ValueError (from non_empty_string): If the input string is empty.
    """
    
    non_empty_string(message)

    DEFAULT_COLOR: Final[str] = "red"
    DEFAULT_REVERSE: Final[bool] = True

    if not isinstance(color, str):
        color = DEFAULT_COLOR

    if not isinstance(reverse_color, bool):
        reverse_color = DEFAULT_REVERSE

    if color.lower().strip() not in list(COLORS.keys()):
        color = DEFAULT_COLOR

    if reverse_color:
        return colored(f"{message}", f"{str(color)}", attrs=["reverse", "blink"])
    return colored(f"{message}", f"{str(color)}", attrs=["blink"])

def save_email(file_path: str, file_name: str, payload: dict, silent_error: bool = False) -> bool | None:
    """
    This function saves a given payload as a JSON file with a unique name in the specified file path.
    The file name is constructed using the provided file_name, a UUID, and a timestamp.

    Parameters:
    file_path (str): The directory path where the JSON file will be saved.
    file_name (str): The base name of the JSON file. The UUID and timestamp will be appended to this name.
    payload (dict): The data to be saved as a JSON file. If the payload is a string, it will be parsed as JSON.
    silent_error (bool): If True, the function will return False instead of raising an exception if an error occurs.
        Defaults to False.

    Returns:
    bool | None: If silent_error is True and an error occurs, the function will return False. Otherwise, it will return None.

    Raises:
    UtilsFileError: If the file does not exist.
    UtilsException: If any other exception occurs during the file existence check.
    UtilsEmailError: If silent_error is False and an error occurs while saving the JSON file.
    TypeError (from non_empty_string): If the input is not of string type.
    ValueError (from non_empty_string): If the input string is empty.
    """

    non_empty_string(file_name)
    non_empty_string(file_path)

    try:

        file_path = file_exists(file_path)

        if isinstance(payload, str):
            payload = json.loads(payload)

        timestamp = (
            str(datetime.now().replace(microsecond=0))
            .replace(":", "")
            .replace("-", "")
            .replace(" ", "")
        )

        with open(f"{file_path}/{file_name}_{uuid.uuid4().hex}_{timestamp}.json", "a+") as file:
            file.write(json.dumps(payload, indent=4))

    except (UtilsFileError, UtilsException, Exception) as e:
        if silent_error:
            return False
        raise UtilsEmailError(f"Failed to save file as json: {e}")

def save_token(token_file: str, credentials: dict) -> None:
    """
    Save and serialize a token to a file using pickle.

    Parameters:
    token_file (str): The path to the file where the token will be saved.
    credentials (dict): The token to be serialized and saved.

    Returns:
    None

    Raises:
    TokenFileOpenException: If the token file could not be opened for writing.
    TokenSerializationException: If an error occurred while serializing the token.
    TypeError (from non_empty_string): If the input is not of string type.
    ValueError (from non_empty_string): If the input string is empty.
    """

    non_empty_string(token_file)

    try:
        with open(token_file, "wb") as file:
            pickle.dump(credentials, file)

    except (UtilsFileError, UtilsException) as e:
        raise TokenFileOpenException(
            f"The token file '{token_file}' could not be opened: {e}"
        )
    except pickle.PickleError as e:
        raise TokenSerializationException(
            f"An error occurred while serializing the token: {e}"
        )


def load_token(token_file: str) -> dict|None:
    """
    Load and deserialize a token from a file using pickle.

    Parameters:
    token_file (str): The path to the file containing the token.

    Returns:
    dict: The deserialized token.

    Raises:
    TokenFileOpenException: If the token file could not be opened.
    TokenSerializationException: If an error occurred while deserializing the token.
    """
    try:

        token_file = file_exists(token_file)

        with open(token_file, "rb") as file:
            return pickle.load(file)
        
    except (UtilsFileError, UtilsException):
        return None # file might not exist yet
    except pickle.PickleError as e:
        raise TokenSerializationException(
            f"An error occurred while deserializing the token: {e}"
        )


def extract_email_address(email_headers: str) -> list:
    """
    Extracts email addresses from a given text.

    This function uses a regular expression to search for email addresses in the provided text.
    The regular expression pattern is defined in the EMAIL_ADDRESS constant.

    Parameters:
    email_headers (str): The text from which to extract email addresses. This should be a string.

    Returns:
    list: A list of email addresses found in the input text. If no email addresses are found, an empty list is returned.

    Raises:
    TypeError (from non_empty_string): If the input is not of string type.
    ValueError (from non_empty_string): If the input string is empty.
    """

    non_empty_string(email_headers)
    return re.findall(EMAIL_ADDRESS, email_headers)


def validate_email_(email: str) -> bool:
    """
    Validates if a given email address is valid or not.

    This function uses the `validate_email` function from the `email_validator` library to validate the email address.
    It checks if the email address is not empty and if it is a valid email address according to the email validation rules.

    Parameters:
    email (str): The email address to be validated.

    Returns:
    bool: True if the email address is valid, False otherwise.

    Raises:
    TypeError (from non_empty_string): If the input is not of string type.
    ValueError (from non_empty_string): If the input string is empty.
    """

    non_empty_string(email)

    try:
        validate_email(email)
        return True
    except EmailNotValidError:
        return False


def validate_bulk_emails(emails: List[str], skip_invalid_emails: bool = True) -> List[str] |  None:
    """
    Validates a list of email addresses using the `validate_email` function.

    Parameters:
    - emails (List[str]): A list of email addresses to be validated.
    - skip_invalid_emails (bool): If True, only valid emails will be returned. If False, an exception will be raised
      for invalid emails. Defaults to True.

    Returns:
    - List[str]: A list of valid email addresses if `skip_invalid_emails` is True.
    - None: If all emails are valid and `skip_invalid_emails` is False.

    Raises:
    - UtilsEmailError: If invalid emails are found and `skip_invalid_emails` is False.
    """

    if not emails:
        return []

    valid_emails, invalid_emails = [], []

    for email in emails:
        try:
            validate_email(email)
            valid_emails.append(email)
        except Exception:
            invalid_emails.append(email)

    if invalid_emails:
        if skip_invalid_emails:
            return valid_emails
        raise UtilsEmailError(f"Found {len(invalid_emails)} invalid email(s).")

    return valid_emails if skip_invalid_emails else None


def clean_text(text: str) -> str:
    """
    This function cleans a given text by removing specific patterns and replacing them with empty strings.

    Parameters:
    text (str): The input text to be cleaned.

    Returns:
    str: The cleaned text with the specified patterns removed.

    Raises:
    UtilsTextFormattingError: If an error occurs during the cleaning process.
    """

    if not text:
        return text
    
    if not isinstance(text, str):
        raise TypeError(f"Input for clearing Unicode must be a string, but received '{type(text).__name__}' instead.")
    
    try:
        cleaned_text = re.sub(r'(\r\n|\n|\r){2,}', '\n', text)
        cleaned_text = re.sub(r'[\u2000-\u200F\u2028\u2029\u202A-\u202F]', '', cleaned_text)
        return cleaned_text.strip()
    except Exception as e:
        raise UtilsTextFormattingError(f"{e}")


def exec_callable(name: str, arguments: Optional[dict] = {}) -> None:
    """
    This function executes a callable object with the given name and arguments.

    Note:
    This function uses the globals().get() method to retrieve the callable object by its name. It then checks if the retrieved
    object is callable using the callable() function. If both conditions are met, the function will execute the callable object
    with the provided arguments using the **arguments syntax. If an error occurs during execution, the function will catch the
    exception and return a dictionary with an "Error" key containing a message indicating the unknown function.

    Parameters:
    name (str): The name of the callable object to be executed. The function will search for this name in the global scope.
    arguments (Optional[dict]): A dictionary containing the arguments to be passed to the callable object. Optional.

    Returns:
    None

    Raises:
    UtilsCallableError: If an error occurs during the execution of the callable object.
    """

    non_empty_string(name)
    
    try:
        func = globals().get(name)
        if callable(func):
            return func(**arguments)
    except (NameError, TypeError) as e:
        raise UtilsCallableError(f"{e}")


def abspath(file: str = None) -> Path:
    """
    This function returns the absolute path of a given file or directory. If no file is provided,
    it returns the absolute path of the directory containing the current script.

    Parameters:
    file (str): The file or directory for which to return the absolute path. If not provided,
        the function will return the absolute path of the current script's directory.

    Returns:
    pathlib.Path: The absolute path of the file or directory. If no file is provided,
        the function will return the absolute path of the current script's directory.
    """
    if not file:
        return Path(os.path.abspath(os.path.join(os.path.dirname(__file__)))).as_posix()
    return (
        Path(os.path.abspath(os.path.join(os.path.dirname(__file__)))).as_posix()
        + "/" + Path(f"{file}").as_posix()
    )


def verify_limit(limit: int|None) -> None|int:
    """
    This function verifies and returns a valid limit value.

    Parameters:
    limit (int|None): The limit value to be verified. If the limit is not provided (None),
        the function will return None. If the limit is not an integer, the function
        will return a default limit value of 10. If the limit is less than or equal to 0,
        the function will return a default limit value of 10.

    Returns:
    None|int: The verified limit value. If the limit is not provided (None),
        the function will return None. If the limit is not an integer or less than or equal to 0,
        the function will return a default limit value of 10.
    """

    if not limit:
        return None
    
    if not isinstance(limit, int):
        return 10
    
    if limit <= 0:
        return 10
    
    return limit

def indent(data: dict) -> str:
    """
    This function takes a dictionary as input and returns a string with the dictionary's contents
    formatted with indentation.

    Parameters:
    data (dict): The input dictionary to be formatted. The function checks if the input is a dictionary.
        If the input is not a dictionary, it raises a TypeError.

    Returns:
    str: A string with the input dictionary's contents formatted with indentation. The function uses
        the json.dumps() method with the 'indent' parameter set to 4 to achieve the desired indentation.
    """
    if not data:
        raise ValueError("Indentaion error. Dict data to dump cannot be empty.")
    if not isinstance(data, dict):
        return TypeError(f"Required dict type, not '{type(data)}'.")
    return json.dumps(data, indent=4)


def generate_timestamp() -> str:
    return str(datetime.now().replace(microsecond=0)).replace(":","").replace(" ","").replace("-","")


def save_local_attachment(file_path: str, part: Any, attachment_data: Any, mime_type: str, silent_error: bool = False) -> bool:
    """
    This function saves a local copy of an email attachment.

    Parameters:
    file_path (str): The directory path where the attachment will be saved.
    part (Any): The email part containing the attachment information.
    attachment_data (Any): The data of the attachment to be saved.
    silent_error (bool): return False if downloading failed, else raise an exception.

    Returns:
    bool: True if successful, else False.

    Raises:
    UtilsFileError: If silent_error=False, when error occurs while saving the attachment.
    """
    try:
        file_path = f"{file_path}/{part['filename'].split(".")[-1]}"

        if not os.path.exists(file_path):
            file_path = abspath(file_path)
            if not os.path.exists(file_path):
                os.makedirs(file_path, mode=0o755)
        
        file_path = os.path.join(file_path, f"{generate_timestamp()}_{part['filename']}")
        
        with open(file_path, "wb") as f:
            f.write(base64.urlsafe_b64decode(attachment_data))
        return True
    except Exception as e:
        if silent_error:
            return False
        raise UtilsFileError(f"Failed to locally save attachment(s): {e}")


def is_attachment_allowed(mime_type: str) -> bool:
    """
    Check if the MIME type is allowed based on predefined rules.

    Parameters:
    mime_type (str): The MIME type of the attachment.
    part (Any): The email part containing the attachment information.

    Returns:
    bool: True if the MIME type is allowed, False otherwise.

    Raises:
    None
    """

    try:
        mime_type = mime_type.split(';')[0].strip()

        if not mime_type:
            return False

        file_extension = MIME_TYPE_MAP.get(mime_type)
        if file_extension:
            return True
        return False
    except IndexError:
        # if mime_type not available or not recognizable, skip it
        return False
