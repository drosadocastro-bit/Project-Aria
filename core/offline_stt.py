"""
Offline STT (Speech-to-Text) using whisper.cpp
Transcribes audio files to text for voice interaction
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict
import tempfile

logger = logging.getLogger(__name__)

# whisper.cpp configuration
_whisper_cpp_path = None
_whisper_model_path = None
_backend_initialized = False


def initialize_stt():
    """
    Initialize whisper.cpp STT backend.
    
    Expects:
        - WHISPER_CPP_PATH env var pointing to whisper.cpp main binary
        - WHISPER_MODEL_PATH env var pointing to ggml model file
        - OR NOVA_OFFLINE_MODEL_DIR with models/ggml-*.bin files
    
    Returns:
        bool: True if initialization successful
    """
    global _whisper_cpp_path, _whisper_model_path, _backend_initialized
    
    if _backend_initialized:
        return True
    
    # Get whisper.cpp binary path
    whisper_env = os.getenv("WHISPER_CPP_PATH")
    if whisper_env:
        _whisper_cpp_path = Path(whisper_env)
    else:
        # Try common locations
        possible_paths = [
            Path.home() / "whisper.cpp" / "main",
            Path.home() / "whisper.cpp" / "main.exe",
            Path("/usr/local/bin/whisper"),
            Path("C:/whisper.cpp/main.exe"),
        ]
        
        for path in possible_paths:
            if path.exists():
                _whisper_cpp_path = path
                break
    
    if not _whisper_cpp_path or not _whisper_cpp_path.exists():
        logger.error("❌ whisper.cpp binary not found")
        logger.error("   Set WHISPER_CPP_PATH environment variable")
        logger.error("   See: docs/deployment/OFFLINE_TTS_STT.md")
        return False
    
    # Get model path
    model_env = os.getenv("WHISPER_MODEL_PATH")
    if model_env:
        _whisper_model_path = Path(model_env)
    else:
        # Try NOVA_OFFLINE_MODEL_DIR
        model_dir = os.getenv("NOVA_OFFLINE_MODEL_DIR")
        if model_dir:
            model_dir = Path(model_dir)
            
            # Prefer small or medium model
            for model_name in ["ggml-small.bin", "ggml-medium.bin", "ggml-base.bin"]:
                model_path = model_dir / model_name
                if model_path.exists():
                    _whisper_model_path = model_path
                    break
    
    if not _whisper_model_path or not _whisper_model_path.exists():
        logger.error("❌ Whisper model not found")
        logger.error("   Set WHISPER_MODEL_PATH or NOVA_OFFLINE_MODEL_DIR")
        logger.error("   Download models using: scripts/download_models.sh")
        logger.error("   See: docs/deployment/OFFLINE_TTS_STT.md")
        return False
    
    _backend_initialized = True
    logger.info(f"🎤 STT backend ready: whisper.cpp")
    logger.info(f"   Binary: {_whisper_cpp_path}")
    logger.info(f"   Model: {_whisper_model_path.name}")
    
    return True


def transcribe(audio_path: str, language: str = "en") -> Dict:
    """
    Transcribe audio file to text using whisper.cpp.
    
    Args:
        audio_path: Path to audio file (WAV, MP3, etc.)
        language: Language code (default: "en")
    
    Returns:
        dict: {
            "text": "transcribed text",
            "language": "en",
            "success": True,
            "model": "ggml-small.bin"
        }
    """
    global _whisper_cpp_path, _whisper_model_path
    
    # Ensure STT is initialized
    if not _backend_initialized:
        if not initialize_stt():
            return {
                "text": "",
                "language": language,
                "success": False,
                "error": "STT backend not initialized"
            }
    
    audio_file = Path(audio_path)
    if not audio_file.exists():
        logger.error(f"❌ Audio file not found: {audio_path}")
        return {
            "text": "",
            "language": language,
            "success": False,
            "error": f"File not found: {audio_path}"
        }
    
    try:
        # Build whisper.cpp command
        # Format: ./main -m model.bin -f audio.wav -l en -nt
        cmd = [
            str(_whisper_cpp_path),
            "-m", str(_whisper_model_path),
            "-f", str(audio_file),
            "-l", language,
            "-nt"  # No timestamps in output
        ]
        
        logger.debug(f"Running whisper.cpp: {' '.join(cmd)}")
        
        # Run whisper.cpp
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            logger.error(f"whisper.cpp failed: {result.stderr}")
            return {
                "text": "",
                "language": language,
                "success": False,
                "error": result.stderr
            }
        
        # Parse output (whisper.cpp outputs to stdout)
        transcription = result.stdout.strip()
        
        # Remove any metadata lines (lines starting with '[')
        lines = [line for line in transcription.split('\n') if not line.strip().startswith('[')]
        text = ' '.join(lines).strip()
        
        logger.info(f"✅ Transcription: {text[:100]}...")
        
        return {
            "text": text,
            "language": language,
            "success": True,
            "model": _whisper_model_path.name
        }
        
    except subprocess.TimeoutExpired:
        logger.error("❌ whisper.cpp timeout (>60s)")
        return {
            "text": "",
            "language": language,
            "success": False,
            "error": "Transcription timeout"
        }
    except Exception as e:
        logger.error(f"❌ whisper.cpp error: {e}")
        return {
            "text": "",
            "language": language,
            "success": False,
            "error": str(e)
        }


def get_backend_info() -> Dict:
    """
    Get information about current STT backend.
    
    Returns:
        dict with backend details
    """
    return {
        "initialized": _backend_initialized,
        "backend": "whisper.cpp" if _backend_initialized else None,
        "binary_path": str(_whisper_cpp_path) if _whisper_cpp_path else None,
        "model_path": str(_whisper_model_path) if _whisper_model_path else None,
        "model_name": _whisper_model_path.name if _whisper_model_path else None
    }


# Auto-initialize on import if env var is set
if os.getenv("OFFLINE_STT_ENABLED", "").lower() in ("true", "1", "yes"):
    initialize_stt()
