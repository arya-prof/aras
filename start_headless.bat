@echo off
echo Starting Aras Agent in headless mode...
echo Look for the circular indicator in the bottom-right corner of your screen.
echo Click on it or say "What's the home status?" to see the 3D home visualization.
echo Press Ctrl+C to exit.
echo.

set PYTHONPATH=%CD%\src
python start_headless.py

pause
