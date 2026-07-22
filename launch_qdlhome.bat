@echo off
REM Activate the virtual environment
call "C:\Users\QT3 User Facility\qdl-utils\vqlm-home-venv\Scripts\activate.bat"

REM Launch qdlhome GUI within the virtual environment
python "C:\Users\QT3 User Facility\qdl-utils\src\qdlutils\applications\qdlhome\main.py"

REM Optional: Pause to keep the window open
pause
