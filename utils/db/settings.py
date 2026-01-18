"""
User settings management.
"""

from typing import Optional, Dict


class SettingsMixin:
    """Mixin for user settings operations."""

    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        """Get a user setting by key."""
        with self._get_connection() as conn:
            row = conn.execute(
                'SELECT value FROM user_settings WHERE key = ?', (key,)
            ).fetchone()
            return row['value'] if row else default

    def set_setting(self, key: str, value: str) -> None:
        """Set a user setting."""
        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO user_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = CURRENT_TIMESTAMP
            ''', (key, value, value))
        self.invalidate_cache()

    def get_all_settings(self) -> Dict[str, str]:
        """Get all user settings as a dictionary."""
        with self._get_connection() as conn:
            rows = conn.execute('SELECT key, value FROM user_settings').fetchall()
            return {row['key']: row['value'] for row in rows}
