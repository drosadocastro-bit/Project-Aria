# Troubleshooting Guide

## LM Studio Issues

### "Cannot connect to LM Studio"
**Symptoms:** Error message about LM Studio not responding

**Solutions:**
1. Make sure LM Studio is running
2. Check model is loaded (google/gemma-3n-e4b)
3. Verify API server is enabled in LM Studio settings
4. Test connection: http://127.0.0.1:1234/v1/models

### "Model not found"
**Solutions:**
1. Download google/gemma-3n-e4b in LM Studio
2. Or change LM_STUDIO_MODEL in config.py to your loaded model

## OBD-II Issues

### "OBD-II connection failed"
**Checklist:**
- [ ] OBDLink plugged into car
- [ ] Car ignition ON (engine doesn't need to run)
- [ ] OBDLink paired via Bluetooth
- [ ] Correct COM port in config.py

**Finding COM Port:**
1. Windows + X → Device Manager
2. Ports (COM & LPT)
3. Look for "Standard Serial over Bluetooth"
4. Note the COM number (e.g., COM3)

**Auto-Detection:**
Set `OBD_PORT = "AUTO"` in config.py

## Audio Issues

### "No voice output"
**Solutions:**
1. Check FFPLAY_PATH in config.py
2. Test ffplay: `C:\path\to\ffplay.exe -version`
3. Verify ElevenLabs API key
4. Set USE_ELEVENLABS = False to disable voice temporarily

## General Issues

### "Module not found"
**Solution:**
```cmd
pip install -r requirements.txt
```

### "Permission denied" on queue/logs folders
**Solution:**
Run as administrator or check folder permissions
