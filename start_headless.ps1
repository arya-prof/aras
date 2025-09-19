# PowerShell script to start Aras Agent in headless mode
Write-Host "Starting Aras Agent in headless mode..." -ForegroundColor Green
Write-Host "Look for the circular indicator in the bottom-right corner of your screen." -ForegroundColor Yellow
Write-Host "Click on it or say 'What's the home status?' to see the 3D home visualization." -ForegroundColor Yellow
Write-Host "Press Ctrl+C to exit." -ForegroundColor Red
Write-Host ""

# Set Python path
$env:PYTHONPATH = "$PWD\src"

# Run the headless agent
try {
    python start_headless.py
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit"
}
