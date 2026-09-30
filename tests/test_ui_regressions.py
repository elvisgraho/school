"""Dependency-free regressions for record labels and the portable launcher."""
import ast
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

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
