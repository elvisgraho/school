"""
Lesson management: CRUD operations, sync, and pagination.
"""

import os
import re
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

PAGE_SIZE = 50


def parse_srt_file(srt_path: str) -> Optional[str]:
    """Parse SRT file and extract plain text efficiently.

    Returns concatenated text from all subtitle entries, or None if file can't be read.
    """
    try:
        # Try common encodings
        for encoding in ('utf-8', 'utf-8-sig', 'latin-1', 'cp1252'):
            try:
                with open(srt_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue
        else:
            return None

        # Remove SRT formatting: sequence numbers, timestamps, and empty lines
        # SRT format: number \n timestamp --> timestamp \n text \n\n
        lines = []
        for line in content.split('\n'):
            line = line.strip()
            # Skip empty lines, sequence numbers (pure digits), and timestamp lines
            if not line:
                continue
            if line.isdigit():
                continue
            if '-->' in line:
                continue
            # Remove HTML-style tags like <i>, </i>, <font>, etc.
            line = re.sub(r'<[^>]+>', '', line)
            if line:
                lines.append(line)

        return ' '.join(lines) if lines else None
    except (OSError, IOError):
        return None


class LessonsMixin:
    """Mixin for lesson-related database operations."""

    def sync_folder(self, folder_path: str, parse_func) -> Dict[str, Any]:
        """Sync lessons from folder using diff engine with content-based hashing."""
        stats = {'added': 0, 'updated': 0, 'archived': 0, 'errors': 0, 'unchanged': 0}

        if not os.path.isdir(folder_path):
            return stats

        def compute_file_hash(filepath: str) -> Optional[str]:
            """Compute MD5 hash of file content (first + last 8KB)."""
            try:
                hash_obj = hashlib.md5()
                with open(filepath, 'rb') as f:
                    data = f.read(8192)
                    hash_obj.update(data)
                    f.seek(0, 2)
                    size = f.tell()
                    if size > 8192:
                        f.seek(-8192, 2)
                        data = f.read(8192)
                        hash_obj.update(data)
                return hash_obj.hexdigest()
            except (OSError, IOError):
                return None

        file_data = []

        try:
            with os.scandir(folder_path) as entries:
                for entry in entries:
                    if entry.is_file() and entry.name.lower().endswith('.mp4'):
                        try:
                            mtime = entry.stat().st_mtime
                            filepath = os.path.normpath(os.path.join(folder_path, entry.name))
                            file_hash = compute_file_hash(filepath)
                            if file_hash:
                                # Check for matching .srt file
                                base_name = os.path.splitext(entry.name)[0]
                                srt_path = os.path.join(folder_path, base_name + '.srt')
                                transcript = None
                                if os.path.isfile(srt_path):
                                    transcript = parse_srt_file(srt_path)
                                file_data.append((file_hash, filepath, entry.name, mtime, transcript))
                            else:
                                stats['errors'] += 1
                        except (OSError, IOError):
                            stats['errors'] += 1
        except OSError:
            stats['errors'] = 1
            return stats

        if not file_data:
            return stats

        current_hashes = set()

        with self._get_connection() as conn:
            existing_lookup = {}
            rows = conn.execute('SELECT id, file_hash, filepath, filename, status, file_mtime, transcript FROM lessons').fetchall()
            for row in rows:
                existing_lookup[row['file_hash']] = dict(row)

            to_insert = []
            to_update = []

            for file_hash, filepath, filename, mtime, transcript in file_data:
                parsed = parse_func(filename)
                if not parsed:
                    stats['errors'] += 1
                    continue

                current_hashes.add(file_hash)

                if file_hash in existing_lookup:
                    existing = existing_lookup[file_hash]
                    # Update if path/mtime changed, or if we now have a transcript we didn't before
                    needs_update = (
                        existing['filepath'] != filepath or
                        existing.get('file_mtime', 0) != mtime or
                        (transcript and not existing.get('transcript'))
                    )
                    if needs_update:
                        to_update.append({
                            'id': existing['id'],
                            'filename': filename,
                            'filepath': filepath,
                            'mtime': mtime,
                            'status': existing['status'],
                            'transcript': transcript if transcript else existing.get('transcript')
                        })
                        stats['updated'] += 1
                    else:
                        stats['unchanged'] += 1
                else:
                    to_insert.append({
                        'file_hash': file_hash,
                        'filepath': filepath,
                        'filename': filename,
                        'author': parsed['author'],
                        'title': parsed['title'],
                        'lesson_date': parsed['lesson_date'],
                        'mtime': mtime,
                        'transcript': transcript
                    })
                    stats['added'] += 1

            if to_insert:
                conn.executemany('''
                    INSERT INTO lessons (file_hash, filepath, filename, author, title, lesson_date, file_mtime, status, transcript)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'New', ?)
                ''', [(r['file_hash'], r['filepath'], r['filename'], r['author'], r['title'], r['lesson_date'], r['mtime'], r['transcript'])
                      for r in to_insert])

            if to_update:
                conn.executemany('''
                    UPDATE lessons SET filename = ?, filepath = ?, file_mtime = ?, transcript = COALESCE(?, transcript), updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', [(r['filename'], r['filepath'], r['mtime'], r['transcript'], r['id']) for r in to_update])

            if current_hashes:
                placeholders = ','.join('?' * len(current_hashes))
                archived = conn.execute(f'''
                    UPDATE lessons SET status = 'Archived', updated_at = CURRENT_TIMESTAMP
                    WHERE file_hash NOT IN ({placeholders}) AND status != 'Archived'
                ''', tuple(current_hashes)).rowcount
                stats['archived'] = archived

        return stats

    def get_paginated_lessons(self, page: int = 1, page_size: int = None, status_filter: Optional[List[str]] = None,
                              author_filter: Optional[str] = None,
                              date_from: Optional[datetime] = None,
                              date_to: Optional[datetime] = None,
                              search_query: Optional[str] = None,
                              year_filter: Optional[int] = None,
                              month_filter: Optional[int] = None,
                              tag_ids: Optional[List[int]] = None) -> Tuple[List[Dict[str, Any]], int]:
        """Get lessons with server-side pagination."""
        if page_size is None:
            page_size = PAGE_SIZE

        conditions = ['status != "Archived"']
        params = []

        if status_filter:
            placeholders = ','.join('?' * len(status_filter))
            conditions.append(f'status IN ({placeholders})')
            params.extend(status_filter)

        if author_filter:
            conditions.append('author LIKE ?')
            params.append(f'%{author_filter}%')

        if date_from:
            conditions.append('lesson_date >= ?')
            params.append(date_from)

        if date_to:
            conditions.append('lesson_date <= ?')
            params.append(date_to)

        if search_query:
            conditions.append('title LIKE ?')
            params.append(f'%{search_query}%')

        if year_filter:
            conditions.append('strftime("%Y", lesson_date) = ?')
            params.append(str(year_filter))

        if month_filter:
            conditions.append('strftime("%m", lesson_date) = ?')
            params.append(f'{month_filter:02d}')

        # Tag filtering - lessons must have ALL specified tags
        tag_join = ''
        tag_having = ''
        if tag_ids:
            placeholders = ','.join('?' * len(tag_ids))
            tag_join = 'JOIN lesson_tags lt ON lessons.id = lt.lesson_id'
            conditions.append(f'lt.tag_id IN ({placeholders})')
            params.extend(tag_ids)
            tag_having = f'HAVING COUNT(DISTINCT lt.tag_id) = {len(tag_ids)}'

        where_clause = ' AND '.join(conditions)

        with self._get_connection() as conn:
            if tag_ids:
                count_query = f'''
                    SELECT COUNT(*) FROM (
                        SELECT lessons.id FROM lessons {tag_join}
                        WHERE {where_clause}
                        GROUP BY lessons.id {tag_having}
                    )
                '''
                total = conn.execute(count_query, params).fetchone()[0]
            else:
                total = conn.execute(f'SELECT COUNT(*) FROM lessons WHERE {where_clause}', params).fetchone()[0]

            offset = (page - 1) * page_size
            if tag_ids:
                query = f'''
                    SELECT lessons.id, file_hash, filename, filepath, author, title, lesson_date,
                           status, completed_at, lessons.created_at
                    FROM lessons {tag_join}
                    WHERE {where_clause}
                    GROUP BY lessons.id {tag_having}
                    ORDER BY lesson_date DESC
                    LIMIT {page_size} OFFSET {offset}
                '''
            else:
                query = f'''
                    SELECT id, file_hash, filename, filepath, author, title, lesson_date,
                           status, completed_at, created_at
                    FROM lessons
                    WHERE {where_clause}
                    ORDER BY lesson_date DESC
                    LIMIT {page_size} OFFSET {offset}
                '''
            rows = conn.execute(query, params).fetchall()
            lessons = [dict(row) for row in rows]

        return lessons, total

    def search_transcripts(self, query: str, page_size: int = 500,
                           status_filter: Optional[List[str]] = None,
                           year_filter: Optional[int] = None,
                           month_filter: Optional[int] = None,
                           tag_ids: Optional[List[int]] = None) -> Tuple[List[Dict[str, Any]], int]:
        """Search transcripts efficiently and return matching lessons with context snippets.

        Optimized for 15k+ videos with 8-min average transcripts.
        Returns lessons with a 'context' field showing ~15 words around the match.
        """
        if not query or not query.strip():
            return [], 0

        query_lower = query.lower().strip()
        context_words = 8  # words before and after match

        conditions = ['status != "Archived"', 'transcript IS NOT NULL']
        params = []

        if status_filter:
            placeholders = ','.join('?' * len(status_filter))
            conditions.append(f'status IN ({placeholders})')
            params.extend(status_filter)

        if year_filter:
            conditions.append('strftime("%Y", lesson_date) = ?')
            params.append(str(year_filter))

        if month_filter:
            conditions.append('strftime("%m", lesson_date) = ?')
            params.append(f'{month_filter:02d}')

        # Tag filtering
        tag_join = ''
        tag_having = ''
        if tag_ids:
            placeholders = ','.join('?' * len(tag_ids))
            tag_join = 'JOIN lesson_tags lt ON lessons.id = lt.lesson_id'
            conditions.append(f'lt.tag_id IN ({placeholders})')
            params.extend(tag_ids)
            tag_having = f'HAVING COUNT(DISTINCT lt.tag_id) = {len(tag_ids)}'

        where_clause = ' AND '.join(conditions)

        with self._get_connection() as conn:
            # Use LIKE for case-insensitive search (SQLite LIKE is case-insensitive for ASCII)
            # First get count
            if tag_ids:
                count_query = f'''
                    SELECT COUNT(*) FROM (
                        SELECT lessons.id FROM lessons {tag_join}
                        WHERE {where_clause} AND LOWER(transcript) LIKE ?
                        GROUP BY lessons.id {tag_having}
                    )
                '''
            else:
                count_query = f'''
                    SELECT COUNT(*) FROM lessons
                    WHERE {where_clause} AND LOWER(transcript) LIKE ?
                '''
            total = conn.execute(count_query, params + [f'%{query_lower}%']).fetchone()[0]

            # Fetch matching lessons with transcript for context extraction
            if tag_ids:
                data_query = f'''
                    SELECT lessons.id, file_hash, filename, filepath, author, title, lesson_date,
                           status, completed_at, lessons.created_at, transcript
                    FROM lessons {tag_join}
                    WHERE {where_clause} AND LOWER(transcript) LIKE ?
                    GROUP BY lessons.id {tag_having}
                    ORDER BY lesson_date DESC
                    LIMIT {page_size}
                '''
            else:
                data_query = f'''
                    SELECT id, file_hash, filename, filepath, author, title, lesson_date,
                           status, completed_at, created_at, transcript
                    FROM lessons
                    WHERE {where_clause} AND LOWER(transcript) LIKE ?
                    ORDER BY lesson_date DESC
                    LIMIT {page_size}
                '''
            rows = conn.execute(data_query, params + [f'%{query_lower}%']).fetchall()

            lessons = []
            for row in rows:
                lesson = dict(row)
                transcript = lesson.pop('transcript', '') or ''

                # Extract context around match (efficient string search)
                transcript_lower = transcript.lower()
                match_pos = transcript_lower.find(query_lower)

                if match_pos >= 0:
                    # Find word boundaries around match
                    words = transcript.split()
                    char_count = 0
                    match_word_idx = 0

                    # Find which word contains the match
                    for i, word in enumerate(words):
                        if char_count + len(word) >= match_pos:
                            match_word_idx = i
                            break
                        char_count += len(word) + 1  # +1 for space

                    # Extract context window
                    start_idx = max(0, match_word_idx - context_words)
                    end_idx = min(len(words), match_word_idx + context_words + 1)
                    context_words_list = words[start_idx:end_idx]

                    # Build context string with ellipsis
                    context = ' '.join(context_words_list)
                    if start_idx > 0:
                        context = '...' + context
                    if end_idx < len(words):
                        context = context + '...'

                    lesson['context'] = context
                else:
                    lesson['context'] = ''

                lessons.append(lesson)

        return lessons, total

    def update_status(self, lesson_id: int, status: str) -> bool:
        """Update lesson status."""
        if status not in ('New', 'In Progress', 'Completed'):
            return False

        completed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S') if status == 'Completed' else None

        with self._get_connection() as conn:
            conn.execute('''
                UPDATE lessons SET status = ?, completed_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, completed_at, lesson_id))

        self.invalidate_cache()
        return True

    def get_lesson_by_id(self, lesson_id: int) -> Optional[Dict[str, Any]]:
        """Get a lesson by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                'SELECT * FROM lessons WHERE id = ?', (lesson_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_in_progress_lessons(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get in-progress lessons ordered by most recently started (cached)."""
        cache_key = f'in_progress_{limit}'
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM lessons
                WHERE status = 'In Progress'
                ORDER BY updated_at DESC
                LIMIT ?
            ''', (limit,)).fetchall()
            result = [dict(row) for row in rows]
            self._set_cache(cache_key, result)
            return result

    def get_lesson_of_day(self, limit: int = 3) -> List[Dict[str, Any]]:
        """Get random uncompleted lessons."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM lessons
                WHERE status IN ('New', 'In Progress')
                ORDER BY RANDOM()
                LIMIT ?
            ''', (limit,)).fetchall()
            return [dict(row) for row in rows]

    def get_rediscover(self) -> Optional[Dict[str, Any]]:
        """Get completed lesson from 6+ months ago."""
        from datetime import timedelta
        six_months_ago = datetime.now() - timedelta(days=180)
        with self._get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM lessons
                WHERE status = 'Completed' AND completed_at <= ?
                ORDER BY RANDOM()
                LIMIT 1
            ''', (six_months_ago,)).fetchone()
            return dict(row) if row else None

    def get_random_lesson(self) -> Optional[Dict[str, Any]]:
        """Get a random lesson."""
        with self._get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM lessons
                WHERE status != 'Archived'
                ORDER BY RANDOM()
                LIMIT 1
            ''').fetchone()
            return dict(row) if row else None

    def get_years_with_lessons(self) -> List[int]:
        """Get list of years with lessons (cached)."""
        cache_key = 'years'
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT DISTINCT CAST(strftime('%Y', lesson_date) AS INTEGER) as year
                FROM lessons
                WHERE status != 'Archived'
                ORDER BY year DESC
            ''').fetchall()
            result = [row[0] for row in rows]
            self._set_cache(cache_key, result)
            return result

    def get_priority_suggestions(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get smart lesson suggestions prioritizing In Progress lessons."""
        with self._get_connection() as conn:
            in_progress = conn.execute('''
                SELECT * FROM lessons
                WHERE status = 'In Progress'
                ORDER BY updated_at DESC
                LIMIT ?
            ''', (limit,)).fetchall()

            results = [dict(row) for row in in_progress]

            remaining = limit - len(results)
            if remaining > 0:
                new_lessons = conn.execute('''
                    SELECT * FROM lessons
                    WHERE status = 'New'
                    ORDER BY RANDOM()
                    LIMIT ?
                ''', (remaining,)).fetchall()
                results.extend([dict(row) for row in new_lessons])

            return results
