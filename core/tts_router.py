"""
TTS Router - Routes persona + language to appropriate voice backend
Supports ElevenLabs (preferred), Coqui TTS, and pyttsx3 fallback
"""

import os
import logging
from pathlib import Path
from typing import Dict, Optional
import asyncio

logger = logging.getLogger(__name__)

# Import voice backends
try:
    from core.voice import generate_voice as elevenlabs_generate
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False
    logger.warning("ElevenLabs voice not available")

try:
    from core.offline_tts import speak as offline_speak, speak_async as offline_speak_async, initialize_tts
    OFFLINE_TTS_AVAILABLE = True
except ImportError:
    OFFLINE_TTS_AVAILABLE = False
    logger.warning("Offline TTS not available")


def get_voice_config(persona: str, lang: str) -> Dict:
    """
    Get voice configuration for persona + language combination.
    
    Args:
        persona: "nova" or "aria"
        lang: "en" or "es"
    
    Returns:
        dict with voice_id, backend preference, etc.
    """
    # Import config to get PERSONA_VOICE_MAP
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    
    try:
        from config import PERSONA_VOICE_MAP
    except (ImportError, AttributeError):
        # Fallback if PERSONA_VOICE_MAP not defined
        PERSONA_VOICE_MAP = {
            "nova": {"en": "", "es": ""},
            "aria": {"en": "", "es": ""}
        }
    
    voice_map = PERSONA_VOICE_MAP.get(persona, {})
    voice_id = voice_map.get(lang, "")
    
    # Get backend preference from environment
    backend_pref = os.getenv("NOVA_TTS_BACKEND", "auto")  # auto|elevenlabs|coqui|pyttsx3
    
    return {
        "voice_id": voice_id,
        "backend": backend_pref,
        "lang": lang,
        "persona": persona
    }


def _select_backend(config: Dict) -> str:
    """
    Select TTS backend based on configuration and availability.
    
    Args:
        config: Voice configuration dict
    
    Returns:
        Backend name: "elevenlabs", "coqui", or "pyttsx3"
    """
    backend_pref = config.get("backend", "auto")
    
    # If specific backend requested, try it
    if backend_pref == "elevenlabs" and ELEVENLABS_AVAILABLE:
        return "elevenlabs"
    elif backend_pref in ["coqui", "pyttsx3"] and OFFLINE_TTS_AVAILABLE:
        return backend_pref
    
    # Auto selection: prefer ElevenLabs if configured, else offline
    if backend_pref == "auto":
        # Check if ElevenLabs is configured (has API key and voice ID)
        if ELEVENLABS_AVAILABLE and config.get("voice_id"):
            try:
                from config import ELEVENLABS_API_KEY, USE_ELEVENLABS
                if USE_ELEVENLABS and ELEVENLABS_API_KEY and ELEVENLABS_API_KEY != "your_api_key_here":
                    return "elevenlabs"
            except ImportError:
                pass
        
        # Fall back to offline TTS
        if OFFLINE_TTS_AVAILABLE:
            return "offline"
    
    # Last resort
    if OFFLINE_TTS_AVAILABLE:
        return "offline"
    elif ELEVENLABS_AVAILABLE:
        return "elevenlabs"
    
    raise RuntimeError("No TTS backend available")


def speak_for_persona(text: str, persona: str, lang: str) -> Dict:
    """
    Generate speech for specific persona and language (synchronous).
    
    Args:
        text: Text to synthesize
        persona: "nova" or "aria"
        lang: "en" or "es"
    
    Returns:
        dict: {
            "audio_path": "/tts/file.wav",  # Relative URL for browser
            "backend": "elevenlabs|coqui|pyttsx3",
            "voice_id": "...",
            "lang": "en|es",
            "success": True
        }
    """
    config = get_voice_config(persona, lang)
    backend = _select_backend(config)
    
    logger.info(f"🎙️ TTS for {persona} ({lang}): backend={backend}")
    
    try:
        if backend == "elevenlabs":
            # Use ElevenLabs
            audio_path = elevenlabs_generate(text)
            if audio_path:
                # Return relative URL for browser
                filename = Path(audio_path).name
                return {
                    "audio_path": f"/tts/{filename}",
                    "backend": "elevenlabs",
                    "voice_id": config.get("voice_id", ""),
                    "lang": lang,
                    "success": True
                }
            else:
                # ElevenLabs failed, fall back
                logger.warning("ElevenLabs failed, falling back to offline TTS")
                if OFFLINE_TTS_AVAILABLE:
                    backend = "offline"
                else:
                    raise RuntimeError("TTS generation failed")
        
        if backend == "offline" or backend in ["coqui", "pyttsx3"]:
            # Use offline TTS
            result = offline_speak(text)
            if result.get("success"):
                # Convert absolute path to relative URL
                audio_path = Path(result["audio_path"])
                filename = audio_path.name
                
                return {
                    "audio_path": f"/tts/{filename}",
                    "backend": result.get("backend", "offline"),
                    "voice_id": "",
                    "lang": lang,
                    "success": True
                }
            else:
                raise RuntimeError(f"Offline TTS failed: {result.get('error', 'Unknown')}")
        
        raise RuntimeError(f"Unsupported backend: {backend}")
        
    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        return {
            "audio_path": "",
            "backend": backend,
            "voice_id": "",
            "lang": lang,
            "success": False,
            "error": str(e)
        }


async def speak_for_persona_async(text: str, persona: str, lang: str) -> Dict:
    """
    Generate speech for specific persona and language (asynchronous).
    For use in WebSocket handlers to avoid blocking.
    
    Args:
        text: Text to synthesize
        persona: "nova" or "aria"
        lang: "en" or "es"
    
    Returns:
        dict: Same as speak_for_persona()
    """
    config = get_voice_config(persona, lang)
    backend = _select_backend(config)
    
    logger.info(f"🎙️ Async TTS for {persona} ({lang}): backend={backend}")
    
    try:
        if backend == "elevenlabs":
            # ElevenLabs is synchronous but fast enough
            loop = asyncio.get_event_loop()
            audio_path = await loop.run_in_executor(None, elevenlabs_generate, text)
            
            if audio_path:
                filename = Path(audio_path).name
                return {
                    "audio_path": f"/tts/{filename}",
                    "backend": "elevenlabs",
                    "voice_id": config.get("voice_id", ""),
                    "lang": lang,
                    "success": True
                }
            else:
                # Fall back
                logger.warning("ElevenLabs failed, falling back to offline TTS")
                if OFFLINE_TTS_AVAILABLE:
                    backend = "offline"
                else:
                    raise RuntimeError("TTS generation failed")
        
        if backend == "offline" or backend in ["coqui", "pyttsx3"]:
            # Use async offline TTS
            result = await offline_speak_async(text)
            if result.get("success"):
                audio_path = Path(result["audio_path"])
                filename = audio_path.name
                
                return {
                    "audio_path": f"/tts/{filename}",
                    "backend": result.get("backend", "offline"),
                    "voice_id": "",
                    "lang": lang,
                    "success": True
                }
            else:
                raise RuntimeError(f"Offline TTS failed: {result.get('error', 'Unknown')}")
        
        raise RuntimeError(f"Unsupported backend: {backend}")
        
    except Exception as e:
        logger.error(f"Async TTS generation failed: {e}")
        return {
            "audio_path": "",
            "backend": backend,
            "voice_id": "",
            "lang": lang,
            "success": False,
            "error": str(e)
        }


def get_persona_ui_config(persona: str) -> Dict:
    """
    Get UI configuration for persona (theme colors, accent, etc.).
    
    Args:
        persona: "nova" or "aria"
    
    Returns:
        dict with UI settings
    """
    ui_configs = {
        "nova": {
            "theme": "nova",
            "accent": "#7b2cbf",  # Purple
            "glow": "#00d4ff",  # Cyan
            "gradient": ["#00d4ff", "#7b2cbf"]
        },
        "aria": {
            "theme": "aria",
            "accent": "#00D1FF",  # Bright cyan
            "glow": "#00ff88",  # Green
            "gradient": ["#00D1FF", "#00ff88"]
        }
    }
    
    return ui_configs.get(persona, ui_configs["nova"])
