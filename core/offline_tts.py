"""
Offline TTS engine with Coqui TTS (preferred) and pyttsx3 (Windows fallback)
Generates WAV files asynchronously for WebSocket responsiveness
"""

import os
import uuid
import logging
from pathlib import Path
from typing import Optional, Dict
from concurrent.futures import ThreadPoolExecutor
import asyncio

logger = logging.getLogger(__name__)

# Thread pool for async TTS generation
_tts_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tts")

# TTS backend state
_coqui_tts = None
_pyttsx3_engine = None
_backend_initialized = False
_current_backend = None


def _init_coqui():
    """Initialize Coqui TTS if available."""
    global _coqui_tts, _current_backend
    
    try:
        from TTS.api import TTS
        
        # Get model path from environment or use default
        model_name = os.getenv("COQUI_MODEL_NAME", "tts_models/en/ljspeech/tacotron2-DDC")
        model_path = os.getenv("COQUI_MODEL_PATH")
        
        logger.info(f"Initializing Coqui TTS with model: {model_name}")
        
        if model_path and os.path.exists(model_path):
            _coqui_tts = TTS(model_path=model_path)
            logger.info(f"✅ Coqui TTS loaded from: {model_path}")
        else:
            _coqui_tts = TTS(model_name=model_name)
            logger.info(f"✅ Coqui TTS initialized with model: {model_name}")
        
        _current_backend = "coqui"
        return True
        
    except ImportError:
        logger.warning("⚠️ Coqui TTS not installed (pip install TTS)")
        logger.info("   Falling back to pyttsx3")
        return False
    except Exception as e:
        logger.error(f"❌ Coqui TTS initialization failed: {e}")
        logger.info(f"   See docs/deployment/OFFLINE_TTS_STT.md for setup instructions")
        return False


def _init_pyttsx3():
    """Initialize pyttsx3 fallback engine (Windows)."""
    global _pyttsx3_engine, _current_backend
    
    try:
        import pyttsx3
        
        _pyttsx3_engine = pyttsx3.init()
        
        # Configure voice settings
        rate = int(os.getenv("PYTTSX3_RATE", "150"))
        volume = float(os.getenv("PYTTSX3_VOLUME", "0.9"))
        
        _pyttsx3_engine.setProperty('rate', rate)
        _pyttsx3_engine.setProperty('volume', volume)
        
        # Try to set a female voice if available
        voices = _pyttsx3_engine.getProperty('voices')
        for voice in voices:
            if 'female' in voice.name.lower() or 'zira' in voice.name.lower():
                _pyttsx3_engine.setProperty('voice', voice.id)
                logger.info(f"✅ pyttsx3 initialized with voice: {voice.name}")
                break
        else:
            logger.info(f"✅ pyttsx3 initialized with default voice")
        
        _current_backend = "pyttsx3"
        return True
        
    except ImportError:
        logger.error("❌ pyttsx3 not installed (pip install pyttsx3)")
        return False
    except Exception as e:
        logger.error(f"❌ pyttsx3 initialization failed: {e}")
        return False


def initialize_tts(force_backend: Optional[str] = None):
    """
    Initialize TTS backend (Coqui preferred, pyttsx3 fallback).
    
    Args:
        force_backend: Force specific backend ("coqui" or "pyttsx3")
    
    Returns:
        bool: True if initialization successful
    """
    global _backend_initialized, _current_backend
    
    if _backend_initialized and not force_backend:
        return True
    
    # Check environment variable for backend preference
    preferred_backend = force_backend or os.getenv("OFFLINE_TTS_BACKEND", "auto")
    
    if preferred_backend == "coqui":
        success = _init_coqui()
        if not success:
            logger.error("❌ Coqui TTS required but initialization failed")
            return False
    
    elif preferred_backend == "pyttsx3":
        success = _init_pyttsx3()
        if not success:
            logger.error("❌ pyttsx3 required but initialization failed")
            return False
    
    else:  # auto
        # Try Coqui first, fall back to pyttsx3
        if not _init_coqui():
            if not _init_pyttsx3():
                logger.error("❌ No TTS backend available")
                logger.error("   Install Coqui TTS: pip install TTS")
                logger.error("   OR install pyttsx3: pip install pyttsx3")
                logger.error("   See: docs/deployment/OFFLINE_TTS_STT.md")
                return False
    
    _backend_initialized = True
    logger.info(f"🎙️ TTS backend ready: {_current_backend}")
    return True


def _generate_coqui(text: str, output_path: Path) -> Dict:
    """Generate speech using Coqui TTS."""
    global _coqui_tts
    
    if _coqui_tts is None:
        raise RuntimeError("Coqui TTS not initialized")
    
    try:
        _coqui_tts.tts_to_file(text=text, file_path=str(output_path))
        return {
            "audio_path": str(output_path),
            "backend": "coqui",
            "success": True
        }
    except Exception as e:
        logger.error(f"Coqui TTS generation failed: {e}")
        raise


def _generate_pyttsx3(text: str, output_path: Path) -> Dict:
    """Generate speech using pyttsx3."""
    global _pyttsx3_engine
    
    if _pyttsx3_engine is None:
        raise RuntimeError("pyttsx3 not initialized")
    
    try:
        _pyttsx3_engine.save_to_file(text, str(output_path))
        _pyttsx3_engine.runAndWait()
        
        return {
            "audio_path": str(output_path),
            "backend": "pyttsx3",
            "success": True
        }
    except Exception as e:
        logger.error(f"pyttsx3 generation failed: {e}")
        raise


def _speak_sync(text: str, out_path: Optional[str] = None) -> Dict:
    """
    Synchronous TTS generation (called in thread pool).
    
    Args:
        text: Text to speak
        out_path: Optional custom output path
    
    Returns:
        dict with keys: audio_path, backend, success
    """
    global _current_backend
    
    # Ensure TTS is initialized
    if not _backend_initialized:
        initialize_tts()
    
    # Determine output path
    if out_path:
        output_path = Path(out_path)
    else:
        # Use static/tts/ directory with UUID filename
        static_tts_dir = Path(__file__).parent.parent / "static" / "tts"
        static_tts_dir.mkdir(parents=True, exist_ok=True)
        
        file_id = str(uuid.uuid4())
        output_path = static_tts_dir / f"{file_id}.wav"
    
    # Generate based on current backend
    if _current_backend == "coqui":
        return _generate_coqui(text, output_path)
    elif _current_backend == "pyttsx3":
        return _generate_pyttsx3(text, output_path)
    else:
        raise RuntimeError("No TTS backend available")


def speak(text: str, out_path: Optional[str] = None) -> Dict:
    """
    Generate speech from text (synchronous wrapper).
    For async usage in WebSocket, use speak_async().
    
    Args:
        text: Text to synthesize
        out_path: Optional custom output path (defaults to static/tts/<uuid>.wav)
    
    Returns:
        dict: {"audio_path": "<file>.wav", "backend": "coqui|pyttsx3", "success": True}
    """
    return _speak_sync(text, out_path)


async def speak_async(text: str, out_path: Optional[str] = None) -> Dict:
    """
    Generate speech from text asynchronously (for WebSocket responsiveness).
    
    Args:
        text: Text to synthesize
        out_path: Optional custom output path (defaults to static/tts/<uuid>.wav)
    
    Returns:
        dict: {"audio_path": "<file>.wav", "backend": "coqui|pyttsx3", "success": True}
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_tts_executor, _speak_sync, text, out_path)


def get_backend_info() -> Dict:
    """
    Get information about current TTS backend.
    
    Returns:
        dict with backend details
    """
    return {
        "initialized": _backend_initialized,
        "backend": _current_backend,
        "coqui_available": _coqui_tts is not None,
        "pyttsx3_available": _pyttsx3_engine is not None
    }


def cleanup_old_files(max_files: int = 20):
    """
    Clean up old TTS files from static/tts directory.
    
    Args:
        max_files: Maximum number of files to keep
    """
    static_tts_dir = Path(__file__).parent.parent / "static" / "tts"
    
    if not static_tts_dir.exists():
        return
    
    files = sorted(static_tts_dir.glob("*.wav"), key=os.path.getctime)
    
    while len(files) > max_files:
        file_to_delete = files[0]
        try:
            file_to_delete.unlink()
            logger.debug(f"Cleaned up old TTS file: {file_to_delete.name}")
        except Exception as e:
            logger.warning(f"Failed to delete {file_to_delete}: {e}")
        files = files[1:]


# Auto-initialize on import if env var is set
if os.getenv("OFFLINE_TTS_ENABLED", "").lower() in ("true", "1", "yes"):
    initialize_tts()
