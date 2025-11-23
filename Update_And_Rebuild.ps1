# Update and Rebuild FeedbackCollector Desktop Application
# This script copies updated source files and rebuilds the executable

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "FeedbackCollector Desktop Build Tool" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Define paths
$DevPath = "D:\FeedbackCollector"
$BuildPath = "D:\FeedbackCollector_Desktop_Build"

# Check if development path exists
if (-not (Test-Path $DevPath)) {
    Write-Host "ERROR: Development path not found: $DevPath" -ForegroundColor Red
    exit 1
}

# Create build directory if it doesn't exist
if (-not (Test-Path $BuildPath)) {
    Write-Host "Creating build directory: $BuildPath" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $BuildPath -Force | Out-Null
}

# Step 1: Copy updated source files
Write-Host "[1/4] Copying updated source files..." -ForegroundColor Green
try {
    # Copy src directory
    Copy-Item "$DevPath\src\*" -Destination "$BuildPath\src\" -Recurse -Force
    Write-Host "  ✓ Source files copied" -ForegroundColor Gray
    
    # Always copy .env file
    if (Test-Path "$DevPath\src\.env") {
        Copy-Item "$DevPath\src\.env" -Destination "$BuildPath\src\.env" -Force
        Write-Host "  ✓ .env file copied" -ForegroundColor Gray
    } else {
        Write-Host "  ⚠ Warning: .env file not found in source" -ForegroundColor Yellow
    }
    
    # Copy spec file
    if (Test-Path "$DevPath\FeedbackCollector.spec") {
        Copy-Item "$DevPath\FeedbackCollector.spec" -Destination "$BuildPath\" -Force
        Write-Host "  ✓ Spec file copied" -ForegroundColor Gray
    }
    
    # Copy requirements if exists
    if (Test-Path "$DevPath\src\requirements.txt") {
        Copy-Item "$DevPath\src\requirements.txt" -Destination "$BuildPath\" -Force
        Write-Host "  ✓ Requirements copied" -ForegroundColor Gray
    }
} catch {
    Write-Host "ERROR: Failed to copy files - $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Step 2: Check PyInstaller installation
Write-Host "[2/4] Checking PyInstaller installation..." -ForegroundColor Green
try {
    $pyinstallerCheck = python -m PyInstaller --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ⚠ PyInstaller not found, installing..." -ForegroundColor Yellow
        python -m pip install pyinstaller
    } else {
        Write-Host "  ✓ PyInstaller is installed" -ForegroundColor Gray
    }
} catch {
    Write-Host "ERROR: Failed to check PyInstaller - $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Step 3: Build executable
Write-Host "[3/4] Building executable with PyInstaller..." -ForegroundColor Green
Write-Host "  This may take a few minutes..." -ForegroundColor Gray

Set-Location $BuildPath

try {
    python -m PyInstaller FeedbackCollector.spec --noconfirm --clean
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Build completed successfully" -ForegroundColor Gray
    } else {
        Write-Host "ERROR: Build failed with exit code $LASTEXITCODE" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "ERROR: Build failed - $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Step 4: Verify output
Write-Host "[4/4] Verifying build output..." -ForegroundColor Green

$exePath = "$BuildPath\dist\FeedbackCollector\FeedbackCollector.exe"
if (Test-Path $exePath) {
    $exeSize = (Get-Item $exePath).Length / 1MB
    Write-Host "  ✓ Executable created: $exePath" -ForegroundColor Gray
    Write-Host "  ✓ Size: $([math]::Round($exeSize, 2)) MB" -ForegroundColor Gray
    
    # Check if .env was included
    $envInDist = "$BuildPath\dist\FeedbackCollector\_internal\.env"
    if (Test-Path $envInDist) {
        Write-Host "  ✓ .env file included in distribution" -ForegroundColor Gray
    } else {
        Write-Host "  ⚠ Warning: .env file not found in _internal directory" -ForegroundColor Yellow
    }
} else {
    Write-Host "ERROR: Executable not found at expected location" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Build Complete!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Executable location:" -ForegroundColor White
Write-Host "  $exePath" -ForegroundColor Cyan
Write-Host ""
Write-Host "To run the application:" -ForegroundColor White
Write-Host "  cd $BuildPath\dist\FeedbackCollector" -ForegroundColor Gray
Write-Host "  .\FeedbackCollector.exe" -ForegroundColor Gray
Write-Host ""
Write-Host "Distribution folder:" -ForegroundColor White
Write-Host "  $BuildPath\dist\FeedbackCollector\" -ForegroundColor Cyan
Write-Host ""
