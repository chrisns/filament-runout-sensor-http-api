@echo off
echo ============================================================
echo         MCP2221A DUAL FILAMENT SENSOR MONITOR
echo ============================================================
echo.
echo Features:
echo   * Persistent filament usage tracking
echo   * Session and total metrics
echo   * Non-scrolling display updates
echo   * HTTP API on port 5002
echo   * Web interface: dashboard.html
echo.
echo Starting monitor...
echo.

C:\OctoPrint\WPy64-31050\Scripts\python.bat monitor.py

echo.
echo Monitor stopped
pause