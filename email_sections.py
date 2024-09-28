import re
import sys
import base64
from logging import Logger
from bs4 import BeautifulSoup
from typing import Any, Dict, List, Union
from googleapiclient.errors import HttpError
from .exceptions import non_empty_string, non_empty_dict
from .utils import extract_email_address, clean_text, null_logger
from .compiled_regexes import HTTP_HTTPS_URL, DETAILED_LINK, BASIC_LINK


"""
This module provides functions for extracting different sections of an email message, such as links, headers, recipients, and more. 
The main functionalities of the module are outlined below:
"""

def links_detailed(links: List[str], logger: Logger = null_logger()) -> List[str]:
    """
    Extracts unique URLs from a list of strings that may contain multiple links.

    This function uses a regular expression to identify and return a list of URLs 
    that start with 'http://' or 'https://' or www. Only unique URLs are returned.

    Parameters:
    links (List[str]): A list of strings where each string may contain multiple links.

    Returns:
    List[str]: A list of unique URLs matching the specified pattern. If no valid URLs 
               are found, an empty list is returned.

    Raises:
    TypeError: If the 'links' parameter is not a list of strings.
    ValueError: If there is an error in the regular expression.
    """

    logger.info("Preparing detailed links.")

    if not isinstance(links, list):
        logger.exception(f"Invalid detailed links type. Expected list of str, got {type(links)}")
        raise TypeError(f"Detailed links must be a list of str, got {type(links)}")
    
    if not all(isinstance(link, str) for link in links):
        logger.exception(f"Invalid detailed link type. Expected str, got {type(links)}")
        raise TypeError(f"Invalid detailed link type. Expected str, got {type(links)}")

    unique_links = set()

    logger.debug(f"Found {len(links)} detailed link(s).")

    try:
        for link in links:
            matches = DETAILED_LINK.findall(link)
            unique_links.update(matches)

        logger.debug(f"Unique detailed link(s): {len(unique_links)}")
        return list(unique_links)
    
    except re.error as e:
        logger.exception(f"Invalid regular expression pattern found in detailed link: {e}")
        raise ValueError(f"Invalid regular expression pattern found in detailed link: {e}") from e


def links_basic(links: List[str], logger: Logger = null_logger()) -> List[str]:
    """
    Extracts unique domain links from a list of strings.

    This function matches URLs starting with 'http://' or 'https://' and extracts only 
    the domain part (i.e., up to the first slash after the domain).

    Parameters:
    links (List[str]): A list of strings where each string may contain multiple links.

    Returns:
    List[str]: A list of unique domain URLs. If no valid URLs are found, an empty list is returned.

    Raises:
    TypeError: If the 'links' parameter is not a list of strings.
    ValueError: If there is an error in the regular expression.
    """
    
    logger.info("Preparing basic links.")

    if not isinstance(links, list):
        logger.exception(f"Invalid basic links type. Expected list of str, got {type(links)}")
        raise TypeError(f"Invalid basic links type. Expected list of str, got {type(links)}")
    
    if not all(isinstance(link, str) for link in links):
        logger.exception(f"Invalid basic link type. Expected str, got {type(links)}")
        raise TypeError(f"Invalid basic link type. Expected str, got {type(links)}")
    
    unique_domains = set()
    logger.debug(f"Found {len(links)} basic link(s).")

    try:
        for link in links:
            matches = BASIC_LINK.findall(link)
            unique_domains.update(matches)

        logger.debug(f"Unique basic link(s): {len(unique_domains)}")
        return list(unique_domains)

    except re.error as e:
        logger.exception(f"Invalid regular expression pattern found in basic link: {e}")
        raise ValueError(f"Invalid regular expression pattern found in basic: {e}") from e


def add_links(links: List[str], link_type: str, message_template: Dict, logger: Logger = null_logger()) -> Dict:
    """
    Includes links in the given message template based on the specified link type.

    Parameters:
    links (List[str]): A list of strings representing links.
    link_type (str): The type of links to be included, either 'detailed' or 'selected'.
    message_template (Dict): A dictionary representing the message template. Must contain 
                             a 'links' key with 'href' and 'number' keys.

    Returns:
    Dict: The updated message template with the included links and their count.

    Raises:
    TypeError: If 'links' is not a list of strings.
    ValueError: If 'link_type' is not valid ('detailed' or 'selected').
    EmailSectionKeyException: If required keys are missing in the message_template.
    EmailSectionUnexpectedException: If any other unexpected error occurs.
    """
    
    logger.debug("Adding links.")

    try:
        non_empty_string(link_type)
        method = getattr(sys.modules[__name__], link_type, None)

        if callable(method):
            message_template["links"]["href"] = method(links, logger)
            message_template["links"]["number"] = len(message_template["links"]["href"])

        logger.debug(f"Added {message_template['links']['number']} link(s)")
        return message_template
    except KeyError as e:
        logger.exception(f"Missing key in message_template: {e}")
        raise KeyError(f"Missing key in message_template: {e}") from e
    except Exception as e:
        logger.exception(f"Unexpected exception while adding links: {e}")
        raise Exception(f"Unexpected exception while adding links: {e}") from e
    

def get_headers(message: Dict, logger: Logger = null_logger()) -> Dict:
    """
    Retrieves headers from a given message dictionary.

    This function checks if the 'payload' key exists in the message dictionary. If it does, it further checks if the 
    'headers' key exists within the 'payload' dictionary and returns it. If 'payload' does not exist but 'headers' 
    do, it returns the 'headers' directly from the message dictionary.

    Parameters:
    message (Dict): A dictionary representing a message, which may contain 'payload' and/or 'headers' keys.

    Returns:
    Dict: A dictionary containing the headers. Returns an empty dictionary if no headers are found.

    Raises:
    TypeError: If 'message' is not a dictionary.
    KeyError: If the 'headers' key is not found within 'payload' or the top level of the message dictionary.
    """
    logger.debug("Retrieving headers.")

    if not isinstance(message, dict):
        logger.exception(f"Message should be a dictionary, got {type(message)}")
        raise TypeError(f"Message should be a dictionary, got {type(message)}")

    if 'payload' in message:
        headers = message.get('payload', {}).get('headers', {})
    else:
        headers = message.get('headers', {})

    if not isinstance(headers, dict):
        logger.exception(f"'headers' key should be a dictionary, not '{type(headers)}'")
        raise KeyError(f"'headers' key should be a dictionary, not '{type(headers)}'")

    return headers


def get_labels(service, logger: Logger = null_logger()) -> list:
    """
    Retrieves a list of labels associated with the user's account from the Gmail API.

    Parameters:
    service (Any): An instance of the Gmail API service object. This object is used to make API calls.

    Returns:
    list: A list of dictionaries representing the labels. Each dictionary contains the label's ID, name,
          labelListVisibility, and messageListVisibility. If no labels are found, an empty list is returned.

    Raises:
    Exception: If an error occurs during the API call or if the response does not contain the expected data.
    """

    logger.debug("Collecting labels from Gmail account.")

    try:
        return service.users().labels().list(userId="me").execute().get("labels", [])
    except TypeError as e:
        logger.exception(f"Invalid input for 'label_name': {e}")
        raise TypeError(f"Invalid input for 'label_name': {e}") from e
    except HttpError as e:
        logger.exception(f"HTTP error occurred while getting labels: {e}")
        raise HttpError(f"HTTP error occurred while getting labels: {e}") from e
    except TimeoutError as e:
        logger.exception(f"API call timed out while getting labels: {e}")
        raise TimeoutError(f"API call timed out while getting labels: {e}") from e
    except KeyError as e:
        logger.exception(f"Missing key in API response while getting labels: {e}")
        raise KeyError(f"Missing key in API response while getting labels: {e}") from e
    except Exception as e:
        logger.exception(f"An unexpected error occurred while getting labels: {e}")
        raise Exception(f"An unexpected error occurred while getting labels: {e}") from e

def create_visible_label(label_name: str, service: Any, logger: Logger = null_logger()) -> Any:
    """
    Creates a visible label in the user's Gmail account.
    Gmail API exceptions are verified by gmail_api_exceptions wrapper.

    Parameters:
    label_name (str): The name of the label to be created. Must be a non-empty string.
    service (Any): An instance of the Gmail API service object. This object is used to make API calls.

    Returns:
    None: The function does not return any value. However, it creates a visible label in the user's Gmail account.

    Raises:
    TypeError: If the 'label_name' parameter is not a string (raises by non_empty_string)
    ValueError: If the 'label_name' parameter is an empty string (raises by non_empty_string)
    Exception: If an error occurs during the API call or if the response does not contain the expected data.
    HttpError: If there is an error in the HTTP request or response.
    TimeoutError: If the API call times out.
    QuotaExceededError: If the API call exceeds the quota limit.
    ServiceUnavailableError: If the Gmail API service is unavailable.
    """

    logger.info("Creating visible label.")

    try:
        non_empty_string(label_name)

        label_body = {
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }
        return service.users().labels().create(userId="me", body=label_body).execute()    
    except TypeError as e:
        logger.exception(f"Invalid input for visible 'label_name': {e}") 
        raise TypeError(f"Invalid input for visible 'label_name': {e}") from e
    except HttpError as e:
        logger.exception(f"HTTP error occurred while creating visible label: {e}")
        raise HttpError(f"HTTP error occurred while creating visible label: {e}") from e
    except TimeoutError as e:
        logger.exception(f"API call timed out while creating visible label: {e}")
        raise TimeoutError(f"API call timed out while creating visible label: {e}") from e
    except KeyError as e:
        logger.exception(f"Missing key in API response while creating visible label: {e}")
        raise KeyError(f"Missing key in API response while creating visible label: {e}") from e
    except Exception as e:
        logger.exception(f"An unexpected error occurred while creating visible label: {e}") 
        raise Exception(f"An unexpected error occurred while creating visible label: {e}") from e


def create_hidden_label(label_name: str, service: Any, logger: Logger = null_logger()) -> Any:
    """
    Creates a hidden label in the user's Gmail account.
    Gmail API exceptions are verified by gmail_api_exceptions wrapper.

    Parameters:
    label_name (str): The name of the label to be created. Must be a non-empty string.
    service (Any): An instance of the Gmail API service object. This object is used to make API calls.

    Returns:
    None: The function does not return any value. However, it creates a visible label in the user's Gmail account.

    Raises:
    TypeError: If the 'label_name' parameter is not a string (raises by non_empty_string)
    ValueError: If the 'label_name' parameter is an empty string (raises by non_empty_string)
    Exception: If an error occurs during the API call or if the response does not contain the expected data.
    HttpError: If there is an error in the HTTP request or response.
    TimeoutError: If the API call times out.
    QuotaExceededError: If the API call exceeds the quota limit.
    ServiceUnavailableError: If the Gmail API service is unavailable.
    """

    logger.info("Creating hidden label.")

    try:
        non_empty_string(label_name)

        label_body = {
            "name": label_name,
            "labelListVisibility": "labelHide",
            "messageListVisibility": "hide",
        }
        return service.users().labels().create(userId="me", body=label_body).execute()
    except TypeError as e:
        logger.exception(f"Invalid input for hidden 'label_name': {e}")
        raise TypeError(f"Invalid input for hidden 'label_name': {e}") from e
    except HttpError as e:
        logger.exception(f"HTTP error occurred while creating hidden label: {e}")
        raise HttpError(f"HTTP error occurred while creating hidden label: {e}") from e
    except TimeoutError as e:
        logger.exception(f"HTTP error occurred while creating hidden label: {e}")
        raise TimeoutError(f"HTTP error occurred while creating hidden label: {e}") from e
    except KeyError as e:
        logger.exception(f"Missing key in API response while creating hidden label: {e}")
        raise KeyError(f"Missing key in API response while creating hidden label: {e}") from e
    except Exception as e:
        logger.exception(f"Unexpected error occurred while creating hidden label: {e}")
        raise Exception(f"Unexpected error occurred while creating hidden label: {e}") from e


def delete_label(label_name: str, label_id: str, service: Any, logger: Logger = null_logger()) -> bool:
    """
    Deletes a label from the user's Gmail account using the Gmail API.
    
    This function validates the input parameters and handles various exceptions that may arise during the 
    API call. If an exception occurs, it propagates it to the calling function.

    Parameters:
    label_name (str): The name of the label to be deleted. Must be a non-empty string.
                      This parameter is used for input validation and is not directly used in the API call.
    label_id (str): The ID of the label to be deleted. Must be a non-empty string.
                    This parameter is used in the API call to identify the label to be deleted.
    service (Any): An instance of the Gmail API service object. This object is used to make API calls.

    Returns:
    bool: Returns True if the label is successfully deleted.
          Returns False if the label deletion fails or if the API call does not return the expected data.

    Raises:
    TypeError: If 'label_name' or 'label_id' is not a string.
    ValueError: If 'label_name' or 'label_id' is an empty string.
    HttpError: If there is an error in the HTTP request or response.
    TimeoutError: If the API call times out.
    Exception: If an unexpected error occurs.
    """
    
    logger.info("Deleting label.")

    non_empty_string(label_name)
    non_empty_string(label_id)

    try:
        response = service.users().labels().delete(userId="me", id=label_id).execute()
        return response
    
    except HttpError as e:
        logger.exception(f"HttpError. Failed to delete label '{label_name}'")
        raise HttpError(f"Failed to delete label '{label_name}' (ID: {label_id}) due to an HTTP error: {e}") from e

    except TimeoutError as e:
        logger.exception(f"TimeoutError. Failed to delete label '{label_name}'")
        raise TimeoutError(f"API call timed out while deleting label '{label_name}' (ID: {label_id}): {e}") from e

    except Exception as e:
        logger.exception(f"Unexpected exception. Failed to delete label '{label_name}'")
        raise Exception(f"An unexpected error occurred while deleting label '{label_name}' (ID: {label_id}): {e}") from e


def email_basic_information(
    email_data: List[Dict[str, str]], message_template: Dict[str, Union[str, List[str]]], logger: Logger = null_logger()
) -> Dict[str, Union[str, List[str]]]:
    """
    This function extracts basic information from an email data dictionary and populates a message template dictionary.

    Parameters:
    email_data (List[Dict[str, str]]): A list of dictionaries representing email headers. Each dictionary contains a 'name' and 'value' key.
    message_template (Dict[str, Union[str, List[str]]]): A dictionary representing a message template. It contains keys like 'from', 'to', and 'subject'.

    Returns:
    Dict[str, Union[str, List[str]]]: The updated message template dictionary with 'from', 'to', and 'subject' fields populated from the email data.

    The function iterates through the email data and populates the 'from', 'to', and 'subject' fields in the message template based on the 'name' field.
    If the 'name' field is 'From', the function extracts the email address using the 'extract_email_address' function and populates the 'from' field in the message template.
    If the 'name' field is 'Subject', the function populates the 'subject' field in the message template.
    If the 'name' field is 'To', the function extracts the email address using the 'extract_email_address' function and populates the 'to' field in the message template.

    Raises:
    Exception:
    """

    logger.info("Collecting basic email data from headers.")

    try:
        for values in email_data:
            name = values["name"]
            if name == "From":
                message_template["from"] = extract_email_address(values["value"])
                message_template["subject"] = [
                    j["value"] for j in email_data if j["name"] == "Subject"
                ]
                logger.debug(f"message from: {message_template['from']}")
                logger.debug(f"message subject: {message_template['subject']}")
            if name == "To":
                message_template["to"] = extract_email_address(values["value"])
                logger.debug(f"message to: {message_template['to']}")
                
        return message_template
    except KeyError as e:
        logger.exception(f"Missing key while extracting basic email data: {e}")
        raise KeyError(
            f"Missing key while extracting basic email data: {e}"
        )
    except Exception as e:
        logger.exception(f"Unexpected error while extracting basic email data: {e}")
        raise Exception(f"Unexpected error while extracting basic email data: {e}")


def email_message_from_partial(
    message: dict, message_template: dict, logger: Logger = null_logger()) -> tuple:
    """
    Extracts the message content and hidden links from a partial email message.

    Parameters:
    message (dict): A dictionary representing the email message. It should contain a 'payload' key,
                    which is also a dictionary. The 'payload' dictionary should contain a 'parts' key,
                    which is a list of dictionaries representing different parts of the email message.
    message_template (dict): A dictionary representing a template for the email message. It should contain
                             a 'message' key, which is a string to store the extracted message content.
    Returns:
    tuple: A tuple containing the updated message_template dictionary and the list of extracted links.
           If the 'payload' or 'parts' key is not found in the 'message' dictionary, an empty tuple is returned.

    Raises:
    KeyError: If partial is missing 'body' or 'data' keys.
    ValueError (from non_empty_dict()): If the input is not of dict type.
    TypeError (from non_empty_dict()): If the input dict is empty.
    """

    logger.info("Collecting messages from partial.")

    non_empty_dict(message)
    links: list = []

    if "payload" not in message.keys():
        logger.debug("No 'payload' in message keys. Returning None.")
        return ({},[])

    if "parts" not in message["payload"].keys():
        logger.debug("No 'parts' in message payload keys. Returning None.")
        return ({},[])

    for part in message["payload"]["parts"]:
        if "mimeType" not in part.keys():
            logger.debug("No 'mimeType' in message payload part keys. Continue search.")
            continue
        else:
            if part["mimeType"] in ["text/plain", "text/html"]:
                try:
                    chunk = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
                    soup = BeautifulSoup(chunk, "html.parser")

                    for link in re.findall(HTTP_HTTPS_URL, chunk):
                        links.append(link) # extract hidden links
                    message = re.sub(HTTP_HTTPS_URL, "", soup.get_text())  # remove links from message
                    
                    message_template["message"] += clean_text(message)
                except KeyError as e:
                    logger.exception(f"Missing key in 'part' (partial) of email message: {e}")
                    raise KeyError(
                        f"Missing key in 'part' (partial) of email message: {e}"
                    )
    return message_template, links
