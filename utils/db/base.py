"""
Base database functionality: connection, caching, and schema initialization.
"""

import sqlite3
from datetime import datetime
from typing import Optional, Any
import threading


DB_FILE = 'progress.db'


class ClosingConnection(sqlite3.Connection):
    """Commit or roll back a transaction, then always release the file handle."""

    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


class DatabaseBase:
    """Base class with connection management and caching."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path: str = DB_FILE):
        """Singleton pattern to reuse database connections."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = DB_FILE):
        if self._initialized:
            return
        self.db_path = db_path
        self._cache = {}
        self._cache_timestamp = {}
        self._cache_ttl = 5  # seconds
        self._init_db()
        self._initialized = True

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid."""
        if key not in self._cache_timestamp:
            return False
        return (datetime.now() - self._cache_timestamp[key]).total_seconds() < self._cache_ttl

    def _set_cache(self, key: str, value: Any) -> None:
        """Store value in cache with timestamp."""
        self._cache[key] = value
        self._cache_timestamp[key] = datetime.now()

    def _get_cache(self, key: str) -> Optional[Any]:
        """Get value from cache if valid."""
        if self._is_cache_valid(key):
            return self._cache.get(key)
        return None

    def invalidate_cache(self) -> None:
        """Clear all caches - call after mutations."""
        self._cache.clear()
        self._cache_timestamp.clear()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path, timeout=30, factory=ClosingConnection)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        return conn

    def _init_db(self):
        """Initialize the database schema."""
        with self._get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_hash TEXT UNIQUE NOT NULL,
                    filepath TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    author TEXT NOT NULL,
                    title TEXT NOT NULL,
                    lesson_date DATE NOT NULL,
                    file_mtime REAL DEFAULT 0,
                    status TEXT DEFAULT 'New' CHECK(status IN ('New', 'In Progress', 'Completed', 'Archived')),
                    completed_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    transcript TEXT
                )
            ''')

            # Add metadata without replacing existing lessons, IDs, or tags.
            columns = {row['name'] for row in conn.execute('PRAGMA table_info(lessons)')}
            for name, declaration in {
                'file_size': 'INTEGER', 'file_mtime_ns': 'INTEGER',
                'transcript_size': 'INTEGER', 'transcript_mtime_ns': 'INTEGER',
                'file_mtime': 'REAL DEFAULT 0', 'transcript': 'TEXT',
                'status_before_archive': 'TEXT',
            }.items():
                if name not in columns:
                    conn.execute(f'ALTER TABLE lessons ADD COLUMN {name} {declaration}')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS completion_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
                    completed_at TEXT NOT NULL,
                    UNIQUE(lesson_id, completed_at)
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_completion_date ON completion_events(completed_at)')
            previous_view = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='view' AND name='completion_activity'").fetchone()
            repair_records = previous_view is not None and 'GROUP BY l.id' not in previous_view[0]

            # Completion credit belongs to the first finish of a lesson. Keep
            # legacy repeat events for history, but never add another credit.
            conn.execute('DROP TRIGGER IF EXISTS record_insert_completion')
            conn.execute('DROP TRIGGER IF EXISTS record_update_completion')
            conn.execute('''
                INSERT OR IGNORE INTO completion_events (lesson_id, completed_at)
                SELECT l.id, l.completed_at FROM lessons l
                WHERE l.completed_at IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM completion_events e WHERE e.lesson_id=l.id)
            ''')
            conn.execute('''
                CREATE TRIGGER record_insert_completion
                AFTER INSERT ON lessons WHEN NEW.completed_at IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM completion_events WHERE lesson_id=NEW.id)
                BEGIN
                    INSERT OR IGNORE INTO completion_events (lesson_id, completed_at)
                    VALUES (NEW.id, NEW.completed_at);
                END
            ''')
            conn.execute('''
                CREATE TRIGGER record_update_completion
                AFTER UPDATE OF status, completed_at ON lessons
                WHEN NEW.status = 'Completed' AND NEW.completed_at IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM completion_events WHERE lesson_id=NEW.id)
                BEGIN
                    INSERT OR IGNORE INTO completion_events (lesson_id, completed_at)
                    VALUES (NEW.id, NEW.completed_at);
                END
            ''')
            conn.execute('''
                UPDATE lessons SET completed_at = (
                    SELECT MIN(e.completed_at) FROM completion_events e WHERE e.lesson_id=lessons.id)
                WHERE EXISTS (SELECT 1 FROM completion_events e WHERE e.lesson_id=lessons.id)
                  AND completed_at IS NOT (
                    SELECT MIN(e.completed_at) FROM completion_events e WHERE e.lesson_id=lessons.id)
            ''')
            conn.execute('DROP VIEW IF EXISTS completion_activity')
            conn.execute('''
                CREATE VIEW completion_activity AS
                SELECT l.id, l.title, l.author, l.lesson_date, MIN(e.completed_at) AS completed_at,
                       'Completed' AS status
                FROM completion_events e JOIN lessons l ON l.id = e.lesson_id
                GROUP BY l.id
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_lessons_file_hash
                ON lessons(file_hash)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_lessons_status
                ON lessons(status)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_lessons_author
                ON lessons(author)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_lessons_lesson_date
                ON lessons(lesson_date)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_lessons_completed_at
                ON lessons(completed_at)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_lessons_status_date
                ON lessons(status, lesson_date DESC)
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS personal_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_type TEXT UNIQUE NOT NULL,
                    value INTEGER NOT NULL,
                    achieved_date DATE,
                    details TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS streak_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    streak_length INTEGER NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS lesson_tags (
                    lesson_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (lesson_id, tag_id),
                    FOREIGN KEY (lesson_id) REFERENCES lessons(id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
                )
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_lesson_tags_lesson
                ON lesson_tags(lesson_id)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_lesson_tags_tag
                ON lesson_tags(tag_id)
            ''')

            if repair_records and conn.execute('''
                SELECT 1 FROM completion_events GROUP BY lesson_id HAVING COUNT(*) > 1 LIMIT 1
            ''').fetchone():
                # Old repeat credits may have inflated saved records. These
                # derived values are recomputed from first completions on demand.
                conn.execute('''DELETE FROM personal_records WHERE record_type IN
                    ('best_streak', 'most_day', 'most_week', 'most_month',
                     'most_consistent', 'best_rolling_7', 'best_rolling_30')''')
        self.invalidate_cache()
