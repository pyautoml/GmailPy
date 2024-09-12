# https://github.com/pyautoml/GmailPy

import json
from logging import Logger
from datetime import datetime
from typing import Final, Optional
from utils import save_email, null_logger


"""
This module provides a class called TrackedEmail for tracking and managing email data. 
The TrackedEmail class is designed to handle various aspects of email management, 
such as storing email details, updating email status, and saving email data to a file.
"""

LOGGER_NAME: Final[str] ="GmailPy"

class TrackedEmail:

    STATUS: Final[list] = [
        "new",
        "read",
        "sent",
        "draft",
        "moved",
        "replied",
        "deleted",
        "scheduled" "forwarded",
    ]

    def __init__(self, id_: str, thread: str, labels: list, payload: Optional[dict] = {}, logger: Logger = null_logger()) -> None:
        """
        Initializes a new instance of TrackedEmail.

        Parameters:
        id_ (str): The unique identifier of the email.
        thread (str): The thread identifier of the email.
        labels (list): A list of labels associated with the email.
        payload (Optional[dict], optional): The payload of the email. Defaults to an empty dictionary.

        Attributes:
        __id (str): The unique identifier of the email.
        __status (str): The current status of the email. Initialized to 'new'.
        __thread (str): The thread identifier of the email.
        __labels (list): A list of labels associated with the email.
        __payload (dict): The payload of the email. Optional.
        __status_history (list): A list of status updates for the email.

        Raises:
        TypeError: If any of the parameters are not of the expected type.
        """

        self.logger = logger

        if not isinstance(id_, str):
            logger.exception(f"'id_' must be of type str, not '{type(id_)}'")
            raise TypeError(f"'id_' must be of type str, not '{type(id_)}'")

        if not isinstance(thread, str):
            logger.exception(f"Thread must be of type str, not '{type(thread)}'")
            raise TypeError(f"Thread must be of type str, not '{type(thread)}'")

        if not isinstance(labels, list):
            logger.exception(f"Labels must be of type list, not '{type(labels)}'")
            raise TypeError(f"Labels must be of type list, not '{type(labels)}'")

        if payload and not isinstance(payload, dict):
            logger.exception(f"Payload must be of type dict or None, not '{type(payload)}'")
            raise TypeError(f"Payload must be of type dict or None, not '{type(payload)}'")

        self.__id = id_
        self.__status = "new"
        self.__thread = thread
        self.__labels = labels
        self.__payload = payload
        self.__status_history: list = []
        self._update_status(self.__status)

    @property
    def message_id(self) -> str:
        """
        Returns the unique identifier of the email.

        Parameters:
        None

        Returns:
        str: The unique identifier of the email.
        """
        return self.__id

    @property
    def message(self) -> dict:
        """
        Returns the payload of the email.

        Parameters:
        None

        Returns:
        dict: The payload of the email. The payload contains the details of the email, such as sender, recipient, subject, body, etc.
        """
        return self.__payload

    @property
    def labels(self) -> list:
        """
        Returns the list of labels associated with the email.

        Parameters:
        None

        Returns:
        list: A list of labels associated with the email. Each label is a string.
        """
        return self.__labels

    @property
    def stats(self) -> dict:
        """
        Returns a dictionary containing various statistics about the email.

        Parameters:
        None

        Returns:
        dict: A dictionary containing the following keys:
            - "id": The unique identifier of the email.
            - "status": The current status of the email.
            - "thread": The thread identifier of the email.
            - "labels": A list of labels associated with the email.
        """

        self.logger.debug("Sending back stats.")
        
        return {
            "id": self.__id,
            "status": self.__status,
            "thread": self.__thread,
            "labels": self.__labels,
        }

    def _update_status(self, status: str) -> None:
        """
        Updates the status of the email.

        Parameters:
        status (str): The new status to be set for the email. It should be one of the following:
            - 'new'
            - 'sent'
            - 'read'
            - 'draft'
            - 'moved'
            - 'replied'
            - 'deleted'
            - 'scheduled'
            - 'forwarded'

        Raises:
        ValueError: If the provided status is not one of the valid statuses.

        Returns:
        None
        """

        self.logger.debug("Updating email status.")

        if status not in self.STATUS:
            self.logger.exception(f"Status '{status}' is not supported. Please use instead: {', '.join([s for s in self.STATUS])}")
            raise ValueError(
                f"Status '{status}' is not supported. Please use instead: {', '.join([s for s in self.STATUS])}"
            )

        self.__status = status
        self._update_history(status)

    def unpack(self) -> dict:
        try:
            return{
                "id": self.__id,
                "thread": self.__thread,
                "labels": self.__labels,
                "history": self.__status_history,
                "details": json.loads(json.dumps(self.__payload, indent=4)) if self.__payload else {},
            }
        except (TypeError, AttributeError, ValueError, Exception) as e:
            self.logger.exception(f"Failed to unpack email: {e}")
            raise Exception (f"Failed to unpack email: {e}")

    def _update_history(self, status: str) -> None:
        """
        Adds a status update to the email's history.

        Parameters:
        status (str): The status to be added to the history. It should be one of the following:
            - 'new'
            - 'read'
            - 'draft'
            - 'moved'
            - 'replied'
            - 'deleted'
            - 'forwarded'

        Returns:
        None

        The function appends a dictionary containing the provided status and the current timestamp to the email's status history.
        """
        self.logger.debug("Adding status history")
        self.__status_history.append({status: str(datetime.now())})

    def _delete_history(self) -> None:
        """
        Deletes the status history of the email.
        This method clears the status history of the email, effectively resetting it to an empty list.

        Parameters:
        None

        Returns:
        None

        The status history is stored in the `__status_history` attribute as a list of dictionaries.
        Each dictionary contains a status update and its corresponding timestamp.
        After calling this method, the `__status_history` attribute will be set to an empty list.
        """
        self.logger.debug("Deleting status history")
        self.__status_history = []


    def _save(self, output_path: str) -> None:
        """
        Saves the email details to a file.
        The function uses the `save_email` function from the `utils` module to save the email details to a file.
        The saved file contains the email's unique identifier, thread identifier, labels, status history, and detailed payload.

        Parameters:
        output_path (str): The path where the email details will be saved.

        Returns:
        None

        Raises:
        FileNotFoundError: If the specified output path does not exist.
        PermissionError: If the user does not have the necessary permissions to write to the file.
        Exception: For any other unexpected errors.
        """

        self.logger.debug("Saving email as json file.")

        try:
            save_email(
                file_path=output_path,
                file_name=self.__id,
                payload={
                    "id": self.__id,
                    "thread": self.__thread,
                    "labels": self.__labels,
                    "history": self.__status_history,
                    "details": json.loads(json.dumps(self.__payload, indent=4)) if self.__payload else {},
                },
            )
        except FileNotFoundError:
            self.logger.exception(f"Failed to save email: File not found at {output_path}")
            raise FileNotFoundError(
                f"Failed to save email: File not found at {output_path}"
            )
        except PermissionError:
            self.logger.exception(f"Failed to save email: Permission denied for {output_path}")
            raise PermissionError(
                f"Failed to save email: Permission denied for {output_path}"
            )
        except Exception as e:
            self.logger.exception(f"Failed to save email: {e}")
            raise Exception(f"Failed to save email: {e}")
