"""Run the actual Streamlit app against disposable databases."""
from datetime import date, timedelta
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

from utils import DatabaseManager

ROOT = Path(__file__).resolve().parents[1]


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.original_instance = DatabaseManager._instance
        DatabaseManager._instance = None
        self.addCleanup(setattr, DatabaseManager, '_instance', self.original_instance)
        self.db = DatabaseManager(str(Path(self.temp.name) / 'progress.db'))
        st.cache_resource.clear()
        self.addCleanup(st.cache_resource.clear)
        factory = patch('utils.DatabaseManager', return_value=self.db)
        factory.start()
        self.addCleanup(factory.stop)
        self.app = AppTest.from_file(str(ROOT / 'ui_app.py'), default_timeout=30)

    def assert_app_ok(self):
        self.assertEqual(list(self.app.exception), [])

    def seed_lessons(self):
        today = date.today().isoformat()
        with self.db._get_connection() as conn:
            for index, status in enumerate(('New', 'In Progress', 'Completed'), 1):
                video = Path(self.temp.name) / f'video{index}.mp4'
                video.write_bytes(b'test video')
                conn.execute('''
                    INSERT INTO lessons (file_hash, filepath, filename, author, title,
                                         lesson_date, status, completed_at, transcript)
                    VALUES (?, ?, ?, 'Teacher', ?, ?, ?, ?, 'Practice scales slowly')
                ''', (str(index), str(video), video.name, f'Lesson {index}', today,
                      status, today if status == 'Completed' else None))
        self.db.invalidate_cache()

    def test_empty_dashboard(self):
        self.app.run()
        self.assert_app_ok()
        self.assertEqual([tab.label for tab in self.app.tabs],
                         ['DISCOVERY', 'LIBRARY', 'ANALYTICS'])

    def test_populated_dashboard_search_and_practice(self):
        self.seed_lessons()
        self.app.run()
        self.assert_app_ok()
        self.app.text_input(key='lib_search').set_value('Lesson').run()
        self.assert_app_ok()
        self.app.session_state['selected_lesson_id'] = 1
        self.app.run()
        self.assert_app_ok()
        next(button for button in self.app.button if button.label == 'Start').click().run()
        self.assert_app_ok()
        self.assertEqual(self.db.get_lesson_by_id(1)['status'], 'In Progress')
        next(button for button in self.app.button if button.label == 'Complete').click().run()
        self.assert_app_ok()
        self.assertEqual(self.db.get_lesson_by_id(1)['status'], 'Completed')

    def test_disable_zero_deadline_goal(self):
        self.db.set_setting('deadline_goal_enabled', 'true')
        self.db.set_setting('deadline_goal_date', (date.today() + timedelta(days=30)).isoformat())
        self.app.run()
        self.assert_app_ok()
        self.assertEqual(self.app.number_input(key='settings_daily_goal').value, 0)
        self.app.toggle(key='settings_deadline_enabled').set_value(False).run()
        self.assert_app_ok()
        self.assertGreaterEqual(self.app.number_input(key='settings_daily_goal').value, 1)
        next(button for button in self.app.button if button.label == 'Save Goals').click().run()
        self.assert_app_ok()
        self.assertGreaterEqual(self.db.get_daily_goal(), 1)

    def test_deadline_target_replaces_manual_widget_value(self):
        self.seed_lessons()
        self.app.run()
        self.app.number_input(key='settings_daily_goal').set_value(8).run()
        self.app.toggle(key='settings_deadline_enabled').set_value(True).run()
        self.assert_app_ok()
        self.assertEqual(self.app.number_input(key='settings_daily_goal').value, 1)
        self.db.update_status(3, 'New')
        self.app.date_input(key='settings_deadline_date').set_value(
            date.today() + timedelta(days=1)).run()
        self.assert_app_ok()
        self.assertEqual(self.app.number_input(key='settings_daily_goal').value, 2)

    def test_transcript_tagging_and_playlist(self):
        self.seed_lessons()
        self.app.run()
        self.app.text_input(key='lib_transcript_search').set_value('scales').run()
        self.assert_app_ok()
        self.app.button(key='bulk_tag_btn').click().run()
        self.assert_app_ok()
        self.assertEqual(len(self.db.get_lesson_tags(1)), 1)
        self.app.button(key='start_playlist_btn').click().run()
        self.assert_app_ok()
        self.assertEqual(len(self.app.session_state['playlist_ids']), 2)
        first_id = self.app.session_state['selected_lesson_id']
        next(button for button in self.app.button if button.label == 'Complete & Next').click().run()
        self.assert_app_ok()
        self.assertEqual(self.db.get_lesson_by_id(first_id)['status'], 'Completed')
        self.assertNotEqual(self.app.session_state['selected_lesson_id'], first_id)

    def test_library_sync(self):
        video = Path(self.temp.name) / 'Teacher - Scales 10-10-2026.mp4'
        video.write_bytes(b'new video')
        self.app.session_state['folder_path'] = self.temp.name
        self.app.run()
        next(button for button in self.app.button if button.label == 'Sync Library').click().run()
        self.assert_app_ok()
        self.assertEqual(self.db.get_stats()['total'], 1)

    def test_large_saved_manual_goal(self):
        self.db.set_setting('daily_goal', '25')
        self.app.run()
        self.assert_app_ok()
        self.assertEqual(self.app.number_input(key='settings_daily_goal').value, 25)

    def test_historical_heatmap_date_is_browsable(self):
        self.seed_lessons()
        with self.db._get_connection() as conn:
            conn.execute("INSERT INTO completion_events(lesson_id,completed_at) VALUES (1,'2024-01-01')")
        self.db.invalidate_cache()
        self.app.run()
        self.app.session_state['browse_by_date'] = date(2024, 1, 1)
        self.app.run()
        self.assert_app_ok()
        self.assertEqual(self.app.date_input(key='analytics_browse_date').value, date(2024, 1, 1))

    def test_pagination_and_bulk_actions_include_results_past_first_page(self):
        self.seed_lessons()
        with self.db._get_connection() as conn:
            conn.executemany('''INSERT INTO lessons(file_hash,filepath,filename,author,title,
                                lesson_date,transcript)
                                VALUES (?,'missing.mp4','missing.mp4','Teacher',?,'2026-10-10','scales')''',
                             [(f'bulk{i}', f'Extra {i}') for i in range(1100)])
        self.db.invalidate_cache()
        self.app.session_state['lib_page'] = None  # State left by the broken page input.
        from utils.ui.library import AgGrid
        with patch('utils.ui.library.AgGrid', wraps=AgGrid) as grid:
            self.app.run()
            self.app.text_input(key='lib_transcript_search').set_value('scales').run()
            rows = grid.call_args.args[0]
            options = grid.call_args.kwargs['gridOptions']
            self.assertEqual(len(rows), 1102)
            self.assertTrue(options['pagination'])
            self.assertEqual(options['paginationPageSize'], 100)
        self.assertFalse(any(widget.label == 'Page' for widget in self.app.number_input))
        self.assert_app_ok()
        self.app.button(key='bulk_tag_btn').click().run()
        self.assert_app_ok()
        tag = next(tag for tag in self.db.get_all_tags() if tag['name'] == 'scales')
        self.assertEqual(len(self.db.get_matching_lesson_ids(tag_ids=[tag['id']])), 1102)
        self.app.button(key='start_playlist_btn').click().run()
        self.assert_app_ok()
        self.assertEqual(len(self.app.session_state['playlist_ids']), 1102)

    def test_rendering_dashboard_does_not_prepare_export(self):
        with patch.object(self.db, 'export_statistics_json', wraps=self.db.export_statistics_json) as export:
            self.app.run()
            self.assert_app_ok()
            export.assert_not_called()

    def test_server_import_does_not_load_grid_before_script_context(self):
        result = subprocess.run([
            sys.executable, '-c',
            "import utils.video_server; import sys; assert 'st_aggrid' not in sys.modules",
        ], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
