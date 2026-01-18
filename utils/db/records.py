"""
Personal records tracking and computation.
"""

from datetime import datetime
from typing import Dict, Any


class RecordsMixin:
    """Mixin for personal records operations."""

    def get_personal_records(self) -> Dict[str, Any]:
        """Get all personal records from database."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT record_type, value, achieved_date, details
                FROM personal_records
            ''').fetchall()

            records = {}
            for row in rows:
                records[row['record_type']] = {
                    'value': row['value'],
                    'achieved_date': row['achieved_date'],
                    'details': row['details']
                }
            return records

    def _save_personal_record(self, record_type: str, value: int, achieved_date: str = None, details: str = None) -> None:
        """Save a personal record."""
        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO personal_records (record_type, value, achieved_date, details, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(record_type) DO UPDATE SET
                    value = ?, achieved_date = ?, details = ?, updated_at = CURRENT_TIMESTAMP
            ''', (record_type, value, achieved_date, details, value, achieved_date, details))

    def get_most_lessons_in_day(self) -> Dict[str, Any]:
        """Calculate most lessons completed in a single day."""
        with self._get_connection() as conn:
            row = conn.execute('''
                SELECT DATE(completed_at) as date, COUNT(*) as count
                FROM lessons
                WHERE status = 'Completed'
                GROUP BY DATE(completed_at)
                ORDER BY count DESC
                LIMIT 1
            ''').fetchone()

            if row:
                return {'value': row['count'], 'date': row['date']}
            return {'value': 0, 'date': None}

    def get_most_lessons_in_week(self) -> Dict[str, Any]:
        """Calculate most lessons completed in a single week."""
        with self._get_connection() as conn:
            row = conn.execute('''
                SELECT strftime('%Y-%W', completed_at) as week, COUNT(*) as count
                FROM lessons
                WHERE status = 'Completed'
                GROUP BY week
                ORDER BY count DESC
                LIMIT 1
            ''').fetchone()

            if row:
                return {'value': row['count'], 'week': row['week']}
            return {'value': 0, 'week': None}

    def get_most_lessons_in_month(self) -> Dict[str, Any]:
        """Calculate most lessons completed in a single month."""
        with self._get_connection() as conn:
            row = conn.execute('''
                SELECT strftime('%Y-%m', completed_at) as month, COUNT(*) as count
                FROM lessons
                WHERE status = 'Completed'
                GROUP BY month
                ORDER BY count DESC
                LIMIT 1
            ''').fetchone()

            if row:
                return {'value': row['count'], 'month': row['month']}
            return {'value': 0, 'month': None}

    def get_most_consistent_week(self) -> Dict[str, Any]:
        """Find week with lowest variance in daily completions (most consistent)."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT strftime('%Y-%W', completed_at) as week,
                       DATE(completed_at) as date,
                       COUNT(*) as count
                FROM lessons
                WHERE status = 'Completed'
                GROUP BY week, date
                ORDER BY week, date
            ''').fetchall()

            if not rows:
                return {'value': 0, 'week': None, 'avg_per_day': 0}

            weeks = {}
            for row in rows:
                week = row['week']
                if week not in weeks:
                    weeks[week] = []
                weeks[week].append(row['count'])

            best_week = None
            best_variance = float('inf')
            best_avg = 0

            for week, counts in weeks.items():
                if len(counts) >= 3:
                    avg = sum(counts) / len(counts)
                    variance = sum((c - avg) ** 2 for c in counts) / len(counts)
                    if variance < best_variance:
                        best_variance = variance
                        best_week = week
                        best_avg = avg

            if best_week:
                return {'week': best_week, 'variance': best_variance, 'avg_per_day': round(best_avg, 1)}
            return {'week': None, 'variance': 0, 'avg_per_day': 0}

    def compute_and_update_records(self) -> Dict[str, Any]:
        """Recompute all personal records and save to database."""
        records = {}

        best_streak = self.get_best_streak()
        self._save_personal_record('best_streak', best_streak)
        records['best_streak'] = {'value': best_streak}

        day_record = self.get_most_lessons_in_day()
        self._save_personal_record('most_day', day_record['value'], day_record.get('date'))
        records['most_day'] = day_record

        week_record = self.get_most_lessons_in_week()
        self._save_personal_record('most_week', week_record['value'], details=week_record.get('week'))
        records['most_week'] = week_record

        month_record = self.get_most_lessons_in_month()
        self._save_personal_record('most_month', month_record['value'], details=month_record.get('month'))
        records['most_month'] = month_record

        consistent = self.get_most_consistent_week()
        self._save_personal_record('most_consistent', int(consistent.get('avg_per_day', 0) * 10),
                                   details=consistent.get('week'))
        records['most_consistent'] = consistent

        return records
