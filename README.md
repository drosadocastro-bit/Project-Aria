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
└── assets/                        # Assets (auto-created)
```

## Quick Start

### 1. Install Dependencies

```cmd
pip install -r requirements.txt
```

### 2. Configure

Edit `config.py`:
- Set your LM Studio IP address
- Configure OBD-II COM port (check Device Manager)
- Update ElevenLabs API key if needed

### 3. Run

```cmd
# Console mode (default)
python aria.py

# With personality/language options
python aria.py --personality joi --language en
python aria.py --personality aria --language es

# Avatar mode (WebSocket server)
python aria.py --mode avatar
```

Then open `joi_avatar.html` in your browser.

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

- **LM Studio**: Running locally with a loaded model
- **ElevenLabs**: API key (already configured)
- **OBD-II**: Bluetooth adapter paired to Windows (optional)
- **ffmpeg**: Included in `ffmpeg/bin/`

## Personalities

### JOI 💜
> "Hello. I've been waiting for you."

Holographic AI companion inspired by Blade Runner 2049. Caring, attentive, emotionally intelligent.

### Aria 🚗
> "Hey! Ready to work on the GTI?"

Car-focused AI copilot. Knowledgeable, helpful, friendly.

## License

MIT License
