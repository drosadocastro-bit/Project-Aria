"""
Project Aria Configuration (Windows)
"""

import os
from pathlib import Path

# ========== PATHS (Windows) ==========
PROJECT_ROOT = Path(__file__).parent
QUEUE_FOLDER = PROJECT_ROOT / "queue"
LOGS_FOLDER = PROJECT_ROOT / "logs"
ASSETS_FOLDER = PROJECT_ROOT / "assets"

# Create directories
for folder in [QUEUE_FOLDER, LOGS_FOLDER, ASSETS_FOLDER]:
    folder.mkdir(parents=True, exist_ok=True)

# ========== NIC INTEGRATION (if you have it) ==========
NIC_PATH = os.getenv("NIC_PATH", str(Path.home() / "nic"))
NIC_ENABLED = os.path.exists(NIC_PATH) and os.path.exists(Path(NIC_PATH) / "backend.py")

# ========== LLM CONFIG (LM Studio on Windows) ==========
LM_STUDIO_API = "http://172.29.144.1:1234/v1/chat/completions"
LM_STUDIO_MODEL = "granite-4-h-tiny"  # Your current model

# ========== VOICE CONFIG ==========
USE_ELEVENLABS = True  # Set to False to disable voice

ELEVENLABS_API_KEY = "sk_de07da0549c7911619d9cedd8e3b9b8668a402e3152e10c1"
ELEVENLABS_VOICE_ID = "v8DWAeuEGQSfwxqdH9t2"  # JOI voice
ELEVENLABS_HEADERS = {
    "xi-api-key": ELEVENLABS_API_KEY,
    "Content-Type": "application/json"
}

# ========== OBD-II CONFIG (Windows) ==========
OBD_ENABLED = True  # Set to False to disable OBD
OBD_PORT = "COM3"  # Change to your Bluetooth COM port (check Device Manager)
OBD_BAUDRATE = 115200

# ========== WEBSOCKET CONFIG ==========
WEBSOCKET_HOST = "localhost"
WEBSOCKET_PORT = 5001

# ========== LANGUAGE & PERSONALITY ==========
DEFAULT_LANGUAGE = "en"  # "en" or "es"
DEFAULT_PERSONALITY = "joi"  # "joi" or "aria"

# ========== AUDIO (Windows) ==========
FFPLAY_PATH = "C:\\Project_Aria\\ffmpeg\\bin\\ffplay.exe"  # Your existing ffplay
AUDIO_QUEUE_LIMIT = 20

# ========== LOGGING ==========
LOG_LEVEL = "INFO"
LOG_FILE = LOGS_FOLDER / "aria.log"
