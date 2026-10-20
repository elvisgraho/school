"""Data preservation, sync, pagination, and transaction regressions."""
from datetime import date, timedelta
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from utils import DatabaseManager, parse_filename


class DatabaseRegressionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original_instance = DatabaseManager._instance
        DatabaseManager._instance = None
        self.addCleanup(setattr, DatabaseManager, '_instance', self.original_instance)
        self.db = DatabaseManager(str(self.root / 'progress.db'))
        self.videos = self.root / 'videos'
        self.videos.mkdir()

    def video(self, title, content):
        path = self.videos / f'Teacher - {title} 10-10-2026.mp4'
        path.write_bytes(content)
        return path

    def seed(self, count=1, completed=False):
        today = date.today().isoformat()
        with self.db._get_connection() as conn:
            conn.executemany('''
                INSERT INTO lessons(file_hash, filepath, filename, author, title,
                                    lesson_date, status, completed_at, transcript)
                VALUES (?, 'missing.mp4', 'missing.mp4', 'Teacher', ?, ?, ?, ?, 'scales 50%_')
            ''', [(f'seed{i}', f'Lesson {i}', today,
                   'Completed' if completed else 'New', today if completed else None)
                  for i in range(count)])
        self.db.invalidate_cache()

    def test_full_hash_keeps_videos_with_same_ends_distinct(self):
        self.video('A', b'h'*8192 + b'A'*20000 + b't'*8192)
        self.video('B', b'h'*8192 + b'B'*20000 + b't'*8192)
        result = self.db.sync_folder(str(self.videos), parse_filename)
        self.assertEqual(result['added'], 2)
        self.assertEqual(self.db.get_stats()['total'], 2)

    def test_completion_hours_use_event_times_and_skip_unknown_hours(self):
        self.assertEqual(self.db.get_completion_hour_stats(), [])
        self.seed(3)
        with self.db._get_connection() as conn:
            conn.executemany('INSERT INTO completion_events(lesson_id, completed_at) VALUES (?, ?)', [
                (1, '2026-10-18 00:00:00'),  # Sunday midnight is a real hour.
                (1, '2026-10-19 06:15:00.123456'),
                (2, '2026-10-19 06:59:59'),
                (2, '2026-10-19T20:30:00'),
                (3, '2026-10-18T23:45:00+02:00'),  # Preserve recorded wall time.
                (3, '2026-10-19'),  # Legacy dates must not invent midnight activity.
                (3, '2026-10-19  '),
                (3, 'invalid timestamp'),
                (3, '2026-10-19 24:00:00'),
            ])
            conn.execute("UPDATE lessons SET status='Archived' WHERE id=2")
            conn.execute("UPDATE lessons SET completed_at='2026-10-20 12:00:00' WHERE id=1")

        self.assertEqual(self.db.get_completion_hour_stats(), [
            {'day_index': 0, 'hour': 6, 'count': 2},
            {'day_index': 0, 'hour': 20, 'count': 1},
            {'day_index': 6, 'hour': 0, 'count': 1},
            {'day_index': 6, 'hour': 23, 'count': 1},
        ])

    def test_metadata_cleanup_preserves_progress_tags_and_transcripts(self):
        self.seed(3, completed=True)
        with self.db._get_connection() as conn:
            conn.execute("UPDATE lessons SET author='McTeacher',title='remem@gmx.de - Scales' WHERE id=1")
            conn.execute("UPDATE lessons SET author='McTeacher' WHERE id=2")
            conn.execute("UPDATE lessons SET author='mcteacher',title='  ' WHERE id=3")
            history = conn.execute('SELECT * FROM completion_events ORDER BY id').fetchall()
        tag = self.db.create_tag('favorite')
        self.db.add_tag_to_lesson(3, tag)

        self.assertEqual(self.db.normalize_lesson_metadata(), {'authors': 1, 'titles': 2})
        self.assertEqual(self.db.get_library_authors(), ['McTeacher'])
        self.assertEqual(self.db.get_author_breakdown()[0]['count'], 3)
        self.assertEqual(self.db.get_paginated_lessons(author_filter='MCTEACHER')[1], 3)
        self.assertEqual(self.db.get_lesson_by_id(1)['title'], 'Scales')
        unnamed = self.db.get_lesson_by_id(3)
        self.assertEqual(unnamed['title'], f'Lesson by McTeacher ({date.today().isoformat()})')
        self.assertEqual(unnamed['status'], 'Completed')
        self.assertEqual(unnamed['completed_at'], date.today().isoformat())
        self.assertEqual(unnamed['transcript'], 'scales 50%_')
        self.assertEqual(self.db.get_lesson_tags(3)[0]['id'], tag)
        with self.db._get_connection() as conn:
            self.assertEqual(conn.execute('SELECT * FROM completion_events ORDER BY id').fetchall(), history)
        self.assertEqual(self.db.normalize_lesson_metadata(), {'authors': 0, 'titles': 0})

    def test_new_sync_cleans_names_and_reuses_author_capitalization(self):
        self.seed()
        with self.db._get_connection() as conn:
            conn.execute("UPDATE lessons SET author='McTeacher'")
        for index, filename in enumerate((
            'mcteacher - remem@gmx.de - Scales 10-10-2026.mp4',
            'MCTEACHER - 10-10-2026.mp4',
        )):
            (self.videos / filename).write_bytes(f'video {index}'.encode())
        result = self.db.sync_folder(str(self.videos), parse_filename)
        self.assertEqual(result['added'], 2)
        self.assertEqual(result['errors'], 0)
        lessons, total = self.db.get_library_lessons()
        self.assertEqual(total, 2)
        self.assertEqual({row['author'] for row in lessons}, {'McTeacher'})
        self.assertEqual({row['title'] for row in lessons},
                         {'Scales', 'Lesson by McTeacher (2026-10-10)'})
        self.assertEqual(self.db.sync_folder(str(self.videos), parse_filename)['unchanged'], 2)

    def test_author_filters_and_counts_are_unicode_case_insensitive(self):
        self.seed(2)
        with self.db._get_connection() as conn:
            conn.execute("UPDATE lessons SET author='Øyvind' WHERE id=1")
            conn.execute("UPDATE lessons SET author='øyvind' WHERE id=2")
        self.assertEqual(self.db.get_paginated_lessons(author_filter='ØYVIND')[1], 2)
        self.assertEqual(len(self.db.get_library_authors()), 1)
        self.assertEqual(self.db.get_author_breakdown()[0]['count'], 2)
        self.db.normalize_lesson_metadata()
        self.assertEqual(self.db.get_library_authors(), ['Øyvind'])

    def test_sync_and_rename_preserve_id_progress_and_tags(self):
        video = self.video('A', b'video')
        with self.db._get_connection() as conn:
            conn.execute('''INSERT INTO lessons(id,file_hash,filepath,filename,author,title,
                            lesson_date,status,completed_at)
                            VALUES (42,?,?,?,'Teacher','A','2026-10-10','Completed','2024-01-01')''',
                         ('sha256:' + hashlib.sha256(b'video').hexdigest(), str(video), video.name))
        tag = self.db.create_tag('favorite')
        self.db.add_tag_to_lesson(42, tag)
        self.db.sync_folder(str(self.videos), parse_filename)
        lesson = self.db.get_lesson_by_id(42)
        self.assertTrue(lesson['file_hash'].startswith('sha256:'))
        self.assertEqual(lesson['status'], 'Completed')
        self.assertEqual(lesson['completed_at'], '2024-01-01')
        self.assertEqual(self.db.get_lesson_tags(42)[0]['id'], tag)
        renamed = video.with_name('Teacher - Renamed 10-10-2026.mp4')
        video.rename(renamed)
        self.db.sync_folder(str(self.videos), parse_filename)
        self.assertEqual(self.db.get_lesson_by_id(42)['filepath'], str(renamed))

    def test_unchanged_sync_does_not_read_video_or_subtitle_bodies(self):
        video = self.video('A', b'video')
        video.with_suffix('.srt').write_text('1\n00:00:00,000 --> 00:00:01,000\nScales\n')
        self.db.sync_folder(str(self.videos), parse_filename)
        with patch('builtins.open', side_effect=AssertionError('Unchanged file reread')):
            result = self.db.sync_folder(str(self.videos), parse_filename)
        self.assertEqual(result['unchanged'], 1)

    def test_subtitle_changes_and_removal_refresh_search(self):
        video = self.video('A', b'video')
        srt = video.with_suffix('.srt')
        srt.write_text('1\n00:00:00,000 --> 00:00:01,000\nScales\n')
        self.db.sync_folder(str(self.videos), parse_filename)
        srt.write_text('1\n00:00:00,000 --> 00:00:01,000\nArpeggios slowly\n')
        self.db.sync_folder(str(self.videos), parse_filename)
        self.assertEqual(self.db.search_transcripts('arpeggios')[1], 1)
        srt.unlink()
        self.db.sync_folder(str(self.videos), parse_filename)
        self.assertEqual(self.db.search_transcripts('arpeggios')[1], 0)

    def test_empty_folder_archives_and_return_restores_in_progress(self):
        video = self.video('A', b'video')
        self.db.sync_folder(str(self.videos), parse_filename)
        lesson_id = self.db.get_paginated_lessons()[0][0]['id']
        self.db.update_status(lesson_id, 'In Progress')
        video.unlink()
        self.assertEqual(self.db.sync_folder(str(self.videos), parse_filename)['archived'], 1)
        self.assertEqual(self.db.get_stats()['total'], 0)
        self.video('A', b'video')
        self.db.sync_folder(str(self.videos), parse_filename)
        self.assertEqual(self.db.get_lesson_by_id(lesson_id)['status'], 'In Progress')

    def test_incomplete_scan_does_not_archive(self):
        self.video('A', b'video')
        self.db.sync_folder(str(self.videos), parse_filename)
        (self.videos / 'unparseable.mp4').write_bytes(b'other')
        result = self.db.sync_folder(str(self.videos), parse_filename)
        self.assertGreater(result['errors'], 0)
        self.assertEqual(result['archived'], 0)

    def test_repeat_practice_credits_a_lesson_only_once(self):
        self.seed(completed=True)
        original_date = self.db.get_lesson_by_id(1)['completed_at']
        self.db.update_status(1, 'In Progress')
        self.assertEqual(self.db.get_lesson_by_id(1)['completed_at'], original_date)
        self.assertEqual(self.db.get_today_completions(), 1)
        for _ in range(10):
            self.db.update_status(1, 'Completed')
            self.db.update_status(1, 'Completed')  # Duplicate callback is idempotent.
            self.assertEqual(self.db.get_today_completions(), 1)
            self.assertEqual(self.db.get_week_completions(), 1)
            self.assertEqual(self.db.get_stats()['completed'], 1)
            self.db.update_status(1, 'In Progress')
            self.assertEqual(self.db.get_stats()['completed'], 1)
            self.assertEqual(self.db.get_remaining_lessons(), 0)
        self.assertEqual(self.db.get_lesson_by_id(1)['completed_at'], original_date)
        with self.db._get_connection() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM completion_events').fetchone()[0], 1)
        self.assertEqual(len(self.db.get_lessons_completed_on_date(date.today().isoformat())), 1)
        self.assertEqual(self.db.get_backlog_trend()[-1]['completed_cumulative'], 1)
        self.assertEqual(self.db.get_backlog_trend()[-1]['backlog'], 0)
        self.db._init_db()
        self.assertEqual(self.db.get_today_completions(), 1)

    def test_practicing_a_previous_days_lesson_does_not_extend_progress(self):
        self.seed()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        with self.db._get_connection() as conn:
            conn.execute("UPDATE lessons SET status='Completed',completed_at=? WHERE id=1", (yesterday,))
        self.db.invalidate_cache()
        self.db.update_status(1, 'In Progress')
        self.db.update_status(1, 'Completed')
        self.assertEqual(self.db.get_lesson_by_id(1)['completed_at'], yesterday)
        self.assertEqual(self.db.get_today_completions(), 0)
        self.assertEqual(self.db.get_completion_dates(), [date.today() - timedelta(days=1)])
        self.assertEqual(self.db.get_best_streak(), 1)
        self.assertEqual(self.db.get_activity_data_for_year(date.today().year)[0]['count'], 1)

    def test_repeat_event_history_is_counted_once_and_preserved_on_startup(self):
        self.seed()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        today = date.today().isoformat()
        with self.db._get_connection() as conn:
            conn.executemany('INSERT INTO completion_events(lesson_id,completed_at) VALUES (1,?)',
                             [(yesterday,), (today,)])
            conn.execute("UPDATE lessons SET status='Completed',completed_at=? WHERE id=1", (yesterday,))
            conn.execute("INSERT INTO personal_records(record_type,value) VALUES ('most_day',1)")
        self.db._init_db()
        self.assertEqual(self.db.get_lesson_by_id(1)['completed_at'], yesterday)
        self.assertEqual(self.db.get_today_completions(), 0)
        self.assertEqual(self.db.get_most_lessons_in_day()['value'], 1)
        self.assertEqual(self.db.get_best_streak(), 1)
        self.assertEqual(self.db.get_personal_records()['most_day']['value'], 1)
        self.db.compute_and_update_records()
        self.assertEqual(self.db.get_personal_records()['most_day']['value'], 1)
        self.db._init_db()
        self.assertEqual(self.db.get_personal_records()['most_day']['value'], 1)
        with self.db._get_connection() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM completion_events').fetchone()[0], 2)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM completion_activity').fetchone()[0], 1)

    def test_400_day_streak_is_not_truncated(self):
        self.seed(400)
        with self.db._get_connection() as conn:
            conn.executemany("UPDATE lessons SET status='Completed',completed_at=? WHERE id=?",
                [((date.today()-timedelta(days=i)).isoformat(), i+1) for i in range(400)])
        self.db.invalidate_cache()
        self.assertEqual(self.db.get_current_streak(), 400)
        self.assertEqual(self.db.get_best_streak(), 400)
        self.assertFalse(self.db.get_streak_recovery_info()['is_at_best'])

    def test_existing_database_initialization_preserves_schema_and_data(self):
        self.seed(completed=True)
        self.db.compute_and_update_records()
        connect = self.db._get_connection
        with connect() as conn:
            original_schema = conn.execute('SELECT * FROM sqlite_master ORDER BY name').fetchall()
            original_data = {
                table: conn.execute(f'SELECT * FROM {table}').fetchall()
                for table in ('lessons', 'completion_events', 'personal_records')
            }

        def deny_existing_database_changes():
            conn = connect()

            def authorize(action, table, *args):
                if action in (sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_DROP_VIEW,
                              sqlite3.SQLITE_DROP_TRIGGER, sqlite3.SQLITE_DROP_TABLE):
                    return sqlite3.SQLITE_DENY
                if (action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE)
                        and table in original_data):
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK

            conn.set_authorizer(authorize)
            return conn

        with patch.object(self.db, '_get_connection', side_effect=deny_existing_database_changes):
            self.db._init_db()
        with connect() as conn:
            self.assertEqual(conn.execute('SELECT * FROM sqlite_master ORDER BY name').fetchall(),
                             original_schema)
            for table, rows in original_data.items():
                self.assertEqual(conn.execute(f'SELECT * FROM {table}').fetchall(), rows)
        self.assertEqual(self.db.get_today_completions(), 1)
        self.db.update_status(1, 'In Progress')
        self.db.update_status(1, 'Completed')
        self.assertEqual(self.db.get_today_completions(), 1)

    def test_all_pages_and_all_matching_ids_are_available(self):
        self.seed(1101)
        for page in (1, 6, 11, 12):
            lessons, total = self.db.get_paginated_lessons(page=page, page_size=100)
            self.assertEqual(total, 1101)
            self.assertEqual(len(lessons), 100 if page < 12 else 1)
        lessons, total = self.db.search_transcripts('scales', page=12, page_size=100)
        self.assertEqual((len(lessons), total), (1, 1101))
        self.assertEqual(len(self.db.get_matching_lesson_ids(transcript_query='scales')), 1101)
        self.assertEqual(self.db.search_transcripts('50%_')[1], 1101)
        self.assertEqual(self.db.search_transcripts('99%_')[1], 0)
        rows, total = self.db.get_library_lessons(transcript_query='scales')
        self.assertEqual((len(rows), total), (1101, 1101))
        self.assertTrue(all(len(row['context']) <= 320 for row in rows))
        self.assertEqual(len(self.db.get_paginated_lessons(page=None)[0]), 50)

    def test_bulk_tagging_is_atomic_and_uses_one_connection(self):
        self.seed(1000)
        tag = self.db.create_tag('favorite')
        ids = self.db.get_matching_lesson_ids()
        with patch.object(self.db, '_get_connection', wraps=self.db._get_connection) as connect:
            self.assertEqual(self.db.add_tag_to_lessons(ids, tag), 1000)
            self.assertEqual(connect.call_count, 1)
        self.assertEqual(self.db.add_tag_to_lessons(ids, tag), 0)
        other = self.db.create_tag('atomic')
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.add_tag_to_lessons([1, 99999], other)
        self.assertEqual(len(self.db.get_lesson_tags(1)), 1)

    def test_connections_close_on_commit_and_rollback(self):
        with self.db._get_connection() as conn:
            conn.execute("INSERT INTO tags(name) VALUES ('committed')")
        with self.assertRaises(sqlite3.ProgrammingError):
            conn.execute('SELECT 1')
        with self.assertRaises(RuntimeError):
            with self.db._get_connection() as failed:
                failed.execute("INSERT INTO tags(name) VALUES ('rollback')")
                raise RuntimeError('abort')
        with self.assertRaises(sqlite3.ProgrammingError):
            failed.execute('SELECT 1')
        self.assertEqual([tag['name'] for tag in self.db.get_all_tags()], ['committed'])

    def test_records_are_cached_and_read_only_when_unchanged(self):
        self.seed(completed=True)
        self.db.compute_and_update_records()
        with patch.object(self.db, '_get_connection', wraps=self.db._get_connection) as connect:
            self.db.compute_and_update_records()
            self.assertEqual(connect.call_count, 0)
        self.db.invalidate_cache()
        queries = []
        original = self.db._get_connection
        def trace():
            conn = original()
            conn.set_trace_callback(queries.append)
            return conn
        with patch.object(self.db, '_get_connection', side_effect=trace):
            self.db.compute_and_update_records()
        self.assertFalse(any(query.lstrip().startswith('INSERT') for query in queries))


if __name__ == '__main__':
    unittest.main()
