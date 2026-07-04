@echo off
setlocal enabledelayedexpansion
echo === Building ZonaRiska.exe ===
python --version >nul 2>&1
if errorlevel 1 (
  echo Python not found. Install from https://www.python.org/downloads/ ^(check "Add Python to PATH"^).
  pause & exit /b
)
echo Checking Python architecture...
python -c "import struct; print(f'Python: {struct.calcsize(\"P\")*8}-bit')"

echo Removing old build...
if exist venv rmdir /s /q venv >nul 2>&1
if exist build rmdir /s /q build >nul 2>&1
if exist dist rmdir /s /q dist >nul 2>&1

echo Creating virtual environment...
python -m venv venv >nul 2>&1
call venv\Scripts\activate.bat

echo Upgrading pip/setuptools/wheel...
python -m pip install --upgrade pip setuptools wheel >nul 2>&1

echo Installing pygame-ce...
python -m pip install pygame-ce

echo Installing PyInstaller...
python -m pip install pyinstaller >nul 2>&1

echo.
echo Building executable ^(1-3 min^)...
python -m PyInstaller --onefile --windowed --name ZonaRiska --icon assets/icon.ico --collect-all pygame --hidden-import core --hidden-import entities --add-data "assets;assets" main.py

echo.
if exist dist\ZonaRiska.exe (
  echo ============================================
  echo  SUCCESS! dist\ZonaRiska.exe is ready
  echo ============================================
  timeout /t 2 >nul
  explorer dist
  call venv\Scripts\deactivate.bat
) else (
  echo BUILD FAILED
  call venv\Scripts\deactivate.bat
  pause & exit /b 1
)