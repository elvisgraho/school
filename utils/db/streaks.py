"""
Streak tracking and goal management.
"""

from datetime import date, datetime, timedelta
from math import ceil
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
        return self._get_longest_streak()

    def save_streak_if_record(self, streak_length: int, start_date, end_date) -> bool:
        """Save streak to history. Returns True if it's a new record."""
        if streak_length <= 0:
            return False

        current_best = self._get_longest_streak()
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
        prior_best = self._get_longest_streak(exclude_current=True)
        days_to_beat = max(0, best - current + 1) if best > current else 0

        return {
            'current': current,
            'best': best,
            'days_to_beat': days_to_beat,
            # Only celebrate when this active run has actually surpassed a
            # previous run.  Including the current run in ``best`` alone
            # would make every streak appear to be a personal best.
            'is_at_best': prior_best > 0 and current > prior_best
        }

    def _get_longest_streak(self, exclude_current: bool = False) -> int:
        """Return the longest completion streak, optionally excluding today’s run."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT DISTINCT DATE(completed_at) AS date
                FROM lessons
                WHERE status = 'Completed' AND completed_at IS NOT NULL
                ORDER BY date
            ''').fetchall()

        dates = [datetime.strptime(row['date'], '%Y-%m-%d').date() for row in rows]
        if exclude_current and dates:
            current = self.get_current_streak()
            if current:
                active_end = date.today() if date.today() in dates else date.today() - timedelta(days=1)
                cutoff = active_end - timedelta(days=current - 1)
                dates = [completed_date for completed_date in dates if completed_date < cutoff]

        longest = run = 0
        previous = None
        for completed_date in dates:
            run = run + 1 if previous and completed_date == previous + timedelta(days=1) else 1
            longest = max(longest, run)
            previous = completed_date
        return longest

    # ==================== DAILY/WEEKLY GOAL METHODS ====================

    def get_daily_goal(self) -> int:
        """Get configured daily goal (default: 3)."""
        value = self.get_setting('daily_goal', '3')
        try:
            return int(value)
        except (ValueError, TypeError):
            return 3

    def get_weekly_goal(self) -> int:
        """Return the weekly target derived from the daily goal."""
        return self.get_daily_goal() * 7

    def get_remaining_lessons(self) -> int:
        """Return non-archived lessons that are not yet completed."""
        with self._get_connection() as conn:
            row = conn.execute('''
                SELECT COUNT(*) AS count
                FROM lessons
                WHERE status NOT IN ('Completed', 'Archived')
            ''').fetchone()
            return row['count'] if row else 0

    def calculate_deadline_daily_goal(self, end_date: date) -> int:
        """Calculate the whole-lesson daily target needed through ``end_date``."""
        days_remaining = (end_date - date.today()).days + 1
        if days_remaining <= 0:
            raise ValueError('The target date must be in the future.')
        return ceil(self.get_remaining_lessons() / days_remaining)

    def refresh_deadline_goal(self) -> bool:
        """Refresh an enabled deadline goal and return whether its daily target changed."""
        if self.get_setting('deadline_goal_enabled', 'false') != 'true':
            return False

        raw_end_date = self.get_setting('deadline_goal_date')
        try:
            end_date = date.fromisoformat(raw_end_date)
            daily_goal = self.calculate_deadline_daily_goal(end_date)
        except (TypeError, ValueError):
            return False

        if self.get_daily_goal() == daily_goal:
            return False
        self.set_setting('daily_goal', str(daily_goal))
        return True

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
