Write-Host "Starting Build..."
$DevPath = "D:\FeedbackCollector"
$BuildPath = "D:\FeedbackCollector_Desktop_Build"

if (-not (Test-Path $DevPath)) {
    Write-Host "Dev path not found"
    exit 1
}

if (-not (Test-Path $BuildPath)) {
    New-Item -ItemType Directory -Path $BuildPath -Force | Out-Null
}

Write-Host "Copying files..."
Copy-Item "$DevPath\src\*" -Destination "$BuildPath\src\" -Recurse -Force

if (Test-Path "$DevPath\src\.env") {
    Copy-Item "$DevPath\src\.env" -Destination "$BuildPath\src\.env" -Force
}


Write-Host "Checking PyInstaller..."
try {
    $pyinstallerCheck = python -m PyInstaller --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing PyInstaller..."
        python -m pip install pyinstaller
    }
} catch {
    Write-Host "Error checking PyInstaller"
    exit 1
}

Write-Host "Building executable..."
Set-Location $BuildPath
try {
    python -m PyInstaller FeedbackCollector.spec --noconfirm --clean
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Build Success"
        
        # Copy .env to distribution root
        $envInInternal = "$BuildPath\dist\FeedbackCollector\_internal\.env"
        $envInRoot = "$BuildPath\dist\FeedbackCollector\.env"
        if (Test-Path $envInInternal) {
            Copy-Item $envInInternal -Destination $envInRoot -Force
            Write-Host "Copied .env to dist root"
        }
    } else {
        Write-Host "Build Failed"
        exit 1
    }
} catch {
    Write-Host "Build Error"
    exit 1
}

