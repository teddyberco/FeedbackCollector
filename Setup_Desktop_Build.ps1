# Initial Setup for FeedbackCollector Desktop Build
# Run this once to set up the desktop build environment

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "FeedbackCollector Desktop Setup" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Define paths
$BuildPath = "D:\FeedbackCollector_Desktop_Build"
$DevPath = "D:\FeedbackCollector"

# Step 1: Create build directory
Write-Host "[1/6] Creating build directory..." -ForegroundColor Green
if (-not (Test-Path $BuildPath)) {
    New-Item -ItemType Directory -Path $BuildPath -Force | Out-Null
    New-Item -ItemType Directory -Path "$BuildPath\src" -Force | Out-Null
    Write-Host "  ✓ Build directory created" -ForegroundColor Gray
} else {
    Write-Host "  ✓ Build directory already exists" -ForegroundColor Gray
}

# Step 2: Copy source files
Write-Host "[2/6] Copying source files..." -ForegroundColor Green
Copy-Item "$DevPath\src\*" -Destination "$BuildPath\src\" -Recurse -Force
Write-Host "  ✓ Source files copied" -ForegroundColor Gray

# Step 3: Copy .env file
Write-Host "[3/6] Copying .env file..." -ForegroundColor Green
if (Test-Path "$DevPath\src\.env") {
    Copy-Item "$DevPath\src\.env" -Destination "$BuildPath\src\.env" -Force
    Write-Host "  ✓ .env file copied" -ForegroundColor Gray
} else {
    Write-Host "  ⚠ Warning: .env file not found" -ForegroundColor Yellow
}

# Step 4: Copy spec file
Write-Host "[4/6] Copying build specification..." -ForegroundColor Green
Copy-Item "$DevPath\FeedbackCollector.spec" -Destination "$BuildPath\" -Force
Copy-Item "$DevPath\Update_And_Rebuild.ps1" -Destination "$BuildPath\" -Force
Copy-Item "$DevPath\Update_And_Rebuild.bat" -Destination "$BuildPath\" -Force
Write-Host "  ✓ Build files copied" -ForegroundColor Gray

# Step 5: Check Python and PyInstaller
Write-Host "[5/6] Checking Python environment..." -ForegroundColor Green
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  ✓ Python: $pythonVersion" -ForegroundColor Gray
    
    $pyinstallerCheck = python -m PyInstaller --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ⚠ Installing PyInstaller..." -ForegroundColor Yellow
        python -m pip install pyinstaller
        Write-Host "  ✓ PyInstaller installed" -ForegroundColor Gray
    } else {
        Write-Host "  ✓ PyInstaller: $pyinstallerCheck" -ForegroundColor Gray
    }
} catch {
    Write-Host "ERROR: Python environment check failed - $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Step 6: Install dependencies
Write-Host "[6/6] Installing dependencies..." -ForegroundColor Green
if (Test-Path "$BuildPath\src\requirements.txt") {
    Set-Location $BuildPath
    python -m pip install -r src\requirements.txt
    Write-Host "  ✓ Dependencies installed" -ForegroundColor Gray
} else {
    Write-Host "  ⚠ requirements.txt not found, skipping" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Build directory created at:" -ForegroundColor White
Write-Host "  $BuildPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Verify your .env file has correct credentials" -ForegroundColor Gray
Write-Host "  2. Run Update_And_Rebuild.ps1 to build the executable" -ForegroundColor Gray
Write-Host ""
Write-Host "To build now, run:" -ForegroundColor White
Write-Host "  cd $BuildPath" -ForegroundColor Gray
Write-Host "  .\Update_And_Rebuild.ps1" -ForegroundColor Gray
Write-Host ""
