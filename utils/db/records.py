"""
Personal records tracking and computation.
"""

from datetime import datetime, timedelta
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

    def _save_personal_record(self, record_type: str, value: int, achieved_date: str = None, details: str = None) -> bool:
        """Save a personal record only when its value is strictly higher."""
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO personal_records (record_type, value, achieved_date, details, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(record_type) DO UPDATE SET
                    value = ?, achieved_date = ?, details = ?, updated_at = CURRENT_TIMESTAMP
                WHERE excluded.value > personal_records.value
            ''', (record_type, value, achieved_date, details, value, achieved_date, details))
            return cursor.rowcount > 0

    def get_most_lessons_in_day(self) -> Dict[str, Any]:
        """Calculate most lessons completed in a single day."""
        with self._get_connection() as conn:
            row = conn.execute('''
                SELECT DATE(completed_at) as date, COUNT(*) as count
                FROM lessons
                WHERE status = 'Completed' AND completed_at IS NOT NULL
                GROUP BY DATE(completed_at)
                ORDER BY count DESC, date ASC
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
                WHERE status = 'Completed' AND completed_at IS NOT NULL
                GROUP BY week
                ORDER BY count DESC, week ASC
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
                WHERE status = 'Completed' AND completed_at IS NOT NULL
                GROUP BY month
                ORDER BY count DESC, month ASC
                LIMIT 1
            ''').fetchone()

            if row:
                return {'value': row['count'], 'month': row['month']}
            return {'value': 0, 'month': None}

    def get_most_consistent_week(self) -> Dict[str, Any]:
        """Find the calendar week with activity on the most distinct days."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT DATE(completed_at) as date,
                       COUNT(*) as count
                FROM lessons
                WHERE status = 'Completed' AND completed_at IS NOT NULL
                GROUP BY date
                ORDER BY date
            ''').fetchall()

            if not rows:
                return {'active_days': 0, 'week_start': None, 'week_end': None, 'total_lessons': 0}

            weeks = {}
            for row in rows:
                completed_date = datetime.strptime(row['date'], '%Y-%m-%d').date()
                week_start = completed_date - timedelta(days=completed_date.weekday())
                week = weeks.setdefault(week_start, {'active_days': 0, 'total_lessons': 0, 'daily_counts': []})
                week['active_days'] += 1
                week['total_lessons'] += row['count']
                week['daily_counts'].append(row['count'])

            for week in weeks.values():
                # Include missed days in the distribution, not just active days.
                all_day_counts = week['daily_counts'] + [0] * (7 - week['active_days'])
                week['average_per_day'] = week['total_lessons'] / 7
                week['variance'] = sum(
                    (count - week['average_per_day']) ** 2 for count in all_day_counts
                ) / 7

            # Prioritize showing up on more days, then the highest seven-day
            # average. For equal averages, prefer the more evenly paced week.
            best_start, best_week = max(
                weeks.items(),
                key=lambda item: (
                    item[1]['active_days'],
                    item[1]['average_per_day'],
                    -item[1]['variance'],
                )
            )
            return {
                'active_days': best_week['active_days'],
                'total_lessons': best_week['total_lessons'],
                'average_per_day': round(best_week['average_per_day'], 1),
                'week_start': best_start.isoformat(),
                'week_end': (best_start + timedelta(days=6)).isoformat(),
            }

    def get_best_rolling_period(self, days: int) -> Dict[str, Any]:
        """Return the highest lesson total in any rolling calendar-day period."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT DATE(completed_at) AS date, COUNT(*) AS count
                FROM lessons
                WHERE status = 'Completed' AND completed_at IS NOT NULL
                GROUP BY date
                ORDER BY date
            ''').fetchall()

        if not rows:
            return {'value': 0, 'start_date': None, 'end_date': None}

        daily_counts = {
            datetime.strptime(row['date'], '%Y-%m-%d').date(): row['count']
            for row in rows
        }
        best = {'value': 0, 'start_date': None, 'end_date': None}
        for end_date in daily_counts:
            start_date = end_date - timedelta(days=days - 1)
            total = sum(daily_counts.get(start_date + timedelta(days=offset), 0) for offset in range(days))
            if total > best['value']:
                best = {
                    'value': total,
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                }
        return best

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
        # Encode the ranking criteria so equal active-day scores only replace a
        # record when their weekly total (and thus average) is genuinely higher.
        consistency_score = consistent['active_days'] * 1_000_000 + consistent['total_lessons']
        self._save_personal_record('most_consistent', consistency_score,
                                   consistent['week_end'], details=consistent['week_start'])
        records['most_consistent'] = consistent

        rolling_week = self.get_best_rolling_period(7)
        self._save_personal_record('best_rolling_7', rolling_week['value'], rolling_week['end_date'],
                                   details=rolling_week['start_date'])
        records['best_rolling_7'] = rolling_week

        rolling_month = self.get_best_rolling_period(30)
        self._save_personal_record('best_rolling_30', rolling_month['value'], rolling_month['end_date'],
                                   details=rolling_month['start_date'])
        records['best_rolling_30'] = rolling_month

        return records
