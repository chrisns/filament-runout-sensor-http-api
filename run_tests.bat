@echo off
echo ========================================
echo Running Monitor Test Suite
echo ========================================
echo.

echo [1/4] Testing Hardware Connection...
echo ----------------------------------------
C:\OctoPrint\WPy64-31050\Scripts\python.bat test_sensors.py
echo.

echo [2/4] Testing Monitor Startup...
echo ----------------------------------------
C:\OctoPrint\WPy64-31050\Scripts\python.bat test_monitor_startup.py
echo.

echo [3/4] Testing Persistent Storage...
echo ----------------------------------------
C:\OctoPrint\WPy64-31050\Scripts\python.bat test_persistence.py
echo.

echo [4/4] Testing API (requires monitor.py running)...
echo ----------------------------------------
C:\OctoPrint\WPy64-31050\Scripts\python.bat test_api.py
echo.

echo ========================================
echo All tests completed!
echo ========================================
pause