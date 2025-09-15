# PowerShell script to start the filament monitor
# This opens in a new window with proper display

$pythonPath = "C:\OctoPrint\WPy64-31050\Scripts\python.bat"
$scriptPath = "monitor.py"

# Set console properties for better display
$host.UI.RawUI.WindowTitle = "MCP2221A Filament Monitor"
$host.UI.RawUI.BufferSize = New-Object System.Management.Automation.Host.Size(65, 30)
$host.UI.RawUI.WindowSize = New-Object System.Management.Automation.Host.Size(65, 30)

Clear-Host

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "         MCP2221A DUAL FILAMENT SENSOR MONITOR          " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Starting monitor..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Features:" -ForegroundColor Green
Write-Host "  * Persistent usage tracking" -ForegroundColor White
Write-Host "  * Session & total metrics" -ForegroundColor White
Write-Host "  * Non-scrolling display updates" -ForegroundColor White
Write-Host "  * HTTP API on port 5002" -ForegroundColor White
Write-Host "  * Web interface: http://localhost:5002" -ForegroundColor White
Write-Host "  * JSON API: http://localhost:5002/status" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

Start-Sleep -Seconds 2

# Run the monitor
& $pythonPath $scriptPath

Write-Host ""
Write-Host "Monitor stopped" -ForegroundColor Red
Write-Host "Press any key to exit..."
$null = $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")