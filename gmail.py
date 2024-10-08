# https://github.com/pyautoml/GmailPy

import sys
import json
import base64
import logging
from collections import deque
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from ratelimit import limits, sleep_and_retry
from googleapiclient.discovery import Resource
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from typing import Generator, Final, List, Optional
from google_auth_oauthlib.flow import InstalledAppFlow

# custom
from gmailpy.email_tracker import TrackedEmail
from gmailpy.email_enumerators import (
    LabelType, 
    LinksType
)
from gmailpy.exceptions import (
    GmailHttpError,
    UtilsFileError,
    UtilsException,
    GmailSetupError,
    GmailEmailError,
    non_empty_string, 
    GmailPayloadError,
    GmailServiceError,
    GmailInstanceError,
    gmail_api_exceptions,
    TokenFileOpenException,
    GmailApiCallTimeoutError,
    TokenSerializationException
)
from gmailpy.utils import (
    clean_text,
    save_token, 
    load_token,
    file_exists,
    null_logger,
    verify_limit,
    color_message,
    remove_unicode,
    validate_email_,
    validate_bulk_emails,
    setup_console_logger,
    save_local_attachment,
    is_attachment_allowed
)
from gmailpy.email_sections import (
    add_links,
    get_labels,
    create_visible_label,
    create_hidden_label,
    delete_label,
    email_basic_information,
    email_message_from_partial,
)


"""
This module is designed to interact with the Gmail API and perform various operations such as creating, sending, deleting, and moving emails. 
It also provides functionalities for managing labels, drafts, and email threads.

It is organized into several sections, including imports, constants, classes, and functions. 
The main functionalities are implemented within the Gmail class, which serves as the primary interface for interacting with the Gmail API.

The Gmail class has the following key features:
    -   initializes the Gmail API service using the provided credentials and token file,
    -   provides methods for creating, sending, deleting, and moving emails, as well as managing labels, drafts, and email threads,
    -   includes error handling mechanisms to handle potential exceptions that may occur during API calls,
    -   provides functionalities for extracting custom email data, such as sender, recipient, subject, and message body, 
        from the retrieved email messages
    -   allows for custom filtering of email messages based on specified criteria,
    -   supports storing email headers and providing options for storing additional email data, such as links and attachments,
    -   provides a mechanism for tracking the status of processed email messages, such as whether they have been successfully sent or deleted.
"""

MAX_API_CALLS: int = 3
API_AWAIT_PERIOD: int = 10
LOGGER_NAME: Final[str] ="GmailPy"


class GmailService:
    """
    This is a simple connector to a Gmail mailbox from a localhost application.
    It will be supported by additional security classes responsible for
    validating email metadata and generating analytical reports.
    """

    SETUP_KEYS: Final[list] = ["token_file", "credentials_file", "scopes"]

    def __init__(
            self, 
            setup: dict, 
            logger: logging.Logger = None, # can be raplaced by your custom logger
            log_level: str = None,
            colored_logs: bool = True,
            max_api_calls: int = None, 
            api_await_period: int = None
        ) -> None:
        """
        Initialize a Gmail API client with the provided setup parameters.

        Parameters:
        setup (dict): A dictionary containing the necessary setup parameters for the Gmail API client.
            It should include the following keys:
            - 'token_file': The path to the token file.
            - 'credentials_file': The path to the credentials file.
            - 'scopes': A string containing the scopes for the Gmail API client, separated by commas.
            - 'protected_labels': A string containing the protected labels, separated by commas.
        max_api_calls (int): Limits max api calls per method. Overwrites global variable MAX_API_CALLS. None by default.
        api_await_period (int): Time gap between renewed api calls. Overwrites global variable API_AWAIT_PERIOD. None by default.
        logger (logging.Logger): Your custom logger. None by default.
        log_level (str): If logger is used, specify logging level. None by default.

        Raises:
        GmailSetupError: If the 'setup' parameter is not a dictionary.
        GmailSetupError: If the 'setup' parameter is an empty dictionary or if any required setup parameters are missing.
        """
                
        if logger:
            self.logger = logger
        elif log_level:
            setup_console_logger(level=log_level, colored=colored_logs)
            self.logger = logging.getLogger(LOGGER_NAME)
        else:
            self.logger = null_logger()

        self.__setup_verification(setup=setup)
        self.__apicall_verification(max_api_calls, api_await_period)
        self.service: Resource = self._connect()
        self._collect_labels()
        
    def __setup_verification(self, setup: dict) -> None:
        """
        This function sets up the verification process for the Gmail API.

        Parameters:
        setup (dict): A dictionary containing the necessary setup parameters.
            - token_file (str): The path to the token file.
            - credentials_file (str): The path to the credentials file.
            - scopes (str): A comma-separated string of scopes for the Gmail API.
            - protected_labels (str): A comma-separated string of protected labels.

        Returns:
        None

        Raises:
        GmailSetupError: If any of the required setup parameters are missing or invalid.
        """

        self.logger.debug("Starting setup verification.")


        if not isinstance(setup, dict):
            self.logger.exception(color_message(f"'setup' parameter must be a dict, not '{type(setup)}'"))
            if 'invalid_grant' or 'Bad Request' in f"{setup}":
                raise GmailSetupError(f"Gmail credentials error: {setup}")
            raise GmailSetupError(f"'setup' parameter must be a dict, not '{type(setup)}'")

        if not setup:
            self.logger.exception(color_message("'setup' parameter must be a non-empty dict"))
            raise GmailSetupError("'setup' parameter must be a non-empty dict")
        
        missing_keys = [k for k in self.SETUP_KEYS if k not in setup]
        if missing_keys:
            logging.exception(f"Setup configuration missing keys: {', '.join(missing_keys)} Program will shut down.")
            raise GmailSetupError(f"Setup configuration missing keys: {', '.join(missing_keys)}")
        
        del missing_keys

        try:
            self.token_file: str = setup.get("token_file")
            self.credentials_file: str = setup.get("credentials_file")
            self.__scopes: List[str] = setup.get("scopes")
            self.__labels: dict = {}
            self._emails: list = deque()
            self.__protected_labels: list = setup.get("protected_labels", None)
            
            if self.__protected_labels:
                self.__protected_labels.split(",")
            
            self.__scopes = self.__scopes.split(",")
            token_exists = file_exists(self.token_file, silent_error=True)

            if not token_exists:
                self.__create_new_token()

            self.credentials_file = file_exists(self.credentials_file)
        except (UtilsFileError, UtilsException) as e:
            logging.critical(f"File processing related error: {e}. Program will shut down.")
            logging.exception("Exception details: ")
            sys.exit(1)
        except Exception as e:
            logging.critical(f"Unexpected error occurred: {e}. Program will shut down.")
            logging.exception("Exception details: ")
            sys.exit(1)


    def __apicall_verification(self, max_api_calls: int, api_await_period: int) -> None:
        """
        This function verifies and sets the maximum number of API calls and the waiting period between API calls.
        Note:
        - The function checks if the provided parameters are positive integers.
        - If the parameters are not positive integers, the function will print a warning message and use the default values.
        - The function sets the global variables MAX_API_CALLS and API_AWAIT_PERIOD with the provided or default values.

        Parameters:
        max_api_calls (int): The maximum number of API calls allowed.
        api_await_period (int): The waiting period between API calls in seconds. 

        Returns:
        None
        """
        self.logger.debug("Verifying apicalls setup: MAX_API_CALLS and API_AWAIT_PERIOD.")

        if max_api_calls:
            if isinstance(max_api_calls, int) and max_api_calls > 0:
                global MAX_API_CALLS
                MAX_API_CALLS = max_api_calls
                self.logger.debug(f"Set up custom MAX_API_CALLS value: {MAX_API_CALLS}")
            else:
                self.logger.warning(f"'max_api_calls' must be int > 0, not '{max_api_calls}'. Using default value: '{MAX_API_CALLS}'")

        if api_await_period:
            if isinstance(api_await_period, int) and api_await_period > 0:
                global API_AWAIT_PERIOD
                API_AWAIT_PERIOD = api_await_period
                self.logger.debug(f"Set up custom API_AWAIT_PERIOD value: {API_AWAIT_PERIOD}")
            else:
                self.logger.warning(f"'api_await_period' must be int > 0, not '{api_await_period}'. Using default value: '{API_AWAIT_PERIOD}'")


    @sleep_and_retry
    @limits(calls=MAX_API_CALLS, period=API_AWAIT_PERIOD)
    @gmail_api_exceptions
    def __refresh_token(self) -> None:
        """
        Refreshes the access token for the Gmail API service.

        This function uses the refresh method provided by the google.oauth2.credentials.Credentials class
        to refresh the access token. The refreshed access token is then used to update the credentials object.

        Parameters:
        None

        Returns:
        None

        Raises:
        GmailHttpError: If an HTTP error occurs during the API call.
        GmailApiCallTimeoutError: If the API call times out.
        GmailPayloadError: If a key is missing in email/data payload.
        GmailServiceError: If an unhandled exception occurs during the API call.
        GmailInstanceError: Incorrect objects instance for Gmail API services.
        """
        self.logger.info("Refreshing token.")

        try:
            self.credentials.refresh(Request())
            save_token(self.token_file, self.credentials)
        except (GmailHttpError, GmailPayloadError, GmailApiCallTimeoutError, GmailSetupError, GmailServiceError) as e:
            logging.critical(f"Api Call exception: {e}. Program will shut down.")
            logging.exception("Exception details: ")
            sys.exit(1)

    @sleep_and_retry
    @limits(calls=MAX_API_CALLS, period=API_AWAIT_PERIOD)
    @gmail_api_exceptions
    def __create_new_token(self) -> None:
        """
        This function creates a new token for accessing the Gmail API.

        The function uses the InstalledAppFlow class from the google-auth-oauthlib library to
        authenticate the user and obtain the necessary credentials. The obtained credentials are
        stored in the self.credentials attribute.

        Parameters:
        None

        Returns:
        None

        Raises:
        GmailHttpError: If an HTTP error occurs during the API call.
        GmailApiCallTimeoutError: If the API call times out.
        GmailPayloadError: If a key is missing in email/data payload.
        GmailServiceError: If an unhandled exception occurs during the API call.
        GmailInstanceError: If the obtained credentials are not of type 'google.oauth2.credentials.Credentials'.
        """
        self.logger.info("Creating new token.")

        try:
            flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, self.__scopes)
            self.credentials = flow.run_local_server(port=0)

            self.logger.debug("Saving locally new token: token.pickle")
            save_token(self.token_file, self.credentials)
        except (GmailHttpError, GmailPayloadError, GmailApiCallTimeoutError, GmailSetupError, GmailServiceError) as e:
            logging.critical(f"Api Call exception: {e}. Program will shut down.")
            logging.exception("Exception details: ")
            sys.exit(1)
        except (TokenFileOpenException, TokenSerializationException) as e:
            logging.critical(f"{e}")
            logging.exception("Token exception: ")
            sys.exit(1)
    
        if not isinstance(self.credentials, Credentials):
            self.logger.exception(f"Credentials must be class 'google.oauth2.credentials.Credentials', not '{type(self.credentials)}'")
            raise GmailInstanceError(f"Credentials must be class 'google.oauth2.credentials.Credentials', not '{type(self.credentials)}'")

    def __check_token(self) -> None:
        """
        This function refreshes the Gmail API access token using the provided credentials.
        If the token is expired or invalid, it is refreshed using the refresh token.
        If the refresh token is not available, a new authorization flow is initiated.

        Parameters:
        None

        Returns:
        None

        Raises:
        GmailService: If an error occurs during the token refresh process.
        """
        self.logger.debug("Validating token.")
        self.credentials = load_token(self.token_file)
        if not self.credentials or not self.credentials.valid:
            try:
                if (
                    self.credentials
                    and self.credentials.expired
                    and self.credentials.refresh_token
                ):
                    self.__refresh_token()
                else:
                    self.__create_new_token()
            except Exception as e:
                self.logger.exception(f"GmailService exception: Failed to validate token: {e}")
                raise GmailService(f"{e}")


    # ----------
    # labels
    # ----------
    @property
    def _get_labels(self) -> dict:
        """
        Retrieves the dictionary of labels associated with the Gmail account.

        Parameters:
        None

        Returns:
        dict: A dictionary where keys are label names and values are label IDs.

        Raises:
        None
        """
        return self.__labels


    @sleep_and_retry
    @limits(calls=MAX_API_CALLS, period=API_AWAIT_PERIOD)
    @gmail_api_exceptions
    def _collect_labels(self) -> list:
        """
        Collects all labels associated with the Gmail account and stores them in the internal label dictionary.

        Parameters:
        None

        Returns:
        list: A list of all labels retrieved from the Gmail account.

        Raises:
        None

        Note:
        - The function retrieves all labels using the 'get_labels' function.
        - If labels are successfully retrieved, they are stored in the '__labels' dictionary with label names as keys and label IDs as values.
        - The '__labels' dictionary is then sorted alphabetically by label names.
        """

        self.logger.debug("Collecting labels.")
        all_labels = get_labels(self.service, self.logger)

        if all_labels:
            for label in all_labels:
                self.__labels[f"{label['name']}"] = label["id"]
            self.__labels = dict(sorted(self.__labels.items()))
        self.logger.debug(f"Collected {len(self.__labels)} label(s).")


    @sleep_and_retry
    @limits(calls=MAX_API_CALLS, period=API_AWAIT_PERIOD)
    @gmail_api_exceptions
    def _create_label(
        self, label_name: str, label_type: LabelType = LabelType.VISIBLE
    ) -> None:
        """
        Creates a new label in the user's mailbox.
        Note:
        - If the label with the same name already exists, it will not be created again.
        - The created label will be added to the internal label dictionary.
        - The label dictionary will be sorted after the new label is added.

        Parameters:
        label_name (str): The name of the label to be created.
        label_type (LabelType, optional): The type of the label. Defaults to LabelType.VISIBLE.

        Returns:
        None

        Raises:
        None
        """
        self.logger.info(f"Creating new label: {label_name} of type: {label_type.value}")
        non_empty_string(label_name)

        if label_name not in self._get_labels.keys():
            label: dict = (
                create_visible_label(label_name, self.service, self.logger)
                if label_type == LabelType.VISIBLE
                else create_hidden_label(self.logger)
            )
            
            if "id" in label.keys():
                self.__labels[label["name"]] = label["id"]
                self.__labels = dict(sorted(self.__labels.items()))
            else:
                self.logger.error(color_message("Warning: Failed to create label. Label should contain 'id' key. Check Gmail API Documentation to track changes."))
        else:
            self.logger.debug(f"Label: {label_name} of type: {label_type.value} already exists.")

    @sleep_and_retry
    @limits(calls=MAX_API_CALLS, period=API_AWAIT_PERIOD)
    @gmail_api_exceptions
    def _delete_label(self, label_name: str) -> bool:
        """
        Deletes a label from the user's mailbox.
        [!] WARNING: Deleting a label will automatically delete all emails assigned to that label.

        Parameters:
        label_name (str): The name of the label to be deleted. This name must match an existing label name.

        Returns:
        bool: Returns True if the label is successfully deleted. Returns False if the label does not exist or is protected.

        Raises:
        None
        """
        self.logger.info(f"Deleting label {label_name}")
        if (
            label_name in self._get_labels.keys()
            and label_name not in self.__protected_labels
        ):
            delete_label(
                label_name=label_name,
                label_id=self._get_labels[label_name],
                service=self.service,
                logger=self.logger
            )
            self.logger.debug(f"Label {label_name} deleted.")
            return True
        self.logger.debug(f"Failed to delete label {label_name}")
        return False
    

    @sleep_and_retry
    @limits(calls=MAX_API_CALLS, period=API_AWAIT_PERIOD)
    @gmail_api_exceptions
    def __download_attachments(self, message_id: str, attachment_id: str) -> str|None:
        """
        Downloads an attachment from the Gmail message.

        Parameters:
        message_id (str): The unique identifier of the Gmail message from which the attachment is to be downloaded.
        attachment_id (str): The unique identifier of the attachment to be downloaded.

        Returns:
        str: The data of the downloaded attachment.
        None: Is "data" key is not available in fetched attachment dict.

        Raises:
        GmailHttpError: If an HTTP error occurs during the API call to download the attachment.
        GmailApiCallTimeoutError: If the API call to download the attachment times out.
        GmailPayloadError: If a key is missing in the email/data payload for the attachment.
        GmailServiceError: If an unhandled exception occurs during the API call to download the attachment.
        """

        self.logger.info("Downloading attachments.")
        non_empty_string(message_id)
        non_empty_string(attachment_id)

        attachment: dict = self.service.users().messages().attachments().get(userId="me", messageId=message_id, id=attachment_id).execute()
        if "data" in attachment:
            return attachment["data"]
        self.logger.debug("Failed to find 'data' key in attachment dict.")
        return None

    def __get_attachments(
            self, 
            msg: dict, 
            message: dict, 
            return_attachments: bool = False, 
            download_path: Optional[str] = None, 
            skip_on_download_failure: bool = False,
            max_attachments_number: Optional[int] = None
        ) -> Optional[List[str]]:
        """
        Retrieves and saves attachments from a given Gmail message, checking their file types.
        If attachment file type is not in MIME_TYPE_MAP (utils.py), then the attachment won't be processed.

        Parameters:
        msg (dict): The raw message data from the Gmail API.
        message (dict): The formatted message data from the Gmail API.
        return_attachments (bool): If True, return attachments in raw format (bytes/str). False by default.
        download_path (str, optional): The path where the attachments will be saved. If not provided, attachments will not be saved.
        max_attachments_number (positive int, optional): The maximum number of attachments that can be downloaded. None (or 0) is set by default and means 'no limit'.
        skip_on_download_failure (bool): If True: If failed to download given file, continue to the next download. If False: raise exception. False by default.

        Returns:
        Optional[List[str]]: Returns a list of attachment data if attachments are found and saved successfully. Returns an empty list if no attachments are found. Returns None if no attachments are processed.

        Raises:
        GmailPayloadError: If a key is missing in the email/data payload for the attachments.
        """

        self.logger.info("Getting attachments.")
        attachments = []

        if "payload" not in msg.keys():
            self.logger.debug("Missing 'payload' key in msg keys.")
            return attachments
        
        if "parts" not in msg["payload"]:
            self.logger.debug("Missing 'parts' key in msg['payload'] keys.")
            return attachments
        
        try:
            for part in msg["payload"]["parts"]:
                count = 0

                if part.get("filename"):
                    mime_type = part.get("mimeType", "")
                    is_allowed = is_attachment_allowed(mime_type=mime_type)

                    if not is_allowed:
                        self.logger.warning(color_message(f"Attachment type '{mime_type}' excluded from processing."))
                        continue

                    attachment_id = part["body"].get("attachmentId")
                    self.logger.debug(f"Found attachment id: {attachment_id}")

                    if attachment_id:
                        attachment_data = self.__download_attachments(message["id"], attachment_id)

                        if download_path:
                            self.logger.debug(f"Download path: {download_path}")
                            save_status = save_local_attachment(file_path=download_path, part=part, attachment_data=attachment_data, mime_type=mime_type, silent_error=skip_on_download_failure)
                            self.logger.debug(f"Saved local attachment status: {save_status}") # works only if silent_error=True

                            if return_attachments:
                                attachments.append(attachment_data)
                                self.logger.debug(f"Processing attachment: {count}/{max_attachments_number if max_attachments_number else 'no limit'}")
                                count += 1
                            if max_attachments_number and count >= max_attachments_number:
                                self.logger.debug(f"Reach max attachment downloads: {count}/{max_attachments_number}")
                                break
            return attachments if return_attachments else None
        except KeyError as e:
            raise GmailPayloadError(f"Failed searching attachments. Missing key(s): {e}")
        except Exception as e:
            raise GmailPayloadError(f"Failed searching attachments: {e}")

    

    # ----------
    # emails
    # ----------
    @sleep_and_retry
    @limits(calls=MAX_API_CALLS, period=API_AWAIT_PERIOD)
    @gmail_api_exceptions
    def _create_email_draft(self, draft_message: str, sender: str=None, recipient: str=None, subject:str=None) -> str:
        """
        Creates a draft email in the user's mailbox.
        Note:
        - This function uses the 'create_draft' function from the 'email_crud' module to create a draft email.
        - The created draft email's unique identifier is returned.
        - You can verify new draft by checking: draft["id"]

        Parameters:
        draft_message (str): The content of the draft email.

        Returns:
        str: The unique identifier of the created draft email.

        Raises:
        GmailHttpError: If an HTTP error occurs during the API call.
        GmailApiCallTimeoutError: If the API call times out.
        GmailPayloadError: If a key is missing in email/data payload.
        GmailServiceError: If an unhandled exception occurs during the API call.
        """

        self.logger.debug("Creating email draft.")
        non_empty_string(draft_message)

        message = MIMEText(draft_message)
        message['to'] = recipient
        message['from'] = sender
        message['subject'] = subject if subject else "DRAFT "
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        draft_message = {
            'message': {
                'raw': raw_message
            }
        }

        draft = self.service.users().drafts().create(userId="me", body=draft_message).execute()
        self.logger.debug(f"Created draf message id: { draft['id']}")
        return draft['id']


    def _create_email(
        self, 
        sender: str,
        recipient: str,
        subject: str,
        email_message: str,
        cc: Optional[List[str]] = [],
        bcc: Optional[List[str]] = [],
        skip_invalid_emails: bool = True,
    ) -> MIMEText:
        """
        This function creates a MIMEText message with the provided sender, recipient, subject, cc, bcc, and email body.
        It also validates the email addresses and encodes the message in base64.

        Parameters:
        sender (str): The email address of the sender.
        recipient (str): The email address of the recipient.
        subject (str): The subject of the email.
        cc (Optional[List[str]]): A list of email addresses for CC recipients.
        bcc (Optional[List[str]]): A list of email addresses for BCC recipients.
        email_message (str): The content of the email.
        skip_invalid_emails (bool, optional): A flag indicating whether to skip invalid email addresses. Defaults to True.

        Returns:
        MIMEText: The encoded MIMEText message.

        Raises:
        GmailEncodingError: if any of provided email is not a valid email adddress (only if skip_invalid_emails = False) or is email is empty string.
        GmailEmailError: if any email address is not of string type.
        GmailPayloadError: If a key is missing in email/data payload.
        """

        self.logger.debug("Creating email message.")
        non_empty_string(sender)
        non_empty_string(recipient)

        if not validate_email_(sender):
            self.logger.exception(f"Invalid sender email address: {sender}")
            raise GmailEmailError(f"Invalid sender email address: {sender}")

        if not validate_email_(recipient):
            self.logger.exception(f"Invalid recipient email address: {recipient}")
            raise GmailEmailError(f"Invalid recipient email address: {recipient}")

        message = MIMEText(email_message)
        message["to"] = recipient
        message["from"] = sender
        message["subject"] = subject

        if cc:
            self.logger.debug("Adding CC recipients.")
            message["cc"] = ", ".join(
                email
                for email in set(
                    validate_bulk_emails(
                        cc, 
                        skip_invalid_emails=skip_invalid_emails,
                        warnings_on=True,
                    )
                )
            )
        if bcc:
            self.logger.debug("Adding BCC recipients.")
            message["bcc"] = ", ".join(
                email
                for email in set(
                    validate_bulk_emails(
                        bcc, 
                        skip_invalid_emails=skip_invalid_emails,
                        warnings_on=True
                    )
                )
            )
        return message
        

    def _mark_email_as_read(self, message_id: str) -> bool:
        """
        Marks an email as read by removing the 'UNREAD' label.

        Parameters:
        message_id (str): The ID of the message to modify.

        Returns:
        bool: True is successfully marked email as 'read', else False.
        """
        self.logger.debug("Marking email as 'READ'.")
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={
                    'removeLabelIds': ['UNREAD'],
                    'addLabelIds': []
                }
            ).execute()
            self.logger.debug("Email marked as 'READ'.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to mark email as 'READ': {e}")
            return False
        
    def _mark_email_as_unread(self, message_id: str) -> bool:
        """
        Marks an email as unread by removing the 'READ' label.

        Parameters:
        message_id (str): The ID of the message to modify.

        Returns:
        bool: True is successfully marked email as 'unread', else False.
        """
        self.logger.debug("Marking email as 'UNREAD'.")
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={
                    'removeLabelIds': ['READ'],
                    'addLabelIds': ['UNREAD']
                }
            ).execute()
            self.logger.debug("Email marked as 'UNREAD'.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to mark email as 'UNREAD': {e}")
            return False


    def _read_email(self, email: TrackedEmail, parse: bool = False, mark_as_read: bool = False) -> dict | str | None:
        """
        This function reads and unpacks a TrackedEmail object.

        Parameters:
        email (TrackedEmail): The TrackedEmail object to be unpacked.
        parse (bool): If True, returns a json.dumps of the unpacked email data. Default is False.
        mark_as_read (bool): If True, marks the email as read. Default is False.

        Returns:
        dict: A dictionary containing the unpacked email data.
        str: If parse = True, return a json dumps.
        None: If no email is provided.

        Raises:
        GmailEmailError: If the provided email parameter is not of type TrackedEmail.
        """

        self.logger.debug("Reading email.")

        if not email:
            self.logger.debug("No email found.")
            return  None
        
        if not isinstance(email, TrackedEmail):
            self.logger.exception(f"Email object should be of 'TrackedEmail' type, not '{type(email)}'.")
            raise GmailEmailError(f"Email object should be of 'TrackedEmail' type, not '{type(email)}'.")
        
        self.logger.debug("Unpacking email data.")
        email_data = email.unpack()

        if mark_as_read:
            self._mark_email_as_read(email.message_id)
        if parse:
            self.logger.debug("Parsing email to json str.")
            return json.dumps(email_data, indent=4)
        return email_data

    def _read_emails(self, emails: List[TrackedEmail]) -> Generator:
        """
        This function reads and unpacks a list of TrackedEmail objects.

        Parameters:
        emails (List[TrackedEmail]): A list of TrackedEmail objects to be unpacked.

        Returns:
        Generator: A generator yielding the unpacked email data from each TrackedEmail object.

        Raises:
        GmailEmailError: If the provided emails parameter is not of type List[TrackedEmail].
        """

        self.logger.debug("Reading multiple emails.")

        if not isinstance(emails, deque):
            self.logger.exception(f"Emails should be of deque['TrackedEmail'] type, not '{type(emails)}'.")
            raise GmailEmailError(f"Emails should be of deque['TrackedEmail'] type, not '{type(emails)}'.")
        
        self.logger.debug(f"Emails to yield: {len(emails)}")
        for email in emails:
            yield email.unpack()


    @sleep_and_retry
    @limits(calls=MAX_API_CALLS, period=API_AWAIT_PERIOD)
    @gmail_api_exceptions
    def _send_email(self, email: MIMEText) -> str:
        """
        Sends a MIMEText message to the user's mailbox.

        Parameters:
        email (MIMEText): The email to be sent.

        Returns:
        str: The unique identifier of the sent message.

        Raises:
        GmailHttpError: If an HTTP error occurs during the API call.
        GmailApiCallTimeoutError: If the API call times out.
        GmailPayloadError: If a key is missing in email/data payload.
        GmailServiceError: If an unhandled exception occurs during the API call.
        """

        self.logger.debug("Preparing email to send.")

        if not isinstance(email, MIMEText):
            self.logger.exception(f"Email body must be MIMEText type, not '{type(email)}'.")
            raise GmailEmailError(f"Email body must be MIMEText type, not '{type(email)}'.")

        raw_message = base64.urlsafe_b64encode(email.as_bytes()).decode()
        body = {'raw': raw_message}
        message = self.service.users().messages().send(userId="me", body=body).execute()
        self.logger.info(f"Sent email message id: {message['id']}")
        return message["id"]
    
    @sleep_and_retry
    @limits(calls=MAX_API_CALLS, period=API_AWAIT_PERIOD)
    @gmail_api_exceptions
    def _delete_email(self, email: TrackedEmail) -> str:
        """
        This method deletes the email (it won't be move to Trash, but deleted instantly).

        Parameters:
        email (str|TrackedEmail): The ID of the email message or the email object to be moved to the Trash folder.

        Returns:
        str: The unique identifier of the deleted message.

        Raises:
        GmailHttpError: If an HTTP error occurs during the API call.
        GmailApiCallTimeoutError: If the API call times out.
        GmailPayloadError: If a key is missing in email/data payload.
        GmailServiceError: If an unhandled exception occurs during the API call.
        """

        if not email:
            return None

        if not isinstance(email, TrackedEmail):
            self.logger.exception(f"Email must be a TrackedEmail object, not '{type(email)}'")
            raise ValueError(f"Email must be a TrackedEmail object, not '{type(email)}'")
        
        message_id = dict(email.unpack())["id"]
        self.service.users().messages().delete(userId="me",id=message_id).execute()
        self.logger.debug(f"Deleted email of id: {message_id}")
        return message_id


    @sleep_and_retry
    @limits(calls=MAX_API_CALLS, period=API_AWAIT_PERIOD)
    @gmail_api_exceptions
    def _empty_trash(self) -> bool:
        """
        Deletes all emails in the Trash folder.

        This function retrieves all emails with the 'TRASH' label from the Gmail API,
        and then deletes each email individually. If there are no emails in the Trash folder,
        the function returns True without any action.

        Parameters:
        None

        Returns:
        bool: True if all emails in the Trash folder are successfully deleted, or if there are no emails in the Trash folder.

        Raises:
        GmailHttpError: If an HTTP error occurs during the API call.
        GmailApiCallTimeoutError: If the API call times out.
        GmailPayloadError: If a key is missing in email/data payload.
        GmailServiceError: If an unhandled exception occurs during the API call.
        """

        self.logger.debug("Deleting all emails from Trash.")

        response = (
            self.service.users().messages().list(userId="me", labelIds=["TRASH"]).execute()
        )
        messages = response.get("messages", [])

        if not messages:
            self.logger.debug("No messages found in Trash.")
            return True

        self.logger.debug(f"Number of messages to delete from Trash: {len(messages)}")
        for message in messages:
            self.service.users().messages().delete(userId="me", id=message["id"]).execute()

        self.logger.debug("Deleted all messages from Trash.")
        return True
    
    @sleep_and_retry
    @limits(calls=MAX_API_CALLS, period=API_AWAIT_PERIOD)
    @gmail_api_exceptions
    def _move_to_folder(
        self, current_label_name: str, destination_label_name: str, message_id: str
    ) -> bool:
        """
        Move email from one folder to another. If destination folder doesn't exist, create it.

        Parameters:
        current_label_name (str): The name of the current label (folder) where the email is located.
        destination_label_name (str): The name of the destination label (folder) where the email will be moved.
        message_id (str): The unique identifier of the email message to be moved.

        Returns:
        bool: Returns True if the email is successfully moved to the destination folder. Returns False if there is an error.

        Raises:
        GmailHttpError: If an HTTP error occurs during the API call.
        GmailApiCallTimeoutError: If the API call times out.
        GmailPayloadError: If a key is missing in email/data payload.
        GmailServiceError: If an unhandled exception occurs during the API call.
        """

        self.logger.debug(f"Moving email of id '{message_id}' from '{current_label_name}' to '{destination_label_name}'")

        for check in [message_id, current_label_name, destination_label_name]:
            non_empty_string(check)

        if current_label_name in self.get_labels.keys():
            if destination_label_name not in self.get_labels.keys():
                self.create_label(destination_label_name)
                self.logger.debug(f"'{destination_label_name} folder created (did not exist)")

            self.service.users().messages().modify(
                userId="me",
                id=message_id,
                body={
                    "removeLabelIds": [self.get_labels[current_label_name]],
                    "addLabelIds": [self.get_labels[destination_label_name]],
                },
            ).execute()
            self.logger.debug(f"Email of if '{message_id}' successfully moved from '{current_label_name}' to '{destination_label_name}'")
            return True
        self.logger.error(f"Failed to move email of id '{message_id}' from '{current_label_name}' to '{destination_label_name}'")
        return False

    @sleep_and_retry
    @limits(calls=MAX_API_CALLS, period=API_AWAIT_PERIOD)
    @gmail_api_exceptions
    def __retrieve_emails(self, query: str = "is:unread in:inbox", filters: dict = None, max_results: int = 10, page_token: int = None, fields: str = "messages") -> List[tuple]:
        """
        Retrieves emails from the Gmail account based on the provided custom filter.
        Example return data:
            [
                {'id': '191c84f310aca74c', 'threadId': '191c84f310aca74c'},
                {'id': '191c830f05f2ffa9', 'threadId': '191c830f05f2ffa9'}
            ]

        Parameters:
        query (str): If filter is not provided, a simple query is made to set the retrieved messages scope. "is:unread in:inbox" by default.
        filters (dict, optional): A dictionary representing a custom filter to be applied to the email retrieval. Defaults to None.
        max_results (int): Maximum number of results of fetched emails. DESC by default. Set None to get all emails.
        page_token (int): Token for pagination (set to None for the first page).
        fields (str): Custom query to call specific range of messages. All returned by default.

        Returns:
        List[tuple]: A list of tuples, where each tuple represents an email with the following structure: {'id': 'email_id', 'threadId': 'email_thread_id'}.

        Raises:
        GmailHttpError: If an HTTP error occurs during the API call.
        GmailApiCallTimeoutError: If the API call times out.
        GmailPayloadError: If a key is missing in email/data payload.
        GmailServiceError: If an unhandled exception occurs during the API call.
        """

        self.logger.debug("Retrieving emails.")

        if filters:
            result = (
                self.service.users()
                .settings()
                .filters()
                .create(userId="me", body=filters)
                .execute()
            )
        else:
            result = (
                self.service.users()
                .messages()
                .list(
                    userId="me", 
                    q=query,
                    maxResults=max_results,
                    pageToken=page_token,
                    fields=fields  # 'messages' = all fields by default
                )
                .execute()
            )
        return result.get("messages", [])


    def __extract_custom_email(self, msg: dict, links_type: LinksType, store_headers: bool) -> dict:
        """
        Extracts custom email data from the provided message dictionary.

        Parameters:
        msg (dict): The message dictionary containing email data.
        links_type (LinksType): The preference for adding links to the email payload.
        store_headers (bool): A flag indicating whether to store email headers in the payload.

        Returns:
        dict: A dictionary containing the extracted custom email data.

        Raises:
        GmailPayloadError: If a key is missing in email/data payload.
        GmailServiceError: If an unhandled exception occurs during the API call.
        """

        self.logger.debug(f"Extracting emails. Links type: {links_type.value} Store headers: {store_headers}")

        try:

            if "payload" not in msg.keys():
                self.logger.error("No messages found.")
                return {}

            message_template = {
                "from": None,
                "to": None,
                "subject": None,
                "message": "",
                "links": {"number": 0, "href": []},
            }

            links: list = []

            if "headers" in msg["payload"]:
                email_data = msg["payload"]["headers"]
                message_template = email_basic_information(email_data, message_template, self.logger)
            else:
                self.logger.warning("Missing headers in email. Failed to get basic sender-recipient information")

            if "parts" in msg["payload"]:
                message_template, links = email_message_from_partial(
                    msg, message_template, self.logger
                )

            if links_type.value:
                message_template = add_links(
                    links, links_type.value, message_template, self.logger
                )

            self.logger.debug("Cleaning email message text from unicode characters.")
            message_template["message"] = remove_unicode(message_template["message"])
            message_template["message"] = clean_text(message_template["message"])

            if store_headers:
                self.logger.debug("Adding headers information.")
                message_template["headres"] = email_data

            return message_template
        except KeyError as e:
            self.logger.exception(f"Failed to extract email data. Key Error: {e}")
            raise GmailPayloadError(f"{e}")
        except Exception as e:
            self.logger.exception(f"Failed to extract email data: {e}")
            raise GmailService(f"{e}")
        

    @sleep_and_retry
    @limits(calls=MAX_API_CALLS, period=API_AWAIT_PERIOD)
    @gmail_api_exceptions
    def __get_message(self, message_id: str):
        self.logger.debug(f"Requesting data for email of id: {message_id}")
        return self.service.users().messages().get(userId="me", id=message_id).execute()

    @sleep_and_retry
    @limits(calls=MAX_API_CALLS, period=API_AWAIT_PERIOD)
    @gmail_api_exceptions
    def _get_emails(
        self,
        query: str = "is:unread in:inbox",
        max_results: int = 10,
        links_type: LinksType = LinksType.NONE,
        store_headers: bool = False,
        raw: bool = False,
        filters: Optional[dict] = None,
        return_attachments: bool = False, 
        attachment_file_path: str = None
    ) -> deque[TrackedEmail]:
        """
        Retrieves and processes emails from the Gmail account based on the provided preferences.

        Parameters:
        query (str): If filter is not provided, a simple query is made to set the retrieved messages scope. "is:unread in:inbox" by default.
        max_results (int): How many emails should be returned. 10 by default. None means 'return all'. A positive integer is expected or None value.
        links_type (LinksType, optional): A LinksType representing the preference for adding links to the email payload:
            - LinksType.NONE: no links attached to the final message,
            - LinksType.BASIC: only unique domains attached to the final message,
            - LinksType.DETAILED: full links attached to the final message.
        store_headers (bool, optional): A flag indicating whether to store email headers in the payload. Defaults to False.
        raw (bool, optional): A flag indicating whether to return the raw email data. Defaults to False.
        filters (dict): A dictionary of custom filters that specify the categories for filtering email messages.
        return_attachments (bool): If True then search for email attachments and return them as raw data (bytes/strs). False by default.
        attachment_file_path (str): a path where attachments should be downloaded. If such directory does not exist, create it and grant 755 permissions.
                                    If 'attachment_file_path' provided, then search for attachments and download them locally. None by default.

        Returns:
        List[TrackedEmail]: A list containing the processed email data stored as TrackedEmail objects.

        Raises:
        GmailHttpError: If an HTTP error occurs during the API call.
        GmailApiCallTimeoutError: If the API call times out.
        GmailPayloadError: If a key is missing in email/data payload.
        GmailServiceError: If an unhandled exception occurs during the API call.
        """

        self.logger.debug("Retrieving emails and/or attachmens.")

        try:
            max_results = verify_limit(max_results)
            messages = self.__retrieve_emails(query=query, filters=filters, max_results=max_results )

            if not messages:  
                self.logger.debug("No messages found.")
                return []

            self.logger.debug(f"Searching for {len(messages)} message(s).")

            for message in messages:
                msg = (
                    self.service.users()
                    .messages()
                    .get(userId="me", id=message["id"])
                    .execute()
                )

                if raw:
                    self.logger.debug("Getting raw message.")
                    message_template = json.loads(
                        json.dumps(self.__get_message(message_id=message["id"]), indent=4)
                    )
                else:
                    self.logger.debug("Getting structured message.")
                    message_template = self.__extract_custom_email(msg, links_type, store_headers)
                    
                if return_attachments or attachment_file_path:
                    self.logger.debug("Seaerching for attachments.")
                    message_template["attachments"] = self.__get_attachments(msg=msg, message=message, return_attachments=return_attachments, download_path=attachment_file_path)

                self._emails.append(
                    TrackedEmail(
                        id_=msg["id"],
                        thread=msg["threadId"],
                        labels=msg["labelIds"],
                        payload=message_template,
                        logger=self.logger,
                    )
                )
            self.logger.debug(f"Found {len(self._emails)} email(s) in total.")
            return self._emails
        except KeyError as e:
            self.logger.exception(f"Failed to get emails due to error key: {e}")
            raise GmailEmailError(f"Failed to get emails due to error key: {e}")
        except Exception as e:
            self.logger.exception(f"Failed to get emaile: {e}")
            raise GmailEmailError(f"Failed to get emails: {e}")
        
    
    @sleep_and_retry
    @limits(calls=MAX_API_CALLS, period=API_AWAIT_PERIOD)
    @gmail_api_exceptions
    def _connect(self):
        """
        This function establishes a connection to the Gmail API using the provided credentials.
        If the token file does not exist, it is created and the credentials are loaded from it.
        If the credentials are not valid or expired, they are refreshed.
        The function returns a service object for interacting with the Gmail API.

        Parameters:
        None

        Returns:
        service: A service object for interacting with the Gmail API.

        Raises:
        GmailHttpError: If an HTTP error occurs during the API call.
        GmailApiCallTimeoutError: If the API call times out.
        GmailPayloadError: If a key is missing in email/data payload.
        GmailServiceError: If an unhandled exception occurs during the API call.
        GmailInstanceError: Incorrect objects instance for Gmail API services.

        Important:
        self.credentials is of type: class 'google.oauth2.credentials.Credentials'
        build... (the stablished connection) is of class from googleapiclient.discovery import Resource
        """
        self.logger.info("Connecting to Gmail API service.")
        self.credentials = load_token(self.token_file)
        self.__check_token()
        return build("gmail", "v1", credentials=self.credentials)
