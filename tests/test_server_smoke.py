"""Verify that the installed Streamlit server starts and serves the app."""
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]


class ServerSmokeTest(unittest.TestCase):
    def test_health_and_app_page(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            shutil.copy2(ROOT / 'app.py', target / 'app.py')
            shutil.copy2(ROOT / 'ui_app.py', target / 'ui_app.py')
            video_data = bytes(range(256)) * 1024
            (target / 'sample.mp4').write_bytes(video_data)
            # Seed and sign a video URL inside the actual server process.
            with (target / 'app.py').open('a') as fixture:
                fixture.write('''
from utils.db import DatabaseManager
from utils.video_server import video_url
db = DatabaseManager()
with db._get_connection() as conn:
    conn.execute("INSERT INTO lessons(id,file_hash,filepath,filename,author,title,lesson_date) VALUES (1,'test','sample.mp4','sample.mp4','Teacher','Test','2026-10-10')")
Path('video_url.txt').write_text(video_url(1))
''')
            shutil.copytree(ROOT / 'utils', target / 'utils',
                            ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(ROOT / '.streamlit', target / '.streamlit')
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            with (target / 'server.log').open('w+') as log:
                child = subprocess.Popen([
                    sys.executable, '-m', 'streamlit', 'run', 'app.py',
                    '--server.headless=true', '--server.address=127.0.0.1',
                    f'--server.port={port}', '--browser.gatherUsageStats=false',
                ], cwd=target, stdout=log, stderr=log)
                try:
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    deadline = time.monotonic() + 30
                    while time.monotonic() < deadline:
                        if child.poll() is not None:
                            log.seek(0)
                            self.fail(log.read())
                        try:
                            with opener.open(f'http://127.0.0.1:{port}/_stcore/health',
                                             timeout=1) as response:
                                self.assertEqual(response.status, 200)
                                self.assertEqual(response.read(), b'ok')
                            break
                        except OSError:
                            time.sleep(0.1)
                    else:
                        log.seek(0)
                        self.fail(f'Server startup timed out:\n{log.read()}')
                    with opener.open(f'http://127.0.0.1:{port}/', timeout=2) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIn(b'<html', response.read())
                    url = f'http://127.0.0.1:{port}' + (target / 'video_url.txt').read_text()
                    with opener.open(urllib.request.Request(url, headers={'Range': 'bytes=100-199'})) as response:
                        self.assertEqual(response.status, 206)
                        self.assertEqual(response.headers['Content-Type'], 'video/mp4')
                        self.assertEqual(response.headers['Content-Range'], f'bytes 100-199/{len(video_data)}')
                        self.assertEqual(response.read(), video_data[100:200])
                    with opener.open(urllib.request.Request(url, headers={'Range': 'bytes=-16'})) as response:
                        self.assertEqual(response.read(), video_data[-16:])
                    with opener.open(urllib.request.Request(url, method='HEAD')) as response:
                        self.assertEqual(int(response.headers['Content-Length']), len(video_data))
                        self.assertEqual(response.read(), b'')
                    with self.assertRaises(urllib.error.HTTPError) as invalid:
                        opener.open(urllib.request.Request(url, headers={'Range': 'bytes=9999999-'}))
                    self.assertEqual(invalid.exception.code, 416)
                    with self.assertRaises(urllib.error.HTTPError) as unsigned:
                        opener.open(url.rsplit('/', 1)[0] + '/invalid-token')
                    self.assertEqual(unsigned.exception.code, 404)
                finally:
                    child.terminate()
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=10)


if __name__ == '__main__':
    unittest.main()
