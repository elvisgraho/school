"""
Main DatabaseManager class that combines all mixins.
"""

from .base import DatabaseBase, DB_FILE
from .lessons import LessonsMixin
from .stats import StatsMixin
from .streaks import StreaksMixin
from .records import RecordsMixin
from .settings import SettingsMixin
from .export import ExportMixin
from .tags import TagsMixin


class DatabaseManager(
    DatabaseBase,
    LessonsMixin,
    StatsMixin,
    StreaksMixin,
    RecordsMixin,
    SettingsMixin,
    ExportMixin,
    TagsMixin
):
    """
    SQLite database manager for video lesson progress tracking.

    This class combines all database functionality through mixins:
    - DatabaseBase: Connection management, caching, and schema initialization
    - LessonsMixin: CRUD operations for lessons
    - StatsMixin: Statistics and analytics queries
    - StreaksMixin: Streak tracking and goal management
    - RecordsMixin: Personal records computation
    - SettingsMixin: User settings management
    - ExportMixin: Data export functionality
    - TagsMixin: Tag management for lessons
    """

    def __init__(self, db_path: str = DB_FILE):
        super().__init__(db_path)
