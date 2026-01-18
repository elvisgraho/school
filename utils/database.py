"""
Database utilities for Guitar Shed.
DEPRECATED: This file is kept for backwards compatibility.
Please use utils.db.DatabaseManager instead.
"""

# Re-export from new modular structure
from .db import DatabaseManager
from .db.lessons import PAGE_SIZE
from .db.base import DB_FILE

__all__ = ['DatabaseManager', 'PAGE_SIZE', 'DB_FILE']
