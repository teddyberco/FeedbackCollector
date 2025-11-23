# FeedbackCollector Desktop Build Guide

This directory contains scripts to build a standalone Windows executable of the FeedbackCollector application.

## Quick Start

### First Time Setup
```powershell
.\Setup_Desktop_Build.ps1
```

This will:
- Create build directory at `D:\FeedbackCollector_Desktop_Build`
- Copy all source files including .env
- Install PyInstaller and dependencies
- Prepare the environment for building

### Building the Executable

After making changes to the source code, rebuild:

```powershell
.\Update_And_Rebuild.ps1
```

Or double-click `Update_And_Rebuild.bat`

This will:
1. ✅ Copy updated source files from `D:\FeedbackCollector\src`
2. ✅ **Always copy the .env file** (credentials included)
3. ✅ Rebuild the Windows executable with PyInstaller
4. ✅ Create distributable in `D:\FeedbackCollector_Desktop_Build\dist\FeedbackCollector\`

## Build Output

The executable and all dependencies will be in:
```
D:\FeedbackCollector_Desktop_Build\dist\FeedbackCollector\
├── FeedbackCollector.exe          # Main executable
├── _internal\                      # Dependencies and resources
│   ├── .env                        # Environment configuration
│   ├── templates\                  # HTML templates
│   ├── static\                     # CSS, JS, images
│   ├── *.json                      # Configuration files
│   └── [Python libraries]
```

## Running the Desktop App

### From Build Directory
```powershell
cd D:\FeedbackCollector_Desktop_Build\dist\FeedbackCollector
.\FeedbackCollector.exe
```

### Distributing
To share the application:
1. Copy the entire `FeedbackCollector` folder from `dist\`
2. Recipient runs `FeedbackCollector.exe`
3. **Important**: The .env file with credentials is included

## File Structure

```
D:\FeedbackCollector\                    # Development
├── src\                                  # Source code
│   ├── .env                             # ← Always copied to build
│   ├── app.py
│   ├── run_web.py
│   └── ...
├── FeedbackCollector.spec               # PyInstaller configuration
├── Setup_Desktop_Build.ps1              # First-time setup
├── Update_And_Rebuild.ps1               # Build script
└── Update_And_Rebuild.bat               # Build script (Windows)

D:\FeedbackCollector_Desktop_Build\     # Build directory
├── src\                                 # Copied source
│   ├── .env                            # ← Copied credentials
│   └── ...
├── FeedbackCollector.spec              # Build spec
├── build\                              # Temporary build files
├── dist\FeedbackCollector\             # Final output
│   ├── FeedbackCollector.exe
│   └── _internal\
│       └── .env                        # ← Included in distribution
└── Update_And_Rebuild.ps1              # Local build script
```

## What Gets Included

### Always Included (via spec file)
- ✅ All Python source code
- ✅ HTML templates
- ✅ Static files (CSS, JS)
- ✅ Configuration files (JSON)
- ✅ **.env file** (with credentials)

### Dependencies
All Python packages from requirements.txt are bundled.

## Build Options

### Standard Build
```powershell
.\Update_And_Rebuild.ps1
```

### Clean Build (recommended after adding dependencies)
The script automatically uses `--clean` flag.

### Manual Build
```powershell
cd D:\FeedbackCollector_Desktop_Build
python -m PyInstaller FeedbackCollector.spec --noconfirm --clean
```

## Troubleshooting

### .env File Not Included
- Check if `src\.env` exists in development directory
- Script will show warning if .env is missing
- Verify in `dist\FeedbackCollector\_internal\.env`

### Build Fails
1. Ensure Python is in PATH
2. Check PyInstaller is installed: `python -m PyInstaller --version`
3. Try clean build: already included in script

### Missing Dependencies
1. Update requirements.txt in development
2. Re-run Setup_Desktop_Build.ps1
3. Or manually: `pip install -r src\requirements.txt`

### Executable Won't Run
- Check console output for errors
- Verify .env file exists in `_internal\` folder
- Ensure ODBC driver installed on target machine

## Security Notes

⚠️ **Important**: The .env file contains sensitive credentials:
- Reddit API keys
- Azure/Fabric tokens
- Database connection strings

**Distribution Checklist**:
- ✅ Ensure .env has correct, valid credentials
- ✅ Only share with authorized users
- ✅ Consider creating separate .env for distribution vs development
- ✅ Rotate credentials if needed

## When to Rebuild

Rebuild after:
- ✅ Changing Python code (*.py)
- ✅ Updating templates or static files
- ✅ Modifying configuration (JSON files)
- ✅ Updating .env credentials
- ✅ Adding new dependencies

## Automation

The `Update_And_Rebuild.ps1` script handles the complete workflow automatically. Just run it after making changes!

---

**Last Updated**: November 2025
