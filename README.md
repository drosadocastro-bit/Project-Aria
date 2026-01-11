# Project Aria - GTI AI Copilot

AI companion for your VW GTI MK6 with holographic avatar.

## Features

- 🤖 **Dual Personalities**: JOI (Blade Runner-inspired) or Aria (car copilot)
- 🗣️ **Voice**: ElevenLabs premium TTS
- 🧠 **LLM**: Local via LM Studio
- 🚗 **OBD-II**: Real-time car data
- 📚 **NIC Integration**: Access repair manuals (optional)
- 🌐 **Holographic Avatar**: Browser-based visual interface
- 🌍 **Bilingual**: English/Spanish

## Project Structure

```
Project_Aria/
├── README.md
├── requirements.txt
├── config.py                      # Configuration
├── config.example.py              # Example configuration template
├── aria.py                        # Main script (console + WebSocket)
├── joi_avatar.html                # Browser-based holographic avatar
│
├── core/
│   ├── __init__.py
│   ├── personality.py             # JOI/Aria personalities
│   ├── voice.py                   # ElevenLabs TTS
│   └── obd_integration.py         # OBD-II connection
│
├── queue/                         # Audio files (auto-created)
├── logs/                          # Logs (auto-created)
├── assets/                        # Assets (auto-created)
│
├── setup.bat                      # Windows setup script
├── start.bat                      # Quick start script
├── test_obd.bat                   # OBD test script
├── TROUBLESHOOTING.md             # Troubleshooting guide
└── EXAMPLES.md                    # Example queries
```

## Quick Start Scripts

### Windows Batch Files

- **setup.bat** - Install dependencies and configure
- **start.bat** - Quick start with connection checks
- **test_obd.bat** - Test OBD-II connection only

### First Time Setup

```cmd
# 1. Run setup
setup.bat

# 2. Start LM Studio and load google/gemma-3n-e4b

# 3. Run Aria
start.bat
```

## Manual Setup

### 1. Install Dependencies

```cmd
# Use the setup script (Windows)
setup.bat

# Or manually
pip install -r requirements.txt
```

### 2. Configure

**Option 1: Use the example config**
```cmd
copy config.example.py config.py
```
Then edit `config.py` with your settings.

**Option 2: Edit existing config.py**
- Set your LM Studio IP address (default: http://127.0.0.1:1234)
- Configure OBD-II COM port (check Device Manager) or use "AUTO" for auto-detection
- Update ElevenLabs API key if needed (or set ELEVENLABS_KEY environment variable)

### 3. Run

**Quick Start (Windows):**
```cmd
start.bat
```

**Manual Start:**
```cmd
# Console mode (default)
python aria.py

# With personality/language options
python aria.py --personality joi --language en
python aria.py --personality aria --language es

# Avatar mode (WebSocket server)
python aria.py --mode avatar
```

Then open `joi_avatar.html` in your browser for avatar mode.

## Testing Components

### Test OBD-II Connection
```cmd
test_obd.bat
```

### Test LM Studio Connection
Open in browser: http://127.0.0.1:1234/v1/models

## Commands (Console Mode)

| Command | Description |
|---------|-------------|
| `/joi` | Switch to JOI personality |
| `/aria` | Switch to Aria personality |
| `/en` | Switch to English |
| `/es` | Switch to Spanish |
| `/status` | Show OBD-II car status |
| `exit` | Quit |

## Requirements

- **LM Studio**: Running locally with a loaded model (google/gemma-3n-e4b recommended)
- **ElevenLabs**: API key (set via ELEVENLABS_KEY environment variable or in config.py)
- **OBD-II**: Bluetooth adapter paired to Windows (optional, can be disabled in config.py)
- **ffmpeg**: For audio playback (update FFPLAY_PATH in config.py)

## Personalities

### JOI 💜
> "Hello. I've been waiting for you."

Holographic AI companion inspired by Blade Runner 2049. Caring, attentive, emotionally intelligent.

### Aria 🚗
> "Hey! Ready to work on the GTI?"

Car-focused AI copilot. Knowledgeable, helpful, friendly.

## License

MIT License

## Additional Resources

- **TROUBLESHOOTING.md** - Solutions for common issues
- **EXAMPLES.md** - Sample queries and commands
- **config.example.py** - Template configuration file
