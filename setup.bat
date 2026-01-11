@echo off
echo ========================================
echo   Project Aria - GTI AI Copilot Setup
echo ========================================
echo.

echo Installing Python dependencies...
pip install -r requirements.txt

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Make sure LM Studio is running at http://127.0.0.1:1234
echo 2. Load model: google/gemma-3n-e4b
echo 3. Configure OBD-II COM port in config.py (or use auto-detect)
echo 4. Run: python aria.py
echo.
pause
