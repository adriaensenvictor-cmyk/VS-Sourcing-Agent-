@echo off
rem FirstTrace live desk for Windows: double-click this file.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 scout.py --serve
  goto done
)
where python >nul 2>nul
if %errorlevel%==0 (
  python scout.py --serve
  goto done
)
echo Python 3 is not installed. Install it from https://www.python.org/downloads/ and run this file again.
echo Without Python, open FirstTrace-offline.html in your browser instead.
:done
pause
