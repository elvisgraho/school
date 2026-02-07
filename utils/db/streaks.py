"""
Streak tracking and goal management.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List


class StreaksMixin:
    """Mixin for streak and goal operations."""

    def get_current_streak(self) -> int:
        """Calculate current streak."""
        activity = self.get_activity_data(days=365)
        if not activity:
            return 0

        dates = sorted([datetime.strptime(row['date'], '%Y-%m-%d').date() for row in activity], reverse=True)
        if not dates:
            return 0

        today = datetime.now().date()
        streak = 0

        if dates[0] == today:
            streak = 1
            check_from = today - timedelta(days=1)
        elif dates[0] == today - timedelta(days=1):
            streak = 1
            check_from = today - timedelta(days=2)
        else:
            return 0

        current_check = check_from
        date_set = set(dates)

        while True:
            if current_check in date_set:
                streak += 1
                current_check -= timedelta(days=1)
            else:
                break

        return streak

    def get_best_streak(self) -> int:
        """Get the all-time best streak length."""
        with self._get_connection() as conn:
            row = conn.execute(
                'SELECT MAX(streak_length) as best FROM streak_history'
            ).fetchone()
            db_best = row['best'] if row and row['best'] else 0

            current = self.get_current_streak()
            return max(db_best, current)

    def save_streak_if_record(self, streak_length: int, start_date, end_date) -> bool:
        """Save streak to history. Returns True if it's a new record."""
        if streak_length <= 0:
            return False

        current_best = self.get_best_streak()
        is_record = streak_length > current_best

        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO streak_history (streak_length, start_date, end_date)
                VALUES (?, ?, ?)
            ''', (streak_length, start_date, end_date))

        return is_record

    def get_streak_recovery_info(self) -> Dict[str, Any]:
        """Get info for streak recovery message."""
        current = self.get_current_streak()
        best = self.get_best_streak()
        days_to_beat = max(0, best - current + 1) if best > current else 0

        return {
            'current': current,
            'best': best,
            'days_to_beat': days_to_beat,
            'is_at_best': current >= best and current > 0
        }

    # ==================== DAILY/WEEKLY GOAL METHODS ====================

    def get_daily_goal(self) -> int:
        """Get configured daily goal (default: 3)."""
        value = self.get_setting('daily_goal', '3')
        try:
            return int(value)
        except (ValueError, TypeError):
            return 3

    def get_weekly_goal(self) -> int:
        """Get configured weekly goal (default: 15)."""
        value = self.get_setting('weekly_goal', '15')
        try:
            return int(value)
        except (ValueError, TypeError):
            return 15

    def get_today_completions(self) -> int:
        """Get number of lessons completed today."""
        with self._get_connection() as conn:
            row = conn.execute('''
                SELECT COUNT(*) as count
                FROM lessons
                WHERE status = 'Completed' AND DATE(completed_at) = DATE('now')
            ''').fetchone()
            return row['count'] if row else 0

    def get_week_completions(self) -> int:
        """Get number of lessons completed this week (Mon-Sun)."""
        with self._get_connection() as conn:
            row = conn.execute('''
                SELECT COUNT(*) as count
                FROM lessons
                WHERE status = 'Completed'
                AND DATE(completed_at) >= DATE('now', 'weekday 0', '-6 days')
                AND DATE(completed_at) <= DATE('now')
            ''').fetchone()
            return row['count'] if row else 0

    def get_daily_progress(self) -> Dict[str, Any]:
        """Get daily goal progress."""
        completed = self.get_today_completions()
        goal = self.get_daily_goal()
        percentage = (completed / goal * 100) if goal > 0 else 0

        return {
            'completed': completed,
            'goal': goal,
            'percentage': min(percentage, 100),
            'actual_percentage': percentage,
            'is_overachieved': completed > goal
        }

    def get_weekly_progress(self) -> Dict[str, Any]:
        """Get weekly goal progress."""
        completed = self.get_week_completions()
        goal = self.get_weekly_goal()
        percentage = (completed / goal * 100) if goal > 0 else 0

        return {
            'completed': completed,
            'goal': goal,
            'percentage': min(percentage, 100),
            'actual_percentage': percentage,
            'is_overachieved': completed > goal
        }

    def get_spaced_repetition_suggestions(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get lessons for review at spaced intervals.
        
        Returns 4 unique videos per interval:
        - 2 random videos from the past
        - 2 additional random videos that have at least one tag
        """
        today = datetime.now().date()
        intervals = {
            '1_week': 7,
            '1_month': 30,
            '3_months': 90,
            '6_months': 180,
            '1_year': 365
        }

        results = {}
        with self._get_connection() as conn:
            for key, days in intervals.items():
                target_date = today - timedelta(days=days)
                date_start = target_date - timedelta(days=2)
                date_end = target_date + timedelta(days=2)
                
                # Get 2 random videos (any)
                random_rows = conn.execute('''
                    SELECT id, title, author, completed_at
                    FROM lessons
                    WHERE status = 'Completed'
                    AND DATE(completed_at) BETWEEN DATE(?) AND DATE(?)
                    ORDER BY RANDOM()
                    LIMIT 2
                ''', (date_start, date_end)).fetchall()
                
                random_ids = [row['id'] for row in random_rows]
                exclude_clause = f"AND id NOT IN ({','.join(['?'] * len(random_ids))})" if random_ids else ""
                
                # Get 2 additional random videos that have tags
                tagged_rows = conn.execute(f'''
                    SELECT DISTINCT l.id, l.title, l.author, l.completed_at
                    FROM lessons l
                    INNER JOIN lesson_tags lt ON l.id = lt.lesson_id
                    WHERE l.status = 'Completed'
                    AND DATE(l.completed_at) BETWEEN DATE(?) AND DATE(?)
                    {exclude_clause}
                    ORDER BY RANDOM()
                    LIMIT 2
                ''', [date_start, date_end] + random_ids).fetchall() if random_ids else conn.execute('''
                    SELECT DISTINCT l.id, l.title, l.author, l.completed_at
                    FROM lessons l
                    INNER JOIN lesson_tags lt ON l.id = lt.lesson_id
                    WHERE l.status = 'Completed'
                    AND DATE(l.completed_at) BETWEEN DATE(?) AND DATE(?)
                    ORDER BY RANDOM()
                    LIMIT 2
                ''', (date_start, date_end)).fetchall()
                
                # Combine results (random first, then tagged)
                combined = [dict(row) for row in random_rows] + [dict(row) for row in tagged_rows]
                results[key] = combined

        return results
