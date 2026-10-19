"""Dependency-free regressions for record labels and the portable launcher."""
import ast
from datetime import datetime, timedelta
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]


def load_date_formatters():
    tree = ast.parse((ROOT / 'utils/ui/analytics.py').read_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {'_format_record_date', '_format_record_week'}]
    namespace = {'datetime': datetime, 'timedelta': timedelta}
    exec(compile(ast.Module(body=functions, type_ignores=[]), '<date helpers>', 'exec'), namespace)
    return namespace


def load_launcher():
    tree = ast.parse((ROOT / 'create_portable.py').read_text())
    launcher_source = next(
        node.args[0].value for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == 'write_text' and node.args
        and isinstance(node.args[0], ast.Constant)
        and 'class StreamlitApp:' in str(node.args[0].value)
    )
    namespace = {'__name__': 'launcher_test', '__file__': str(ROOT / 'launcher.py')}
    with patch.dict(sys.modules, {'webview': types.ModuleType('webview')}):
        exec(compile(launcher_source, '<generated launcher>', 'exec'), namespace)
    return namespace


class RecordDatesTest(unittest.TestCase):
    def test_date_and_month_labels(self):
        format_date = load_date_formatters()['_format_record_date']
        self.assertEqual(format_date('2026-01-26'), '26 jan 2026')
        self.assertEqual(format_date('2026-02-01'), '1 feb 2026')
        self.assertEqual(format_date('2024-02-29'), '29 feb 2024')
        self.assertEqual(format_date('2026-01', 'month'), 'jan 2026')
        self.assertIsNone(format_date(None))
        self.assertIsNone(format_date(''))

    def test_sqlite_week_boundaries(self):
        format_week = load_date_formatters()['_format_record_week']
        self.assertEqual(format_week('2026-04'), '26 jan 2026 – 1 feb 2026')
        self.assertEqual(format_week('2026-00'), '1 jan 2026 – 4 jan 2026')
        self.assertEqual(format_week('2026-52'), '28 dec 2026 – 31 dec 2026')
        self.assertEqual(format_week('2024-01'), '1 jan 2024 – 7 jan 2024')
        self.assertIsNone(format_week(None))


class PracticeTranscriptTest(unittest.TestCase):
    def render(self, transcript):
        tree = ast.parse((ROOT / 'utils/ui/practice.py').read_text())
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == 'render_practice_room')
        st = MagicMock()
        st.session_state = {'selected_lesson_id': 1}
        st.columns.side_effect = lambda widths: [MagicMock() for _ in range(
            widths if isinstance(widths, int) else len(widths))]
        st.selectbox.return_value = ''
        namespace = dict(st=st, os=os, urllib=__import__('urllib.parse'),
                         STATUS_COLORS={}, video_url=lambda lesson_id: '/video/1')
        for name in ('clear_lesson', 'update_status_callback', 'add_tag_callback',
                     'remove_tag_callback', 'exit_playlist', 'playlist_next',
                     'playlist_prev', 'complete_and_next'):
            namespace[name] = MagicMock()
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<practice room>', 'exec'),
             namespace)
        db = MagicMock()
        db.get_lesson_by_id.return_value = dict(
            id=1, title='Scales', author='Teacher', lesson_date='2026-10-10',
            filepath=str(ROOT / 'app.py'), status='Completed', transcript=transcript)
        db.get_lesson_tags.return_value = []
        db.get_all_tags.return_value = []
        namespace['render_practice_room'](db)
        return st

    def test_transcript_is_collapsed_below_tags_and_displayed_as_plain_text(self):
        st = self.render('  Practice <b>scales</b> slowly\nNext phrase.  ')
        self.assertEqual([(call.args[0], call.kwargs['expanded'])
                          for call in st.expander.call_args_list],
                         [('Manage Tags', False), ('☰ Transcript', False)])
        st.text.assert_called_once_with('Practice <b>scales</b> slowly\nNext phrase.')
        st.container.assert_called_once_with(height=350)

    def test_missing_transcripts_show_a_clear_message(self):
        for transcript in (None, '', '   '):
            with self.subTest(transcript=transcript):
                st = self.render(transcript)
                st.text.assert_not_called()
                st.caption.assert_called_with('No transcript available for this video.')


class LauncherTest(unittest.TestCase):
    def test_exports_are_enabled_before_the_native_window_opens(self):
        launcher = load_launcher()
        webview = launcher['webview']
        webview.settings = {'ALLOW_DOWNLOADS': False}

        def create_window(*args, **kwargs):
            self.assertTrue(webview.settings['ALLOW_DOWNLOADS'])

        with patch.dict(launcher, {'StreamlitApp': unittest.mock.Mock()}) as namespace:
            app = namespace['StreamlitApp'].return_value
            app.start.return_value = 'http://127.0.0.1:8501'
            with patch.object(webview, 'create_window', side_effect=create_window, create=True) as window, \
                    patch.object(webview, 'start', create=True) as start:
                launcher['main']()
            window.assert_called_once()
            start.assert_called_once_with()
            app.stop.assert_called_once_with()

    def test_server_output_cannot_fill_an_unread_pipe(self):
        launcher = load_launcher()
        real_popen = subprocess.Popen
        children = []

        def noisy_server(cmd, **kwargs):
            child = real_popen([
                sys.executable, '-c',
                "import os; os.write(1, b'x' * 2000000); os.write(2, b'y' * 2000000)",
            ], **kwargs)
            children.append(child)
            return child

        with tempfile.TemporaryDirectory() as directory:
            launcher['__file__'] = str(Path(directory) / 'launcher.py')
            launcher['find_free_port'] = lambda: 8501
            launcher['wait_for_server'] = lambda port: True
            app = launcher['StreamlitApp']()
            try:
                with patch.object(subprocess, 'Popen', side_effect=noisy_server):
                    self.assertEqual(app.start(), 'http://127.0.0.1:8501')
                self.assertEqual(children[0].wait(timeout=10), 0)
                self.assertEqual((Path(directory) / 'streamlit.log').stat().st_size, 4000000)
            finally:
                for child in children:
                    if child.poll() is None:
                        child.kill()
                    child.wait()


if __name__ == '__main__':
    unittest.main()
