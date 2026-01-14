# Persona Routing Implementation - Testing Guide

## Overview

This document provides instructions for testing the new persona routing features implemented in Project Aria.

## What Was Implemented

### Core Features

1. **JOI → Nova Rename**
   - The JOI persona has been renamed to Nova
   - All references updated in code, docs, and UI
   - No functionality changes—purely a canonical naming update

2. **Per-Turn Persona Routing**
   - Users can address "Nova" or "Aria" in any message without changing default
   - Format: `"Nova, [your question]"` or `"Aria, [your question]"`
   - The prefix is detected, stripped, and routing happens for that turn only
   - Default personality remains unchanged unless explicit switch command used

3. **Spanglish-Friendly Language Detection**
   - Automatic per-turn language detection for Spanish, English, or mixed
   - Lightweight heuristic based on common Spanish words and accented characters
   - Language auto-detected and passed to TTS for appropriate voice selection

4. **Persona-Aware TTS Routing**
   - New `core/tts_router.py` module routes persona+language → voice backend
   - Supports ElevenLabs (preferred) and offline TTS (Coqui/pyttsx3)
   - Configuration via `PERSONA_VOICE_MAP` in config.py
   - Audio files saved to `static/tts/` for browser playback

5. **Frontend UI Updates**
   - `static/nova_avatar.html` with dynamic persona theming
   - WebSocket messages include persona + UI + voice metadata
   - Avatar colors and animations switch based on active persona
   - Nova: Purple/cyan gradient (#7b2cbf, #00d4ff)
   - Aria: Cyan/green gradient (#00D1FF, #00ff88)

### Files Changed

**Core Modules:**
- `core/personality.py` - Renamed JOI → Nova, added detection/routing functions
- `core/tts_router.py` - NEW: TTS routing with persona/language awareness
- `aria.py` - Per-turn routing in WebSocket and console mode

**Configuration:**
- `config.example.py` - Added `PERSONA_VOICE_MAP` and backend settings

**Frontend:**
- `static/nova_avatar.html` - NEW: Updated UI with persona theming
- `joi_avatar.html` - Updated to match nova_avatar.html (backward compat)

**Documentation:**
- `README.md` - Updated with per-turn addressing examples
- `docs/deployment/PERSONA_ROUTING.md` - NEW: Comprehensive routing docs
- `EXAMPLES.md` - Added per-turn addressing examples
- `docs/deployment/OFFLINE_TTS_STT.md` - Updated references

**Tests:**
- `tests/test_persona_routing.py` - NEW: Unit tests for routing functions
- `validate_persona_routing.py` - NEW: End-to-end validation script

**Other:**
- `start.bat` - Updated to use nova instead of joi

## Testing Instructions

### Prerequisites

- Python 3.8+
- LM Studio running at `http://127.0.0.1:1234` with a model loaded
- (Optional) ElevenLabs API key for voice generation
- (Optional) Offline TTS setup (Coqui or pyttsx3)

### 1. Validate Core Implementation (No LM Studio Required)

Run the validation script to test core functions:

```bash
python validate_persona_routing.py
```

Expected output: All 9 tests should pass (✅).

### 2. Test Console Mode

Start Aria in console mode:

```bash
python aria.py --mode console --personality nova
```

**Test cases:**

1. **Per-turn addressing:**
   ```
   You: Nova, what is quantum mechanics?
   Nova: [response about quantum mechanics]
   
   You: Aria, what's the coolant temperature?
   Aria: [response about car telemetry]
   
   You: Tell me more
   Nova: [response from default persona Nova]
   ```

2. **Explicit personality switch:**
   ```
   You: /aria
   System: 🚗 Switched to Aria personality
   
   You: What's the status?
   Aria: [response]
   
   You: /nova
   System: 💜 Switched to Nova personality
   ```

3. **Language detection (if bilingual):**
   ```
   You: ¿Qué temperatura tiene el refrigerante?
   Nova: [Spanish response]
   
   You: What about the oil temperature?
   Nova: [English response]
   ```

4. **State commands:**
   ```
   You: /status
   [Shows OBD-II telemetry if connected]
   
   You: /state
   [Shows vehicle state: PARKED, DRIVING, or GARAGE]
   ```

### 3. Test Avatar Mode (WebSocket)

Start Aria in avatar mode:

```bash
python aria.py --mode avatar
```

Then open in your browser:
- Primary: `static/nova_avatar.html`
- Legacy: `joi_avatar.html` (same functionality)

**Test cases:**

1. **Connection:**
   - Status dot should turn green
   - "Connected" message should appear
   - Greeting from Nova should display

2. **Per-turn addressing in chat:**
   - Type: `Nova, hello!`
   - Observe: Message routed to Nova, avatar stays purple/cyan
   - Type: `Aria, check engine`
   - Observe: Message routed to Aria, avatar switches to cyan/green
   - Type: `What else?`
   - Observe: Uses default persona (Nova)

3. **Explicit personality buttons:**
   - Click "ARIA" button
   - Observe: Avatar colors change to cyan/green
   - Default persona now Aria
   - Click "NOVA" button
   - Observe: Avatar colors change to purple/cyan

4. **Voice playback (if TTS configured):**
   - Responses should include voice metadata in console
   - Audio should auto-play in browser
   - Check browser console for audio fetch logs

5. **WebSocket message inspection:**
   - Open browser DevTools → Network → WS
   - Send a query
   - Inspect response JSON:
     ```json
     {
       "type": "response",
       "persona": "nova",
       "text": "...",
       "ui": {
         "theme": "nova",
         "accent": "#7b2cbf",
         ...
       },
       "voice": {
         "audio_path": "/tts/abc123.wav",
         "backend": "elevenlabs",
         ...
       }
     }
     ```

### 4. Test Driving Contract Integration

The driving contract should apply **regardless of persona**:

```bash
python aria.py --mode console --personality nova
```

Commands:
```
You: /setstate DRIVING
System: 🔧 Manual override set to: DRIVING

You: Nova, what's the coolant temperature?
Nova: Coolant: 92°C → Normal → OK
# (Constrained to 150 chars, no emotional language)

You: Aria, tell me about the engine
Aria: Monitoring.
# (Non-essential question in DRIVING mode)

You: /clearstate
System: 🔓 Manual override cleared
```

### 5. Test TTS Routing (Optional)

If you have ElevenLabs configured or offline TTS enabled:

1. **Configure voices in config.py:**
   ```python
   PERSONA_VOICE_MAP = {
       "nova": {
           "en": "your_elevenlabs_voice_id",
           "es": "your_elevenlabs_voice_id_spanish"
       },
       "aria": {
           "en": "different_voice_id",
           "es": "different_voice_id_spanish"
       }
   }
   ```

2. **Test voice routing:**
   ```bash
   export NOVA_TTS_BACKEND=elevenlabs  # or auto, coqui, pyttsx3
   python aria.py --mode console
   ```

3. **Observe:**
   - Nova responses should use Nova's configured voice
   - Aria responses should use Aria's configured voice
   - Spanish text should route to Spanish voice IDs
   - Check console logs for TTS backend selection

### 6. Run Unit Tests

```bash
# Run existing driving contract tests
python test_driving_contract.py

# Run persona routing tests (if pytest installed)
pytest tests/test_persona_routing.py -v

# Or run directly
python tests/test_persona_routing.py
```

Expected: All tests should pass.

## Known Limitations

1. **Language detection heuristic is simple:**
   - For production, consider installing `langdetect`: `pip install langdetect`
   - Update `core/personality.py` to use langdetect library

2. **TTS voice IDs must be configured manually:**
   - No auto-discovery of ElevenLabs voices
   - Configure `PERSONA_VOICE_MAP` in `config.py`

3. **Frontend requires manual refresh on personality switch:**
   - Switching via `/nova` command in console doesn't update browser
   - Use the personality buttons in the UI instead

4. **Audio playback depends on backend configuration:**
   - ElevenLabs: Requires API key and voice IDs
   - Offline: Requires Coqui TTS or pyttsx3 installation
   - Fallback: Silent mode if no backend available

## Troubleshooting

### "No module named 'websockets'"
```bash
pip install websockets aiohttp
```

### "No TTS backend available"
```bash
# For offline TTS:
pip install TTS  # Coqui TTS
# Or
pip install pyttsx3  # Windows fallback

# Set environment variable:
export OFFLINE_TTS_ENABLED=true
```

### "Cannot connect to LM Studio"
- Verify LM Studio is running
- Check that a model is loaded
- Confirm API endpoint: `http://127.0.0.1:1234`
- Test with: `curl http://127.0.0.1:1234/v1/models`

### Persona prefix not detected
- Ensure format is: `"Nova,"` or `"Aria:"` at start of message
- Check case-insensitive: `"nova,"` works too
- Prefix must be at the start (not middle) of message

### Language detection incorrect
- Heuristic is simple; install langdetect for accuracy
- Spanish needs >30% Spanish indicators to be detected
- Override by setting language explicitly: `/es` or `/en`

## Success Criteria

✅ All validation tests pass  
✅ Per-turn routing works in console and avatar mode  
✅ Default personality unchanged after per-turn addressing  
✅ Explicit switch commands (`/nova`, `/aria`) work  
✅ Language detection identifies Spanish vs English  
✅ UI theme switches between Nova and Aria  
✅ Driving contract applies regardless of persona  
✅ Existing driving contract tests pass  

## Next Steps

1. **Manual testing with LM Studio** (requires user)
2. **Configure ElevenLabs voice IDs** (optional)
3. **Test with real OBD-II connection** (optional)
4. **Deploy to Jetson Orin Nano** (future)

## Support

For issues or questions:
- Check `docs/deployment/PERSONA_ROUTING.md` for detailed documentation
- Review `TROUBLESHOOTING.md` for common issues
- Run `validate_persona_routing.py` to verify core functions
