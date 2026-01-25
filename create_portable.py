"""
Create a portable distribution of Video School.

This creates a self-contained folder with:
- Embedded Python
- All dependencies
- The application files
- A launcher batch file

This approach is more reliable than PyInstaller for Streamlit apps.
"""

import subprocess
import sys
import shutil
import zipfile
import urllib.request
import urllib.error
import time
from pathlib import Path


# Python embeddable package configuration
PYTHON_VERSION = "3.11.9"
PYTHON_EMBED_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"


def download_file(url, destination, retries=3):
    """Download a file with progress and retry logic."""
    print(f"Downloading {Path(url).name}...")

    for attempt in range(retries):
        try:
            # Track progress
            def progress_hook(block_num, block_size, total_size):
                if total_size > 0:
                    downloaded = block_num * block_size
                    percent = min(100, downloaded * 100 / total_size)
                    mb_downloaded = downloaded / (1024 * 1024)
                    mb_total = total_size / (1024 * 1024)
                    print(f"\r  Progress: {percent:5.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)", end="", flush=True)

            urllib.request.urlretrieve(url, destination, progress_hook)
            print()  # New line after progress
            return True

        except urllib.error.URLError as e:
            print(f"\n  Attempt {attempt + 1}/{retries} failed: {e}")
            if attempt < retries - 1:
                wait_time = (attempt + 1) * 2
                print(f"  Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise RuntimeError(f"Failed to download {url} after {retries} attempts") from e

    return False


def run_command(cmd, description, cwd=None):
    """Run a command with error handling."""
    print(f"  {description}...")
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"\n  ERROR: {description} failed!")
        print(f"  Command: {' '.join(str(c) for c in cmd)}")
        if result.stderr:
            print(f"  Error output:\n{result.stderr[:500]}")
        raise RuntimeError(f"{description} failed with exit code {result.returncode}")
    return result


def create_portable_distribution():
    """Create the portable distribution."""
    project_root = Path(__file__).parent
    dist_folder = project_root / 'dist' / 'VideoSchool_Portable'

    # Clean and create dist folder
    if dist_folder.exists():
        print(f"Removing existing build folder...")
        shutil.rmtree(dist_folder)
    dist_folder.mkdir(parents=True)

    python_folder = dist_folder / 'python'
    app_folder = dist_folder / 'app'

    print("\n" + "=" * 60)
    print(f"Step 1: Downloading Python {PYTHON_VERSION} Embeddable Package")
    print("=" * 60)

    # Download Python embeddable
    python_zip = dist_folder / 'python_embed.zip'
    download_file(PYTHON_EMBED_URL, python_zip)

    # Extract Python
    print(f"Extracting Python to {python_folder.name}/...")
    with zipfile.ZipFile(python_zip, 'r') as zip_ref:
        zip_ref.extractall(python_folder)
    python_zip.unlink()

    # Enable pip by modifying python*._pth (find it dynamically)
    pth_files = list(python_folder.glob('python*._pth'))
    if not pth_files:
        raise RuntimeError("Could not find python*._pth file in embedded Python")

    pth_file = pth_files[0]
    print(f"Configuring {pth_file.name} for pip support...")
    content = pth_file.read_text()
    content = content.replace('#import site', 'import site')
    content += '\nLib\\site-packages\n'
    pth_file.write_text(content)

    print("\n" + "=" * 60)
    print("Step 2: Installing pip")
    print("=" * 60)

    # Download get-pip.py
    get_pip = dist_folder / 'get-pip.py'
    download_file('https://bootstrap.pypa.io/get-pip.py', get_pip)

    # Install pip
    python_exe = python_folder / 'python.exe'
    run_command(
        [str(python_exe), str(get_pip), '--quiet'],
        "Installing pip",
        cwd=str(python_folder)
    )
    get_pip.unlink()

    print("\n" + "=" * 60)
    print("Step 3: Installing dependencies")
    print("=" * 60)

    # Use requirements.txt file
    requirements_file = project_root / 'requirements.txt'
    if not requirements_file.exists():
        raise RuntimeError(f"requirements.txt not found at {requirements_file}")

    # Count packages for display
    with open(requirements_file) as f:
        package_count = sum(1 for line in f if line.strip() and not line.startswith('#'))

    print(f"Installing {package_count} packages from requirements.txt...")
    run_command(
        [str(python_exe), '-m', 'pip', 'install', '--quiet', '--disable-pip-version-check', '-r', str(requirements_file)],
        "Installing all dependencies"
    )

    print("\n" + "=" * 60)
    print("Step 4: Copying application files")
    print("=" * 60)

    # Create app folder
    app_folder.mkdir(exist_ok=True)

    # Copy Python files
    files_to_copy = ['app.py']
    for f in files_to_copy:
        src = project_root / f
        if src.exists():
            shutil.copy2(src, app_folder / f)
            print(f"Copied {f}")

    # Create the native launcher Python script
    launcher_py = app_folder / 'launcher.py'
    launcher_py.write_text('''"""
Native window launcher for Video School.
Uses pywebview to display the Streamlit app in a native window.
"""
import subprocess
import sys
import time
import socket
import threading
import webview
import os
import signal

# Configuration
APP_TITLE = "Video School"
DEFAULT_PORT = 8501
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800


def find_free_port(start_port=DEFAULT_PORT):
    """Find a free port starting from start_port."""
    for port in range(start_port, start_port + 100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    raise RuntimeError("Could not find a free port")


def wait_for_server(port, timeout=30):
    """Wait for the Streamlit server to be ready."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                s.connect(("127.0.0.1", port))
                return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            time.sleep(0.2)
    return False


class StreamlitApp:
    def __init__(self):
        self.process = None
        self.port = None

    def start(self):
        """Start the Streamlit server."""
        self.port = find_free_port()

        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        app_path = os.path.join(script_dir, "app.py")

        # Start Streamlit as a subprocess
        cmd = [
            sys.executable, "-m", "streamlit", "run", app_path,
            "--server.port", str(self.port),
            "--server.headless", "true",
            "--server.address", "127.0.0.1",
            "--browser.gatherUsageStats", "false",
            "--global.developmentMode", "false",
        ]

        # Use CREATE_NO_WINDOW on Windows to hide console
        startupinfo = None
        creationflags = 0
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = subprocess.CREATE_NO_WINDOW

        self.process = subprocess.Popen(
            cmd,
            cwd=script_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )

        # Wait for server to be ready
        if not wait_for_server(self.port):
            self.stop()
            raise RuntimeError("Streamlit server failed to start")

        return f"http://127.0.0.1:{self.port}"

    def stop(self):
        """Stop the Streamlit server."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None


def main():
    app = StreamlitApp()

    try:
        url = app.start()

        # Create native window
        window = webview.create_window(
            APP_TITLE,
            url,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            resizable=True,
            min_size=(800, 600),
        )

        # Start the webview (blocks until window is closed)
        webview.start()

    finally:
        app.stop()


if __name__ == "__main__":
    main()
''')
    print("Created launcher.py (native window launcher)")

    # Copy utils folder
    utils_src = project_root / 'utils'
    utils_dst = app_folder / 'utils'
    if utils_src.exists():
        shutil.copytree(utils_src, utils_dst)
        print("Copied utils/")

    # Copy database
    db_file = project_root / 'progress.db'
    if db_file.exists():
        shutil.copy2(db_file, app_folder / 'progress.db')
        print("Copied progress.db")

    # Copy .streamlit config
    streamlit_config = project_root / '.streamlit'
    if streamlit_config.exists():
        shutil.copytree(streamlit_config, app_folder / '.streamlit')
        print("Copied .streamlit/")

    print("\n" + "=" * 60)
    print("Step 5: Creating launcher scripts")
    print("=" * 60)

    # Create main launcher batch file (uses pythonw.exe for no console)
    launcher_bat = dist_folder / 'VideoSchool.bat'
    launcher_bat.write_text('''@echo off
setlocal

REM Get the directory where this batch file is located
set "ROOT_DIR=%~dp0"
set "PYTHON_DIR=%ROOT_DIR%python"
set "APP_DIR=%ROOT_DIR%app"

REM Verify Python exists
if not exist "%PYTHON_DIR%\\pythonw.exe" (
    echo ERROR: Python not found at %PYTHON_DIR%\\pythonw.exe
    echo Please ensure the portable distribution is complete.
    pause
    exit /b 1
)

REM Change to app directory and run with pythonw (no console)
cd /d "%APP_DIR%"
start "" "%PYTHON_DIR%\\pythonw.exe" launcher.py
''')
    print(f"Created {launcher_bat.name}")

    # Create debug launcher (shows console for troubleshooting)
    debug_bat = dist_folder / 'VideoSchool_Debug.bat'
    debug_bat.write_text('''@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "PYTHON_DIR=%ROOT_DIR%python"
set "APP_DIR=%ROOT_DIR%app"

if not exist "%PYTHON_DIR%\\python.exe" (
    echo ERROR: Python not found
    pause
    exit /b 1
)

cd /d "%APP_DIR%"

echo ============================================================
echo          Video School - Debug Mode
echo ============================================================
echo.
echo Starting application with console output...
echo.

"%PYTHON_DIR%\\python.exe" launcher.py

echo.
echo Application exited.
pause
''')
    print(f"Created {debug_bat.name}")

    # Create desktop shortcut creator
    create_shortcut = dist_folder / 'Create Desktop Shortcut.bat'
    create_shortcut.write_text('''@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "SHORTCUT=%USERPROFILE%\\Desktop\\Video School.lnk"

echo Creating desktop shortcut...

powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%SCRIPT_DIR%VideoSchool.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.WindowStyle = 7; $s.Description = 'Video School'; $s.Save()"

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Failed to create shortcut.
    echo Try running this script as Administrator.
) else (
    echo.
    echo Desktop shortcut created!
)

echo.
pause
''')
    print(f"Created {create_shortcut.name}")

    # Create README
    readme = dist_folder / 'README.txt'
    readme.write_text(f'''Video School - Portable Application
====================================

Quick Start
-----------
1. Double-click "VideoSchool.bat" to start the application
   (This opens a native desktop window - no browser needed!)

2. The application window will appear after a few seconds

3. To close: Simply close the window


Troubleshooting
---------------
If the app doesn't start, use "VideoSchool_Debug.bat" to see error messages.


Creating a Desktop Shortcut
---------------------------
Run "Create Desktop Shortcut.bat" to add a shortcut to your desktop.


Files and Folders
-----------------
VideoSchool.bat          Main launcher (no console window)
VideoSchool_Debug.bat    Debug launcher (shows console for troubleshooting)
python/                  Embedded Python {PYTHON_VERSION} runtime
app/                     Application files
  app.py                 Main application
  launcher.py            Native window launcher
  utils/                 Application modules
  progress.db            Your progress database (IMPORTANT - back this up!)
  .streamlit/            Configuration


Backing Up Your Data
--------------------
Your progress is saved in: app/progress.db
Copy this file to back up your data.

To restore: Replace app/progress.db with your backup file.


Troubleshooting
---------------
Application won't start?
  - Run VideoSchool_Debug.bat to see error messages
  - Check Windows Defender/antivirus - may need to allow pythonw.exe
  - Try running as Administrator

Window appears blank or doesn't load?
  - Wait a few more seconds - first launch can be slow
  - Run VideoSchool_Debug.bat to see if there are any errors

Application seems frozen?
  - The window uses Edge WebView2 internally
  - If Edge is not installed, install Microsoft Edge or Edge WebView2 Runtime

To stop the application:
  - Close the window, or
  - Open Task Manager and end "pythonw.exe"


System Requirements
-------------------
- Windows 10 or later (64-bit)
- Microsoft Edge WebView2 Runtime (usually pre-installed on Windows 10/11)
- No Python installation required
- ~250MB disk space

''')
    print(f"Created {readme.name}")

    # Calculate folder size
    total_size = sum(f.stat().st_size for f in dist_folder.rglob('*') if f.is_file())
    size_mb = total_size / (1024 * 1024)

    print("\n" + "=" * 60)
    print("                    BUILD COMPLETE!")
    print("=" * 60)
    print(f"\n  Output folder: {dist_folder}")
    print(f"  Total size:    {size_mb:.1f} MB")
    print(f"  Python:        {PYTHON_VERSION}")
    print(f"\n  To run: Double-click 'VideoSchool.bat'")
    print(f"          Use 'VideoSchool_Debug.bat' for troubleshooting")
    print("\n" + "=" * 60)

    return dist_folder


def main():
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║       Video School - Portable Distribution Builder        ║
    ╠═══════════════════════════════════════════════════════════╣
    ║  This will create a self-contained portable folder with:  ║
    ║  - Embedded Python runtime                                ║
    ║  - All required dependencies                              ║
    ║  - Your application and database                          ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    try:
        create_portable_distribution()
        return 0
    except KeyboardInterrupt:
        print("\n\nBuild cancelled by user.")
        return 1
    except Exception as e:
        print(f"\n\nBUILD FAILED: {e}")
        print("\nPlease check your internet connection and try again.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
