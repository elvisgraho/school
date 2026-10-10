"""
Video School utilities package.
"""

from .parser import parse_filename, generate_unique_hash
from .db import DatabaseManager
from .db.lessons import PAGE_SIZE

__all__ = ['parse_filename', 'generate_unique_hash', 'DatabaseManager', 'PAGE_SIZE', 'ui']


def __getattr__(name):
    # UI components must register inside the active Streamlit script context.
    if name == "ui":
        from importlib import import_module
        return import_module(".ui", __name__)
    raise AttributeError(name)
