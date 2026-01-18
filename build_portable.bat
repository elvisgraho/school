@echo off
echo ============================================================
echo      Guitar Shed - Create Portable Distribution
echo ============================================================
echo.
echo This will create a self-contained portable folder that
echo can be copied to any Windows computer and run without
echo installing Python.
echo.
echo Press any key to continue or Ctrl+C to cancel...
pause >nul

python create_portable.py

echo.
pause
