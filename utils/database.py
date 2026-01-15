"""
Database utilities for Guitar Shed.
Manages SQLite database for lesson progress tracking.
Optimized for 15,000+ video files.
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple


DB_FILE = 'progress.db'
PAGE_SIZE = 50
DEFAULT_PAGE_SIZE = 9999


class DatabaseManager:
    """SQLite database manager for guitar lesson progress tracking."""
    
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        return conn
    
    def _init_db(self):
        """Initialize the database schema."""
        with self._get_connection() as conn:
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
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
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
    
    def sync_folder(self, folder_path: str, parse_func) -> Dict[str, Any]:
        """Sync lessons from folder using diff engine with content-based hashing."""
        import hashlib
        
        stats = {'added': 0, 'updated': 0, 'archived': 0, 'errors': 0, 'unchanged': 0}
        
        if not os.path.isdir(folder_path):
            return stats
        
        def compute_file_hash(filepath: str) -> str:
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
            except Exception:
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
                                file_data.append((file_hash, filepath, entry.name, mtime))
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
            rows = conn.execute('SELECT id, file_hash, filepath, filename, status, file_mtime FROM lessons').fetchall()
            for row in rows:
                existing_lookup[row['file_hash']] = dict(row)
            
            to_insert = []
            to_update = []
            
            for file_hash, filepath, filename, mtime in file_data:
                parsed = parse_func(filename)
                if not parsed:
                    stats['errors'] += 1
                    continue
                
                current_hashes.add(file_hash)
                
                if file_hash in existing_lookup:
                    existing = existing_lookup[file_hash]
                    if existing['filepath'] != filepath:
                        to_update.append({
                            'id': existing['id'],
                            'filename': filename,
                            'filepath': filepath,
                            'mtime': mtime,
                            'status': existing['status']
                        })
                        stats['updated'] += 1
                    elif existing.get('file_mtime', 0) != mtime:
                        to_update.append({
                            'id': existing['id'],
                            'filename': filename,
                            'filepath': filepath,
                            'mtime': mtime,
                            'status': existing['status']
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
                        'mtime': mtime
                    })
                    stats['added'] += 1
            
            if to_insert:
                conn.executemany('''
                    INSERT INTO lessons (file_hash, filepath, filename, author, title, lesson_date, file_mtime, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'New')
                ''', [(r['file_hash'], r['filepath'], r['filename'], r['author'], r['title'], r['lesson_date'], r['mtime']) 
                      for r in to_insert])
            
            if to_update:
                conn.executemany('''
                    UPDATE lessons SET filename = ?, filepath = ?, file_mtime = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', [(r['filename'], r['filepath'], r['mtime'], r['id']) for r in to_update])
            
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
                              month_filter: Optional[int] = None) -> Tuple[List[Dict[str, Any]], int]:
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
        
        where_clause = ' AND '.join(conditions)
        
        with self._get_connection() as conn:
            total = conn.execute(f'SELECT COUNT(*) FROM lessons WHERE {where_clause}', params).fetchone()[0]
            
            offset = (page - 1) * page_size
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
    
    def update_status(self, lesson_id: int, status: str) -> bool:
        """Update lesson status."""
        if status not in ('New', 'In Progress', 'Completed'):
            return False
        
        completed_at = datetime.now() if status == 'Completed' else None
        
        with self._get_connection() as conn:
            conn.execute('''
                UPDATE lessons SET status = ?, completed_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, completed_at, lesson_id))
        
        return True
    
    def get_lesson_by_id(self, lesson_id: int) -> Optional[Dict[str, Any]]:
        """Get a lesson by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                'SELECT * FROM lessons WHERE id = ?', (lesson_id,)
            ).fetchone()
            return dict(row) if row else None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics."""
        with self._get_connection() as conn:
            total = conn.execute('SELECT COUNT(*) FROM lessons WHERE status != "Archived"').fetchone()[0]
            completed = conn.execute('SELECT COUNT(*) FROM lessons WHERE status = "Completed"').fetchone()[0]
            in_progress = conn.execute('SELECT COUNT(*) FROM lessons WHERE status = "In Progress"').fetchone()[0]
            new_count = conn.execute('SELECT COUNT(*) FROM lessons WHERE status = "New"').fetchone()[0]
            
            completion_rate = (completed / total * 100) if total > 0 else 0
            
            return {
                'total': total,
                'completed': completed,
                'in_progress': in_progress,
                'new': new_count,
                'completion_rate': completion_rate
            }
    
    def get_activity_data(self, days: int = 365) -> List[Dict[str, Any]]:
        """Get completion activity data."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT DATE(completed_at) as date, COUNT(*) as count
                FROM lessons 
                WHERE status = 'Completed' AND completed_at >= DATE('now', ?)
                GROUP BY DATE(completed_at)
            ''', (f'-{days} days',)).fetchall()
            return [dict(row) for row in rows]
    
    def get_monthly_velocity(self, months: int = 12) -> List[Dict[str, Any]]:
        """Get monthly completion counts."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT strftime('%Y-%m', completed_at) as month, COUNT(*) as count
                FROM lessons 
                WHERE status = 'Completed' AND completed_at >= DATE('now', ?)
                GROUP BY strftime('%Y-%m', completed_at)
                ORDER BY month DESC
            ''', (f'-{months} months',)).fetchall()
            return [dict(row) for row in rows]
    
    def get_author_breakdown(self) -> List[Dict[str, Any]]:
        """Get completion breakdown by author."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT author, COUNT(*) as count
                FROM lessons 
                WHERE status = 'Completed'
                GROUP BY author
                ORDER BY count DESC
            ''').fetchall()
            return [dict(row) for row in rows]
    
    def get_current_streak(self) -> int:
        """Calculate current streak."""
        activity = self.get_activity_data(days=365)
        if not activity:
            return 0
        
        dates = sorted([datetime.strptime(row['date'], '%Y-%m-%d').date() for row in activity])
        if not dates:
            return 0
        
        today = datetime.now().date()
        streak = 0
        check_date = today
        
        if dates[-1] < check_date - timedelta(days=1):
            return 0
        
        i = len(dates) - 1
        while i >= 0:
            if dates[i] == check_date or dates[i] == check_date - timedelta(days=1):
                streak += 1
                check_date = dates[i] - timedelta(days=1)
                i -= 1
            elif dates[i] < check_date - timedelta(days=1):
                break
            else:
                i -= 1
        
        return streak
    
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
    
    def get_backlog_trend(self) -> List[Dict[str, Any]]:
        """Get backlog trend data."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT DATE(completed_at) as date,
                       COUNT(*) as completed_on_date
                FROM lessons
                WHERE status = 'Completed'
                GROUP BY DATE(completed_at)
                ORDER BY date ASC
            ''').fetchall()
            
            result = []
            cumulative_completed = 0
            total = conn.execute('SELECT COUNT(*) FROM lessons WHERE status != "Archived"').fetchone()[0]
            
            for row in rows:
                cumulative_completed += row['completed_on_date']
                result.append({
                    'date': row['date'],
                    'completed_cumulative': cumulative_completed,
                    'backlog': total - cumulative_completed
                })
            
            return result
    
    def get_years_with_lessons(self) -> List[int]:
        """Get list of years with lessons."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT DISTINCT CAST(strftime('%Y', lesson_date) AS INTEGER) as year
                FROM lessons
                WHERE status != 'Archived'
                ORDER BY year DESC
            ''').fetchall()
            return [row[0] for row in rows]

    def get_in_progress_lessons(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get in-progress lessons ordered by most recently started."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM lessons
                WHERE status = 'In Progress'
                ORDER BY updated_at DESC
                LIMIT ?
            ''', (limit,)).fetchall()
            return [dict(row) for row in rows]
