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
import os
import shutil
import zipfile
import urllib.request
from pathlib import Path


# Python embeddable package URL (Windows x64)
PYTHON_EMBED_URL = "https://www.python.org/ftp/python/3.11.7/python-3.11.7-embed-amd64.zip"
PYTHON_VERSION = "3.11.7"


def download_file(url, destination):
    """Download a file with progress."""
    print(f"Downloading {url}...")
    urllib.request.urlretrieve(url, destination)
    print(f"Downloaded to {destination}")


def create_portable_distribution():
    """Create the portable distribution."""
    project_root = Path(__file__).parent
    dist_folder = project_root / 'dist' / 'GuitarShed_Portable'

    # Clean and create dist folder
    if dist_folder.exists():
        shutil.rmtree(dist_folder)
    dist_folder.mkdir(parents=True)

    python_folder = dist_folder / 'python'
    app_folder = dist_folder / 'app'

    print("\n" + "=" * 60)
    print("Step 1: Downloading Python Embeddable Package")
    print("=" * 60)

    # Download Python embeddable
    python_zip = dist_folder / 'python_embed.zip'
    download_file(PYTHON_EMBED_URL, python_zip)

    # Extract Python
    print(f"\nExtracting Python to {python_folder}...")
    with zipfile.ZipFile(python_zip, 'r') as zip_ref:
        zip_ref.extractall(python_folder)
    python_zip.unlink()

    # Enable pip by modifying python311._pth
    pth_file = python_folder / 'python311._pth'
    if pth_file.exists():
        content = pth_file.read_text()
        # Uncomment import site
        content = content.replace('#import site', 'import site')
        # Add Lib\site-packages
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
    subprocess.run([str(python_exe), str(get_pip)], cwd=str(python_folder))
    get_pip.unlink()

    print("\n" + "=" * 60)
    print("Step 3: Installing dependencies")
    print("=" * 60)

    # Install required packages
    packages = [
        'streamlit',
        'pandas',
        'altair',
        'st-aggrid',
        'watchdog',  # Required by streamlit
        'pyarrow',   # For better pandas performance
    ]

    for package in packages:
        print(f"\nInstalling {package}...")
        subprocess.run([
            str(python_exe), '-m', 'pip', 'install', package, '--quiet'
        ])

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

    # Create main launcher batch file
    launcher_bat = dist_folder / 'GuitarShed.bat'
    launcher_bat.write_text('''@echo off
setlocal

REM Get the directory where this batch file is located
set "ROOT_DIR=%~dp0"
set "PYTHON_DIR=%ROOT_DIR%python"
set "APP_DIR=%ROOT_DIR%app"

REM Set Python path
set "PATH=%PYTHON_DIR%;%PYTHON_DIR%\\Scripts;%PATH%"

REM Change to app directory (so database is found)
cd /d "%APP_DIR%"

REM Find a free port
set PORT=8501

REM Launch browser after delay
start "" cmd /c "timeout /t 3 >nul && start http://localhost:%PORT%"

REM Run Streamlit
echo ============================================================
echo          Video School - Starting Application
echo ============================================================
echo.
echo The application will open in your browser shortly...
echo If it doesn't, go to: http://localhost:%PORT%
echo.
echo Press Ctrl+C to stop the server.
echo ============================================================
echo.

"%PYTHON_DIR%\\python.exe" -m streamlit run app.py --server.port %PORT% --server.headless true --browser.gatherUsageStats false

pause
''')
    print(f"Created {launcher_bat.name}")

    # Create a VBS launcher for no-console experience
    launcher_vbs = dist_folder / 'GuitarShed.vbs'
    launcher_vbs.write_text('''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.Run "GuitarShed.bat", 0, False
''')
    print(f"Created {launcher_vbs.name}")

    # Create desktop shortcut creator
    create_shortcut = dist_folder / 'Create Desktop Shortcut.bat'
    create_shortcut.write_text('''@echo off
set "SCRIPT_DIR=%~dp0"
set "SHORTCUT=%USERPROFILE%\\Desktop\\Video School.lnk"

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%SCRIPT_DIR%GuitarShed.vbs'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'Video School - Lesson Progress Tracker'; $s.Save()"

echo.
echo Desktop shortcut created!
echo.
pause
''')
    print(f"Created {create_shortcut.name}")

    # Create README
    readme = dist_folder / 'README.txt'
    readme.write_text('''# Video School - Portable Application

## Quick Start

1. Double-click "GuitarShed.bat" to start the application
   (Or use "GuitarShed.vbs" for a no-console experience)

2. Your browser will automatically open to the application

3. If the browser doesn't open, go to: http://localhost:8501

## Creating a Desktop Shortcut

Run "Create Desktop Shortcut.bat" to add a shortcut to your desktop.

## Files and Folders

- GuitarShed.bat     - Main launcher (shows console)
- GuitarShed.vbs     - Silent launcher (no console window)
- python/            - Embedded Python runtime
- app/               - Application files
  - app.py           - Main application
  - utils/           - Application modules
  - progress.db      - Your progress database (IMPORTANT!)
  - .streamlit/      - Configuration

## Backing Up Your Data

Your progress is saved in: app/progress.db
Copy this file to back up your data.

## Troubleshooting

1. Application won't start?
   - Make sure no other app is using port 8501
   - Try running GuitarShed.bat as Administrator
   - Check Windows Defender/antivirus settings

2. Browser doesn't open?
   - Manually navigate to http://localhost:8501

3. Need to change the port?
   - Edit GuitarShed.bat and change PORT=8501 to another number

## System Requirements

- Windows 10 or later (64-bit)
- No Python installation required
- Internet browser (Chrome, Firefox, Edge)

''')
    print(f"Created {readme.name}")

    # Calculate folder size
    total_size = sum(f.stat().st_size for f in dist_folder.rglob('*') if f.is_file())
    size_mb = total_size / (1024 * 1024)

    print("\n" + "=" * 60)
    print("                    BUILD COMPLETE!")
    print("=" * 60)
    print(f"\n  Output folder: {dist_folder}")
    print(f"  Total size: {size_mb:.1f} MB")
    print(f"\n  To run: Double-click 'GuitarShed.bat' or 'GuitarShed.vbs'")
    print("\n" + "=" * 60)


def main():
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║     Video School - Portable Distribution Builder           ║
    ╠═══════════════════════════════════════════════════════════╣
    ║  This will create a self-contained portable folder with:  ║
    ║  - Embedded Python runtime                                ║
    ║  - All required dependencies                              ║
    ║  - Your application and database                          ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    os.chdir(Path(__file__).parent)
    create_portable_distribution()


if __name__ == '__main__':
    main()
