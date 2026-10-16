@echo off
cd /d "%~dp0"
python -c "import sys" 2>nul || (
    echo Python isn't installed - installing it now, one moment...
    winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    echo.
    echo Python is installed. Close this window and double-click the same file again.
    pause
    exit /b
)
python -c "import importlib.util as u, sys; sys.exit(not all(u.find_spec(m) for m in ('pygame', 'vgamepad', 'pystray', 'PIL')))" 2>nul || (
    echo Installing what PadBridge needs, one moment...
    python -m pip install -r requirements.txt
)
python -m padbridge %*
pause
