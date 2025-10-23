"""Lightweight DICOM viewing and editing helpers.

This package provides a minimal feature set tailored to the kata
requirements.  Only a subset of the DICOM standard is supported, focusing
on little-endian CT images with monochrome pixel data.  The modules expose
high level helpers for reading files, manipulating pixel arrays and writing
back well-formed datasets with selectable save profiles.
"""

from .dataset import DicomDataset
from .io import read_file, write_file
from .profiles import AVAILABLE_PROFILES, SaveProfile, get_profile

__all__ = [
    "DicomDataset",
    "AVAILABLE_PROFILES",
    "SaveProfile",
    "get_profile",
    "read_file",
    "write_file",
]
