"""
Data export functionality.
"""

import json
from datetime import datetime


class ExportMixin:
    """Mixin for data export operations."""

    def export_statistics_json(self) -> str:
        """Export comprehensive statistics as JSON for LLM analysis."""
        stats = self.get_stats()
        streak_info = self.get_streak_recovery_info()
        daily_progress = self.get_daily_progress()
        weekly_progress = self.get_weekly_progress()
        records = self.compute_and_update_records()
        monthly = self.get_monthly_velocity(months=12)
        dow_stats = self.get_day_of_week_stats()
        monthly_comparison = self.get_monthly_comparison()
        last_7_days = self.get_last_7_days_activity()

        export_data = {
            'export_date': datetime.now().isoformat(),
            'library_stats': stats,
            'streak': streak_info,
            'daily_progress': daily_progress,
            'weekly_progress': weekly_progress,
            'personal_records': records,
            'monthly_completions': monthly,
            'day_of_week_distribution': dow_stats,
            'monthly_comparison': monthly_comparison,
            'last_7_days': last_7_days
        }

        return json.dumps(export_data, indent=2, default=str)
