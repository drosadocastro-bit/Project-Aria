@echo off
echo ========================================
echo   Aria Driving Contract Test Suite
echo ========================================
echo.

echo Running tests...
python test_driving_contract.py

echo.
echo ========================================
echo   Running Demo
echo ========================================
echo.

python demo_driving_contract.py

echo.
pause
