@echo off
echo === ZONA RISKA ===
python --version >nul 2>&1
if errorlevel 1 (
  echo Python not found. Install from https://www.python.org/downloads/
  echo IMPORTANT: check "Add Python to PATH" during install.
  pause & exit /b
)
echo Installing pygame...
python -m pip install --quiet pygame
echo Starting game...
python main.py
pause
