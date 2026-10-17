@echo off
REM ============================================================
REM  RCD Reviewer - fully self-contained build (Windows)
REM  Requires: Python 3.x with PyInstaller installed
REM      pip install pyinstaller
REM
REM  Run this file from the project root (where main_menu.py is).
REM  Result goes into the "RCD Reviewer" folder, ready to zip up
REM  and share. Your friends just double-click RCDReviewer.exe -
REM  NO Python installation needed on their PC.
REM ============================================================
setlocal
cd /d "%~dp0"

set OUT=RCD Reviewer

echo [1/4] Cleaning previous build...
if exist "%OUT%" rd /s /q "%OUT%"
mkdir "%OUT%\Topics" "%OUT%\Formulas"

echo [2/4] Building main menu...
pyinstaller --onefile --windowed --noconfirm --distpath build_tmp --workpath build_tmp\work --specpath build_tmp --name RCDReviewer main_menu.py || goto :error
copy /y build_tmp\RCDReviewer.exe "%OUT%\" >nul

echo [3/4] Building all Topics apps...
for %%F in (Topics\*.py) do (
    echo   - %%~nF
    pyinstaller --onefile --windowed --noconfirm --distpath build_tmp --workpath build_tmp\work --specpath build_tmp --name "%%~nF" "%%F" || goto :error
    copy /y "build_tmp\%%~nF.exe" "%OUT%\Topics\" >nul
)

echo [4/4] Building all Formula apps...
for %%F in (Formulas\*.py) do (
    echo   - %%~nF
    pyinstaller --onefile --windowed --noconfirm --distpath build_tmp --workpath build_tmp\work --specpath build_tmp --name "%%~nF" "%%F" || goto :error
    copy /y "build_tmp\%%~nF.exe" "%OUT%\Formulas\" >nul
)

rd /s /q build_tmp
echo.
echo ============================================================
echo  DONE! Share the entire "%OUT%" folder (zip it up).
echo  Friends run: %OUT%\RCDReviewer.exe
echo ============================================================
pause
exit /b 0

:error
echo BUILD FAILED - check the message above.
pause
exit /b 1
