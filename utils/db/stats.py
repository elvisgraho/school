"""
Statistics, activity data, and analytics queries.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any


class StatsMixin:
    """Mixin for statistics and analytics operations."""

    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics (cached)."""
        cache_key = 'stats'
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT status, COUNT(*) as cnt
                FROM lessons
                WHERE status != 'Archived'
                GROUP BY status
            ''').fetchall()

            counts = {row['status']: row['cnt'] for row in rows}
            total = sum(counts.values())
            completed = counts.get('Completed', 0)

            result = {
                'total': total,
                'completed': completed,
                'in_progress': counts.get('In Progress', 0),
                'new': counts.get('New', 0),
                'completion_rate': (completed / total * 100) if total > 0 else 0
            }
            self._set_cache(cache_key, result)
            return result

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

    def get_recent_completions(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get the most recently completed lessons."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT title, author, completed_at
                FROM lessons
                WHERE status = 'Completed'
                ORDER BY completed_at DESC
                LIMIT ?
            ''', (limit,)).fetchall()
            return [dict(row) for row in rows]

    def get_day_of_week_stats(self) -> List[Dict[str, Any]]:
        """Get completions grouped by day of week (0=Monday)."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT strftime('%w', completed_at) as dow, COUNT(*) as count
                FROM lessons
                WHERE status = 'Completed'
                GROUP BY dow
            ''').fetchall()

            result = []
            for row in rows:
                sqlite_dow = int(row['dow'])
                python_dow = (sqlite_dow - 1) % 7
                result.append({'day_index': python_dow, 'count': row['count']})
            return result

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

    def get_monthly_comparison(self) -> Dict[str, Any]:
        """Compare this month to last month."""
        with self._get_connection() as conn:
            current = conn.execute('''
                SELECT COUNT(*) as count
                FROM lessons
                WHERE status = 'Completed'
                AND strftime('%Y-%m', completed_at) = strftime('%Y-%m', 'now')
            ''').fetchone()['count']

            previous = conn.execute('''
                SELECT COUNT(*) as count
                FROM lessons
                WHERE status = 'Completed'
                AND strftime('%Y-%m', completed_at) = strftime('%Y-%m', 'now', '-1 month')
            ''').fetchone()['count']

            if previous > 0:
                change_percent = ((current - previous) / previous) * 100
            else:
                change_percent = 100 if current > 0 else 0

            return {
                'current': current,
                'previous': previous,
                'change_percent': round(change_percent, 1),
                'direction': 'up' if current >= previous else 'down'
            }

    def get_last_7_days_activity(self) -> List[Dict[str, Any]]:
        """Get completion counts for each of the last 7 days."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT DATE(completed_at) as date, COUNT(*) as count
                FROM lessons
                WHERE status = 'Completed'
                AND DATE(completed_at) >= DATE('now', '-6 days')
                GROUP BY DATE(completed_at)
            ''').fetchall()

            result = {}
            for row in rows:
                result[row['date']] = row['count']

            today = datetime.now().date()
            full_week = []
            for i in range(6, -1, -1):
                date = today - timedelta(days=i)
                date_str = date.strftime('%Y-%m-%d')
                full_week.append({
                    'date': date_str,
                    'day': date.strftime('%a'),
                    'count': result.get(date_str, 0)
                })

            return full_week

    def get_lessons_completed_on_date(self, date_str: str) -> List[Dict[str, Any]]:
        """Get all lessons completed on a specific date."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT id, title, author, completed_at
                FROM lessons
                WHERE status = 'Completed' AND DATE(completed_at) = ?
                ORDER BY completed_at DESC
            ''', (date_str,)).fetchall()
            return [dict(row) for row in rows]

    def get_available_years_for_heatmap(self) -> List[int]:
        """Get years that have completion data."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT DISTINCT CAST(strftime('%Y', completed_at) AS INTEGER) as year
                FROM lessons
                WHERE status = 'Completed' AND completed_at IS NOT NULL
                ORDER BY year DESC
            ''').fetchall()
            return [row['year'] for row in rows if row['year']]

    def get_activity_data_for_year(self, year: int) -> List[Dict[str, Any]]:
        """Get activity data for a specific year with lesson details."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT DATE(completed_at) as date, COUNT(*) as count,
                       GROUP_CONCAT(title, ', ') as titles
                FROM lessons
                WHERE status = 'Completed'
                AND strftime('%Y', completed_at) = ?
                GROUP BY DATE(completed_at)
            ''', (str(year),)).fetchall()
            return [dict(row) for row in rows]
