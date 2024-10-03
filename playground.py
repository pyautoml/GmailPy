# https://github.com/pyautoml/GmailPy

import sys
from typing import Final
from datetime import datetime
from .gmail import GmailService
from configparser import ConfigParser
from .email_enumerators import LinksType
from .template import emails_sumup_template
from .utils import abspath, indent, file_exists


"""
This module provides step-by-step instructions on how to configure the Gmail connector. 
You need to add your own details to the configuration in order to run the code.
Some files and directories are generated after the first run (e.g., token.pickle, downloaded attachments).

[IMPORTANT] This is a developer-oriented library.
You must have an active Gmail account and register your application with OAuth 2.0 to use this library.
After that, provide the necessary credentials (the current files contain only dummy structures to guide you):
    - ./credentials/conf.conf
    - ./credentials/general.json

Please review the README.md file for more details.    

If you're not sure where to place files, please take a look below at the generated file tree:
src
├── credentials 
│  ├── conf.conf                    # add your data here
│  ├── general.json                 # add your data here
│  └── token.pickle                 # this file is generated automatically on the first successful code run
├── compiled_regexes.py
├── email_enumerators.py
├── email_sections.py
├── email_tracker.py
├── exceptions.py
├── gmail.py
├── playground.py                   # you are here
├── README.md
├── requirements.txt
├── template.py
├── utils.py
└── __init__.py
"""

sys.path.append("../")
LOGGER_NAME: Final[str] ="GmailPy"

# provide your gmail email address
RECIPIENT = "your_email@example.com"
SENDER = "your_email@example.com"

# ------------------------------------------------------------------------------
# Example usage - using basic components you can create your custom solutions.
# ------------------------------------------------------------------------------

def create_new_label(gmail, label_name: str = "CoolCat") -> None:
    # Create new email label; Refresh browser to see results.
    gmail._create_label(label_name)
    print(f"Current labels: {gmail._get_labels}")


def delete_new_label(gmail, label_name: str = "CoolCat") -> None:
    # Delete the label; WARNING: Deleting a label will also delete all emails associated with it!
    print(f"{gmail._delete_label(label_name)}")


def read_one_email(gmail, parse: bool = False) -> None:
    # Read one last email - unread, from INBOX (make sure you have at least 1 unread email in the Inbox)
    email = gmail._get_emails(max_results=1, links_type=LinksType.BASIC, raw=False)
    print(gmail._read_email(email, parse=parse))


def read_one_email_save_attachments(gmail, query: str = "is:read in:inbox", parse: bool = False, mark_as_read: bool = False) -> None:
    # read one last email - unread, from INBOX (make sure you have at least 1 unread email with attachments in the Inbox)
    # attachments must be compliant with media type stated in `email_enumerators.py`AllowedAttachment
    email = gmail._get_emails(
        max_results=1,
        query=query,
        links_type=LinksType.BASIC,
        return_attachments=False,
        attachment_file_path="attachments"
    )

    if not email:
        return None
    # [0] because all emails are inside deque() 
    return gmail._read_email(email[0], parse=parse, mark_as_read=mark_as_read)


def read_many_emails(gmail, how_many: int = 2) -> None:
    read_emails = gmail._get_emails(query="is:read in:inbox", max_results=how_many, links_type=LinksType.NONE)
    emails = gmail._read_emails(read_emails)
    print(indent(next(emails)), end="\n\n")
    print(indent(next(emails)), end="\n\n")


def delete_email(gmail) -> None:
    emails = gmail._get_emails(query= "is:read in:inbox", max_results=1, links_type=LinksType.BASIC)
    for email in emails:
        gmail._delete_email(email)


def remove_from_bin(gmail) -> None:
    print(gmail._empty_trash())


def create_and_save_draft(gmail) -> None:
    # Check your mailbox' DRAFT folder
    text = emails_sumup_template.substitute(
        recipient_name="Kitty",
        emails_sent=str(datetime.now()),
        emails_received=15,
        spam=100,
        topics="Holiday, Newsletters, Shops",
        assistant="PyLllama - Your Personal Assistant",
    )
    gmail._create_email_draft(draft_message=text, subject="Weekly Emails Summary")


def create_and_send_email(gmail, your_email: str) -> None:
    email = gmail._create_email(
        sender=your_email,
        recipient=your_email,
        subject="Hello from PyLlama!",
        email_message="Hello,\nThis is a test email.",
    )
    print(gmail._send_email(email=email))


def setup() -> dict:
    config = ConfigParser()
    file_exists(abspath("/credentials/conf.conf"))
    config.read(abspath("/credentials/conf.conf"))

    setup: dict = {
        "token_file": abspath(f"{config.get('GMAIL','path')}/token.pickle"),
        "credentials_file": abspath(f"{config.get('GMAIL','path')}/general.json"),
        "scopes": " ".join(config.get("GMAIL", "scopes").split(",")),
        "protected_labels": config.get("GMAIL_LABELS", "protected"),
    }
    return setup

def main():
    # -----------------------------------------------------------------------------
    # Uncomment each part ste-by-step to check how it works.
    # Advised: read comments on top of each playground method before running it.
    # -----------------------------------------------------------------------------

    # connector -------------------------
    gmail = GmailService(setup=setup(), log_level="debug")

    # methods --------------------
    # create_new_label(gmail)
    # delete_new_label(gmail)

    # create_and_save_draft(gmail)
    # create_and_send_email(gmail, "gabrielrodewald@gmail.com")

    # read_many_emails(gmail, how_many=2)
    # read_one_email(gmail, parse=True)
    # print(read_one_email_save_attachments(gmail=gmail, mark_as_read=True))

    # caution: 1 newest unread email will be deleted! (not removed to bin but deleted)
    # delete_email(gmail)
    # remove_from_bin(gmail)

if __name__ == "__main__":
    main()
