# https://github.com/pyautoml/GmailPy

from enum import Enum


"""This module contains enumerations to be used across the whole project."""

class LabelType(Enum):

    VISIBLE = "visible"
    HIDDE = "hidden"

class LinksType(Enum):
    NONE = "None"
    BASIC = "links_basic"
    DETAILED = "links_detailed"

class AllowedAttachment(Enum):
    PNG = "png"
    JPG = "jpg"
    JPEG = "jpeg"
    WEBM = "webm"
    PDF = "pdf"
    XLSX = "xlsx"
    XML = "xml"