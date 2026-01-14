@echo off
title Project Aria - GTI AI Copilot

echo ========================================
echo   Project Aria - GTI AI Copilot
echo ========================================
echo.

REM Check if LM Studio is running
echo Checking LM Studio connection...
curl -s http://127.0.0.1:1234/v1/models >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ⚠️  WARNING: Cannot connect to LM Studio
    echo    Please start LM Studio and load google/gemma-3n-e4b
    echo.
    pause
    exit /b 1
)

echo ✅ LM Studio connected
echo.

REM Run Aria
echo Starting Aria in console mode...
echo.
python aria.py --personality nova --language en

pause
