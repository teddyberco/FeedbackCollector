# FeedbackCollector Desktop Build
# Builds the executable directly from the project root.
# Output: dist\FeedbackCollector\  (FeedbackCollector.exe + .env)

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host " FeedbackCollector Desktop Build" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check Python and PyInstaller
Write-Host "[1/3] Checking environment..." -ForegroundColor Green
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  Python: $pythonVersion" -ForegroundColor Gray

    $pyinstallerCheck = python -m PyInstaller --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Installing PyInstaller..." -ForegroundColor Yellow
        python -m pip install pyinstaller
    } else {
        Write-Host "  PyInstaller: $pyinstallerCheck" -ForegroundColor Gray
    }
} catch {
    Write-Host "ERROR: Python not found" -ForegroundColor Red
    exit 1
}

# Step 2: Build
Write-Host "[2/3] Building executable..." -ForegroundColor Green
python -m PyInstaller FeedbackCollector.spec --noconfirm --clean --distpath "$ProjectRoot\dist" --workpath "$ProjectRoot\build"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "  Build succeeded" -ForegroundColor Gray

# Step 3: Copy .env next to the exe (the ONLY place the app looks for it)
Write-Host "[3/3] Copying .env..." -ForegroundColor Green
$envSource = Join-Path $ProjectRoot "src\.env"
$envDest = Join-Path $ProjectRoot "dist\FeedbackCollector\.env"
if (Test-Path $envSource) {
    Copy-Item $envSource -Destination $envDest -Force
    Write-Host "  .env copied next to FeedbackCollector.exe" -ForegroundColor Gray
} else {
    Write-Host "  WARNING: No src\.env found. Place your .env next to FeedbackCollector.exe before running." -ForegroundColor Yellow
}

# Clean up build intermediates
Write-Host ""
Write-Host "Cleaning up build folder..." -ForegroundColor Gray
Remove-Item "$ProjectRoot\build" -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host " Build Complete!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Distribution folder:" -ForegroundColor White
Write-Host "  $ProjectRoot\dist\FeedbackCollector\" -ForegroundColor Cyan
Write-Host ""
Write-Host "To run: dist\FeedbackCollector\FeedbackCollector.exe" -ForegroundColor White
Write-Host ""
