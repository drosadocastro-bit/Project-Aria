"""
Voice generation with ElevenLabs
"""

import requests
import uuid
import subprocess
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import *


def generate_voice(text):
    """Generate voice using ElevenLabs."""
    if not USE_ELEVENLABS:
        return None
    
    file_id = str(uuid.uuid4())
    output_path = QUEUE_FOLDER / f"{file_id}.mp3"

    voice_payload = {
        "text": text,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    
    try:
        response = requests.post(url, headers=ELEVENLABS_HEADERS, json=voice_payload, timeout=10)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        print(f"🎙️ Voice generated: {output_path.name}")
        return output_path
        
    except Exception as e:
        print(f"❌ ElevenLabs error: {e}")
        return None


def play_audio(path):
    """Play audio file using ffplay."""
    if not path or not Path(path).exists():
        return
    
    try:
        subprocess.Popen([
            FFPLAY_PATH, "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"❌ Audio playback error: {e}")


def cleanup_old_files():
    """Keep only recent audio files."""
    import os
    
    files = sorted(QUEUE_FOLDER.glob("*.mp3"), key=os.path.getctime)
    
    while len(files) > AUDIO_QUEUE_LIMIT:
        try:
            files[0].unlink()
        except:
            pass
        files = files[1:]
