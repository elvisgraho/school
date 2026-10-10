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
        """Sync full content identities; only reread changed video/subtitle files."""
        stats = {'added': 0, 'updated': 0, 'archived': 0, 'errors': 0, 'unchanged': 0}
        if not os.path.isdir(folder_path):
            stats['errors'] = 1
            return stats

        metadata = []
        try:
            with os.scandir(folder_path) as entries:
                for entry in entries:
                    try:
                        if entry.is_file() and entry.name.lower().endswith('.mp4'):
                            metadata.append((os.path.abspath(entry.path), entry.name, entry.stat()))
                    except OSError:
                        stats['errors'] += 1
        except OSError:
            stats['errors'] += 1
            return stats

        with self._get_connection() as conn:
            # Never materialize the library's large transcript bodies during sync.
            rows = conn.execute("""
                SELECT id, file_hash, filepath, filename, status, file_mtime_ns,
                       file_size, transcript_mtime_ns, transcript_size
                FROM lessons
            """).fetchall()
            by_path = {os.path.abspath(row['filepath']): dict(row) for row in rows}
            by_hash = {row['file_hash']: dict(row) for row in rows}
            current_hashes = set()
            metadata.sort(key=lambda item: item[0] not in by_path)

            for filepath, filename, video_stat in metadata:
                parsed = parse_func(filename)
                if not parsed:
                    stats['errors'] += 1
                    continue
                existing = by_path.get(filepath)
                legacy_hash = None
                try:
                    if (existing and existing['file_hash'].startswith('sha256:')
                            and existing['file_size'] == video_stat.st_size
                            and existing['file_mtime_ns'] == video_stat.st_mtime_ns):
                        file_hash = existing['file_hash']
                    else:
                        digest = hashlib.sha256()
                        with open(filepath, 'rb') as video:
                            # Legacy fingerprint is used only to migrate an old row.
                            first = video.read(8192)
                            old_digest = hashlib.md5(first)
                            if video_stat.st_size > 8192:
                                video.seek(-8192, 2)
                                old_digest.update(video.read(8192))
                            legacy_hash = old_digest.hexdigest()
                            video.seek(0)
                            for chunk in iter(lambda: video.read(1024 * 1024), b''):
                                digest.update(chunk)
                        file_hash = 'sha256:' + digest.hexdigest()
                        after = os.stat(filepath)
                        if (after.st_size, after.st_mtime_ns) != (video_stat.st_size, video_stat.st_mtime_ns):
                            raise OSError('Video changed during sync')
                except OSError:
                    stats['errors'] += 1
                    continue

                if file_hash in current_hashes:
                    stats['unchanged'] += 1
                    continue
                current_hashes.add(file_hash)
                matching = by_hash.get(file_hash)
                if matching is None and legacy_hash:
                    legacy = by_hash.get(legacy_hash)
                    # Preserve progress for an existing path or a moved legacy file.
                    # Do not steal another still-present video's legacy identity.
                    if legacy and (os.path.abspath(legacy['filepath']) == filepath
                                   or not os.path.isfile(legacy['filepath'])):
                        matching = legacy

                srt_path = os.path.splitext(filepath)[0] + '.srt'
                try:
                    srt_stat = os.stat(srt_path)
                    srt_metadata = (srt_stat.st_size, srt_stat.st_mtime_ns)
                except FileNotFoundError:
                    srt_metadata = (-1, -1)
                except OSError:
                    stats['errors'] += 1
                    continue
                subtitle_changed = (not matching or srt_metadata !=
                                    (matching['transcript_size'], matching['transcript_mtime_ns']))
                transcript = None
                if subtitle_changed and srt_metadata != (-1, -1):
                    transcript = parse_srt_file(srt_path)
                    if transcript is None and srt_stat.st_size:
                        # Empty, valid subtitles are allowed; unreadable files retry.
                        try:
                            with open(srt_path, 'rb'):
                                pass
                        except OSError:
                            stats['errors'] += 1
                            continue
                    try:
                        after = os.stat(srt_path)
                    except OSError:
                        stats['errors'] += 1
                        continue
                    if (after.st_size, after.st_mtime_ns) != srt_metadata:
                        stats['errors'] += 1
                        continue

                unchanged = (matching and matching['filepath'] == filepath
                             and matching['filename'] == filename
                             and matching['file_hash'] == file_hash
                             and matching['file_size'] == video_stat.st_size
                             and matching['file_mtime_ns'] == video_stat.st_mtime_ns
                             and matching['status'] != 'Archived' and not subtitle_changed)
                if unchanged:
                    stats['unchanged'] += 1
                    continue
                values = (file_hash, filepath, filename, parsed['author'], parsed['title'],
                          parsed['lesson_date'].isoformat(), video_stat.st_mtime,
                          video_stat.st_size, video_stat.st_mtime_ns, *srt_metadata)
                if matching:
                    conn.execute("""
                        UPDATE lessons SET file_hash=?, filepath=?, filename=?, author=?, title=?,
                            lesson_date=?, file_mtime=?, file_size=?, file_mtime_ns=?,
                            transcript_size=?, transcript_mtime_ns=?,
                            transcript=CASE WHEN ? THEN ? ELSE transcript END,
                            status=CASE WHEN status='Archived' THEN COALESCE(status_before_archive,
                                CASE WHEN completed_at IS NOT NULL THEN 'Completed' ELSE 'New' END)
                                ELSE status END,
                            updated_at=CURRENT_TIMESTAMP WHERE id=?
                    """, (*values, subtitle_changed, transcript, matching['id']))
                    stats['updated'] += 1
                    # A duplicate copy later in this scan must see the migrated hash.
                    by_hash.pop(matching['file_hash'], None)
                    matching = dict(matching, file_hash=file_hash, filepath=filepath)
                    by_hash[file_hash] = matching
                else:
                    conn.execute("""
                        INSERT INTO lessons (file_hash, filepath, filename, author, title,
                            lesson_date, file_mtime, file_size, file_mtime_ns, transcript_size,
                            transcript_mtime_ns, transcript)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (*values, transcript))
                    stats['added'] += 1

            # A successfully scanned empty folder must also archive removed files.
            # Never archive after any incomplete scan, parse, or read operation.
            if not stats['errors']:
                conn.execute('CREATE TEMP TABLE synced_hashes (file_hash TEXT PRIMARY KEY)')
                conn.executemany('INSERT INTO synced_hashes VALUES (?)',
                                 [(value,) for value in current_hashes])
                stats['archived'] = conn.execute("""
                    UPDATE lessons SET status_before_archive=status, status='Archived',
                        updated_at=CURRENT_TIMESTAMP
                    WHERE status!='Archived' AND NOT EXISTS
                        (SELECT 1 FROM synced_hashes WHERE synced_hashes.file_hash=lessons.file_hash)
                """).rowcount
        self.invalidate_cache()
        return stats

    def _lesson_filter(self, status_filter=None, author_filter=None, date_from=None,
                       date_to=None, search_query=None, year_filter=None,
                       month_filter=None, tag_ids=None, transcript_query=None):
        conditions = ["l.status != 'Archived'"]
        params = []
        if status_filter:
            conditions.append('l.status IN (' + ','.join('?' for _ in status_filter) + ')')
            params.extend(status_filter)
        if author_filter:
            conditions.append('l.author = ?')
            params.append(author_filter)
        for value, operator in ((date_from, '>='), (date_to, '<=')):
            if value:
                conditions.append(f'l.lesson_date {operator} ?')
                params.append(value.isoformat() if hasattr(value, 'isoformat') else value)
        def literal_pattern(value):
            return '%' + value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        if search_query:
            conditions.append("(l.title LIKE ? ESCAPE '\\' OR l.author LIKE ? ESCAPE '\\')")
            params.extend([literal_pattern(search_query)] * 2)
        if year_filter:
            conditions.append('l.lesson_date >= ? AND l.lesson_date < ?')
            params.extend([f'{int(year_filter):04d}-01-01', f'{int(year_filter)+1:04d}-01-01'])
        if month_filter:
            conditions.append("strftime('%m', l.lesson_date) = ?")
            params.append(f'{int(month_filter):02d}')
        for tag_id in set(tag_ids or []):
            conditions.append('EXISTS (SELECT 1 FROM lesson_tags lt WHERE lt.lesson_id=l.id AND lt.tag_id=?)')
            params.append(tag_id)
        if transcript_query:
            conditions.append("LOWER(l.transcript) LIKE ? ESCAPE '\\'")
            params.append(literal_pattern(transcript_query.lower().strip()))
        return ' AND '.join(conditions), params

    def get_matching_lesson_ids(self, **filters):
        """Fetch all matching identities only, for bulk operations and playlists."""
        where, params = self._lesson_filter(**filters)
        with self._get_connection() as conn:
            return [row[0] for row in conn.execute(
                f'SELECT l.id FROM lessons l WHERE {where} ORDER BY l.lesson_date DESC, l.id DESC', params)]

    def get_library_lessons(self, **filters):
        """Return lightweight rows for the grid's own pagination and filtering."""
        where, params = self._lesson_filter(**filters)
        query = filters.get('transcript_query')
        context_column = ''
        select_params = []
        if query:
            # Extract a bounded excerpt in SQLite; do not load all transcript bodies.
            context_column = ', substr(l.transcript, max(1, instr(lower(l.transcript), ?) - 120), 320) AS context'
            select_params.append(query.lower().strip())
        with self._get_connection() as conn:
            rows = conn.execute(f'''
                SELECT l.id, author, title, lesson_date, status {context_column}
                FROM lessons l WHERE {where}
                ORDER BY lesson_date DESC, l.id DESC
            ''', [*select_params, *params]).fetchall()
        return [dict(row) for row in rows], len(rows)

    def get_paginated_lessons(self, page=1, page_size=None, **filters):
        page = 1 if page is None else page
        page_size = PAGE_SIZE if page_size is None else int(page_size)
        if page_size < 1 or int(page) < 1:
            raise ValueError('Page and page size must be positive')
        where, params = self._lesson_filter(**filters)
        with self._get_connection() as conn:
            total = conn.execute(f'SELECT COUNT(*) FROM lessons l WHERE {where}', params).fetchone()[0]
            rows = conn.execute(f"""
                SELECT l.id, file_hash, filename, filepath, author, title, lesson_date,
                       status, completed_at, created_at
                FROM lessons l WHERE {where}
                ORDER BY lesson_date DESC, l.id DESC LIMIT ? OFFSET ?
            """, [*params, page_size, (int(page)-1)*page_size]).fetchall()
            return [dict(row) for row in rows], total

    def search_transcripts(self, query, page_size=100, page=1, **filters):
        if not query or not query.strip():
            return [], 0
        lessons, total = self.get_paginated_lessons(
            page=page, page_size=page_size, transcript_query=query, **filters)
        # Fetch transcript bodies only for this visible page.
        with self._get_connection() as conn:
            for lesson in lessons:
                row = conn.execute('SELECT transcript FROM lessons WHERE id=?', (lesson['id'],)).fetchone()
                transcript = row[0] or ''
                match = transcript.lower().find(query.lower().strip())
                before = transcript[:match].split() if match >= 0 else []
                after = transcript[match:].split() if match >= 0 else []
                lesson['context'] = (('...' if len(before) > 8 else '')
                    + ' '.join(before[-8:] + after[:len(query.split())+8])
                    + ('...' if len(after) > len(query.split())+8 else ''))
        return lessons, total

    def update_status(self, lesson_id: int, status: str) -> bool:
        """Update lesson status."""
        if status not in ('New', 'In Progress', 'Completed'):
            return False

        completed_at = datetime.now().isoformat(sep=' ', timespec='microseconds')

        with self._get_connection() as conn:
            conn.execute('''
                UPDATE lessons SET status = ?,
                    completed_at = CASE WHEN ? = 'Completed' AND status != 'Completed'
                                        THEN ? ELSE completed_at END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, status, completed_at, lesson_id))

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
