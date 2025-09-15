@echo off
echo ====================================
echo MCP2221A Filament Sensor Test
echo ====================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.11 or later from python.org
    pause
    exit /b 1
)

REM Check if EasyMCP2221 is installed
python -c "import EasyMCP2221" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing EasyMCP2221 library...
    pip install EasyMCP2221
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install EasyMCP2221
        echo Try running: pip install EasyMCP2221 manually
        pause
        exit /b 1
    )
)

echo.
echo Starting hardware test...
echo ========================
echo.

REM Run the test script
python test_hardware.py

echo.
echo ====================================
echo Test completed
echo ====================================
pause