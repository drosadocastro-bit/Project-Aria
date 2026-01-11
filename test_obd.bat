@echo off
echo ========================================
echo   OBD-II Connection Test
echo ========================================
echo.

python -c "from core.obd_integration import obd_monitor; print('Testing connection...'); data = obd_monitor.get_live_data(); print('✅ Connected!' if data else '❌ Connection failed'); print(obd_monitor.format_status(data) if data else 'Check TROUBLESHOOTING.md')"

echo.
pause
