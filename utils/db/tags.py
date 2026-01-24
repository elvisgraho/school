"""
Tag management: CRUD operations for tags and lesson-tag associations.
"""

from typing import Optional, List, Dict, Any


class TagsMixin:
    """Mixin for tag-related database operations."""

    def get_all_tags(self) -> List[Dict[str, Any]]:
        """Get all tags ordered by name."""
        cache_key = 'all_tags'
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT id, name, created_at
                FROM tags
                ORDER BY name
            ''').fetchall()
            result = [dict(row) for row in rows]
            self._set_cache(cache_key, result)
            return result

    def create_tag(self, name: str) -> Optional[int]:
        """Create a new tag. Returns tag ID or None if already exists."""
        name = name.strip()
        if not name:
            return None

        with self._get_connection() as conn:
            try:
                cursor = conn.execute(
                    'INSERT INTO tags (name) VALUES (?)', (name,)
                )
                self.invalidate_cache()
                return cursor.lastrowid
            except Exception:
                # Tag already exists, return existing ID
                row = conn.execute(
                    'SELECT id FROM tags WHERE name = ?', (name,)
                ).fetchone()
                return row['id'] if row else None

    def get_or_create_tag(self, name: str) -> Optional[int]:
        """Get existing tag ID or create new one."""
        name = name.strip()
        if not name:
            return None

        with self._get_connection() as conn:
            row = conn.execute(
                'SELECT id FROM tags WHERE name = ?', (name,)
            ).fetchone()
            if row:
                return row['id']

        return self.create_tag(name)

    def delete_tag(self, tag_id: int) -> bool:
        """Delete a tag (also removes all lesson associations)."""
        with self._get_connection() as conn:
            rowcount = conn.execute(
                'DELETE FROM tags WHERE id = ?', (tag_id,)
            ).rowcount
            self.invalidate_cache()
            return rowcount > 0

    def get_lesson_tags(self, lesson_id: int) -> List[Dict[str, Any]]:
        """Get all tags for a specific lesson."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT t.id, t.name
                FROM tags t
                JOIN lesson_tags lt ON t.id = lt.tag_id
                WHERE lt.lesson_id = ?
                ORDER BY t.name
            ''', (lesson_id,)).fetchall()
            return [dict(row) for row in rows]

    def add_tag_to_lesson(self, lesson_id: int, tag_id: int) -> bool:
        """Add a tag to a lesson."""
        with self._get_connection() as conn:
            try:
                conn.execute(
                    'INSERT INTO lesson_tags (lesson_id, tag_id) VALUES (?, ?)',
                    (lesson_id, tag_id)
                )
                self.invalidate_cache()
                return True
            except Exception:
                return False  # Already exists

    def remove_tag_from_lesson(self, lesson_id: int, tag_id: int) -> bool:
        """Remove a tag from a lesson."""
        with self._get_connection() as conn:
            rowcount = conn.execute(
                'DELETE FROM lesson_tags WHERE lesson_id = ? AND tag_id = ?',
                (lesson_id, tag_id)
            ).rowcount
            self.invalidate_cache()
            return rowcount > 0

    def get_lessons_by_tag_ids(self, tag_ids: List[int]) -> List[int]:
        """Get lesson IDs that have ALL the specified tags."""
        if not tag_ids:
            return []

        with self._get_connection() as conn:
            placeholders = ','.join('?' * len(tag_ids))
            rows = conn.execute(f'''
                SELECT lesson_id
                FROM lesson_tags
                WHERE tag_id IN ({placeholders})
                GROUP BY lesson_id
                HAVING COUNT(DISTINCT tag_id) = ?
            ''', (*tag_ids, len(tag_ids))).fetchall()
            return [row['lesson_id'] for row in rows]

    def get_tag_usage_counts(self) -> Dict[int, int]:
        """Get count of lessons for each tag."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT tag_id, COUNT(*) as count
                FROM lesson_tags
                GROUP BY tag_id
            ''').fetchall()
            return {row['tag_id']: row['count'] for row in rows}

    def get_tags_for_lessons(self, lesson_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
        """Get tags for multiple lessons efficiently (avoids N+1 queries)."""
        if not lesson_ids:
            return {}

        with self._get_connection() as conn:
            placeholders = ','.join('?' * len(lesson_ids))
            rows = conn.execute(f'''
                SELECT lt.lesson_id, t.id, t.name
                FROM lesson_tags lt
                JOIN tags t ON lt.tag_id = t.id
                WHERE lt.lesson_id IN ({placeholders})
                ORDER BY t.name
            ''', lesson_ids).fetchall()

            result: Dict[int, List[Dict[str, Any]]] = {lid: [] for lid in lesson_ids}
            for row in rows:
                result[row['lesson_id']].append({'id': row['id'], 'name': row['name']})
            return result
