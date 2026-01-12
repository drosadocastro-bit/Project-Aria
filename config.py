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
LM_STUDIO_API = "http://127.0.0.1:1234/v1/chat/completions"
LM_STUDIO_MODEL = "google/gemma-3n-e4b"  # Your current model

# ========== VOICE CONFIG ==========
USE_ELEVENLABS = True  # Set to False to disable voice

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_KEY", "sk_de07da0549c7911619d9cedd8e3b9b8668a402e3152e10c1")
ELEVENLABS_VOICE_ID = "v8DWAeuEGQSfwxqdH9t2"  # JOI voice
ELEVENLABS_HEADERS = {
    "xi-api-key": ELEVENLABS_API_KEY,
    "Content-Type": "application/json"
}

# ========== OBD-II CONFIG (Windows) ==========
OBD_ENABLED = True  # Set to False to disable OBD
OBD_PORT = "COM3"  # Change to your Bluetooth COM port (check Device Manager) or set to "AUTO" for auto-detection
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

# ========== STATE MANAGEMENT (Driving Contract) ==========
# Speed threshold for PARKED→DRIVING transition
STATE_SPEED_THRESHOLD = 5.0  # mph

# Idle duration threshold for DRIVING→PARKED transition
STATE_IDLE_THRESHOLD = 10.0  # seconds (stopped duration for PARKED)

# Auto-transition timeout for PARKED→GARAGE
STATE_GARAGE_TIMEOUT = 1800  # seconds (30 minutes)

# Hysteresis duration to prevent rapid state switching
STATE_HYSTERESIS_DURATION = 3.0  # seconds

# Response constraints for DRIVING mode
DRIVING_MAX_RESPONSE_LENGTH = 150  # characters
DRIVING_ALLOW_QUESTIONS = False  # No questions in DRIVING mode
DRIVING_ALLOW_EMOTION = False  # No affectionate/emotional language in DRIVING

# Manual state override settings
STATE_MANUAL_OVERRIDE_ENABLED = True  # Allow manual state override
STATE_MANUAL_OVERRIDE_VALUE = None  # None, "PARKED", "GARAGE", or "DRIVING"
