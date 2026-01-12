# Project Aria - GTI AI Copilot

AI-powered automotive companion for VW GTI MK6 with voice interaction, OBD-II telemetry, and holographic avatar.

## Architecture Overview

```
aria.py (main entry)
├── config.py           # All configuration (paths, API keys, OBD settings)
├── core/
│   ├── personality.py  # JOI/Aria personas with bilingual prompts
│   ├── voice.py        # ElevenLabs TTS generation + audio playback
│   └── obd_integration.py  # OBD-II sensor monitoring
├── joi_avatar.html     # Browser-based holographic interface (WebSocket)
└── queue/              # Temporary audio files (auto-cleanup)
```

**Data Flow**: User input → LLM (LM Studio) + OBD context + NIC manual lookup → Response → ElevenLabs TTS → Audio playback

## Quick Start

```cmd
start.bat                          # Checks LM Studio, launches aria.py
python aria.py --personality joi   # JOI persona (Blade Runner style)
python aria.py --personality aria  # Car-focused copilot
python aria.py --mode avatar       # WebSocket server for browser avatar
```

**Prerequisite**: LM Studio must be running at `http://127.0.0.1:1234` with `google/gemma-3n-e4b` loaded.

## Key Configuration (config.py)

All settings are centralized in `config.py`. Critical values:
- `LM_STUDIO_API` / `LM_STUDIO_MODEL` - LLM endpoint and model name
- `ELEVENLABS_API_KEY` - TTS (prefer `ELEVENLABS_KEY` env var)
- `OBD_PORT` - COM port for Bluetooth OBD adapter (`"AUTO"` for detection)
- `FFPLAY_PATH` - Path to ffmpeg's ffplay for audio

## Code Patterns

### Adding a New Personality
Edit `core/personality.py`:
```python
PERSONALITIES["new_persona"] = {
    "name": "Name",
    "system_prompt_en": "...",
    "system_prompt_es": "...",  # Bilingual support
    "greetings": [...],
}
```

### OBD Telemetry Integration
`obd_monitor.get_live_data()` returns dict with: rpm, speed, coolant_temp, throttle, fuel_trim_short/long, intake_temp, maf. The main loop in `aria.py` automatically injects car context into LLM prompts.

### NIC Manual Lookup (Optional)
If `NIC_PATH` points to a valid `nova_rag_public` install, car-related questions trigger RAG lookup via `query_nic_for_context()`. Keywords: torque, pressure, code, diagnostic, replace, install, repair, manual, procedure, spec.

## Runtime Commands (Console Mode)

| Command | Action |
|---------|--------|
| `/joi`, `/aria` | Switch personality |
| `/en`, `/es` | Switch language |
| `/status` | Show live OBD-II data |
| `exit` | Quit |

## File Conventions

- **Audio files**: UUID-based names in `queue/` (e.g., `{uuid}.mp3`), auto-cleaned beyond `AUDIO_QUEUE_LIMIT`
- **Logs**: Written to `logs/aria.log`
- **Legacy prototypes**: `aeter_talk_to.py`, `talk_to_joi*.py` (superseded by `aria.py`)

## Security

⚠️ `config.py` contains a real API key. Use environment variable `ELEVENLABS_KEY` instead, or replace with placeholder before commits.

## Testing

```cmd
test_obd.bat                       # Test OBD-II connection only
curl http://127.0.0.1:1234/v1/models  # Verify LM Studio is running
```

## Dependencies

Install: `pip install -r requirements.txt`  
Core: `requests`, `websockets`, `python-obd`  
Audio: ffmpeg/ffplay in `ffmpeg/bin/`

## Future Roadmap

**Phase 2: Jetson Orin Nano Deployment**
- Port to JetPack (Ubuntu-based) with TensorRT-optimized models
- Replace ffplay with ALSA/PulseAudio for embedded audio
- Target: offline operation, <2s voice response latency

**Phase 3: Vehicle Integration**
- RAG system via `nova_rag_public` repo with VW MK6 Bentley/Haynes manuals
- CAN bus telemetry logging + anomaly detection ML
- Computer vision (Arducam → Pi Zero W2 → Jetson inference)
- MiniDSP integration for car audio (replace Equalizer APO)

## Audio Intelligence

The `auto_eq.py` system monitors Spotify and auto-adjusts EQ:
- `core/audio_intelligence.py` - Genre→EQ mapping with confidence scoring
- `music_dataset/` - 1,449 tracks with genre labels
- Truthful logging: `phonk → v_shape (100%)`
- Driving mode: rate-limited, ultra-short voice phrases
- Ready for MiniDSP hardware (currently uses Equalizer APO)

