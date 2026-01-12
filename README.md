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
- 🚦 **Driving Contract**: State-aware safety enforcement (DRIVING/PARKED/GARAGE modes)

## Operational States (Driving Contract)

Aria adapts her behavior based on vehicle state for **driver safety**:

### 🚗 DRIVING Mode
- **Trigger**: Vehicle moving (speed ≥ 5 mph) or temporarily stopped at traffic lights
- **Behavior**: Ultra-concise responses (max 150 chars), structured format only
- **Response Format**: `[Metric] → [Interpretation] → [Action]`
- **Restrictions**: No questions, no emotional language, no humor, no verbose explanations
- **Philosophy**: "Silence is safer than distraction"

**Example**: 
```
User: "What's my coolant temp?"
Aria: "Coolant: 92°C → Normal range → Continue monitoring."
```

### 🅿️ PARKED Mode
- **Trigger**: Engine off, stopped >10 seconds, or parking brake engaged
- **Behavior**: Full conversational mode with personality expression
- **Response Style**: Detailed explanations, emotional warmth, questions allowed
- **Use Cases**: Deep diagnostics, learning about your car, friendly chat

**Example**:
```
User: "What's my coolant temp?"
Aria: "Your coolant is sitting at 92°C, which is perfectly normal! The MK6's TSI runs a bit warm by design, but you're well within the 80-100°C operating range. Everything looks healthy!"
```

### 🔧 GARAGE Mode
- **Trigger**: Manual override or sustained PARKED >30 minutes
- **Behavior**: Maximum technical detail, repair manual integration, step-by-step procedures
- **Response Style**: Verbose technical explanations with citations
- **Use Cases**: Repairs, maintenance procedures, troubleshooting

**Example**:
```
User: "How do I replace the PCV valve?"
Aria: "PCV valve replacement on GTI MK6 (TSI EA888 Gen 1):
Tools needed: T25 Torx, 10mm socket...
[Full step-by-step procedure with torque specs and manual citations]"
```

**Documentation**: See `docs/ARIA_DRIVING_CONTRACT.md` for complete specification.

**State Control**: 
- Automatic state detection via OBD-II speed/RPM telemetry
- Manual override: `/setstate PARKED|GARAGE|DRIVING` (console mode)
- Check state: `/state` command

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
│   ├── obd_integration.py         # OBD-II connection
│   ├── state_manager.py           # Vehicle state detection (DRIVING/PARKED/GARAGE)
│   └── response_validator.py     # DRIVING mode response enforcement
│
├── docs/
│   └── ARIA_DRIVING_CONTRACT.md   # Complete operational state specification
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
| `/state` | Show current vehicle state (DRIVING/PARKED/GARAGE) |
| `/setstate [STATE]` | Manually override state (PARKED, GARAGE, or DRIVING) |
| `/clearstate` | Clear manual state override (return to automatic) |
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
