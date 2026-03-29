@echo off
REM ═══════════════════════════════════════════════════════════════
REM  CanadaMart POS – Windows Build Script
REM  Run this from the project root directory.
REM  Requires Python, pip and PyInstaller.
REM ═══════════════════════════════════════════════════════════════

echo.
echo  =============================================
echo   CanadaMart POS – Building Windows EXE
echo  =============================================
echo.

REM Install / upgrade dependencies
pip install -r requirements.txt --upgrade

REM Clean previous build
if exist "dist\CanadaMartPOS" rmdir /s /q "dist\CanadaMartPOS"
if exist "build\CanadaMartPOS" rmdir /s /q "build\CanadaMartPOS"

REM Build
pyinstaller build.spec --clean --noconfirm

if %ERRORLEVEL% EQU 0 (
    echo.
    echo  BUILD SUCCESSFUL!
    echo  EXE located at: dist\CanadaMartPOS\CanadaMartPOS.exe
    echo.
) else (
    echo.
    echo  BUILD FAILED – check errors above.
    echo.
)
pause
