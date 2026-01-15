# Persona Routing & Voice System

## Overview

Project Aria supports **per-turn persona routing**, allowing users to address specific personas (Nova or Aria) in individual messages without changing their default personality setting. The system also includes **Spanglish-friendly language detection** and **persona-aware TTS routing** for multilingual voice interactions.

## Per-Turn Persona Addressing

### How It Works

Users can prefix their message with a persona name to route that specific turn to a particular personality:

```
Nova, what's the weather like today?
Aria, check the coolant temperature
```

The prefix is detected, stripped from the message, and that turn is routed to the requested persona. **The default personality remains unchanged** unless an explicit switch command is used.

### Prefix Detection

- **Format:** `"Nova,"` or `"Aria:"` (case-insensitive)
- **Position:** Only at the start of the message (prevents false positives)
- **Stripping:** The prefix and punctuation are removed before sending to LLM

Examples:
```python
"Nova, explain quantum mechanics"  → persona="nova", text="explain quantum mechanics"
"Aria: what's the RPM?"           → persona="aria", text="what's the RPM?"
"Tell me about Nova"              → persona=None (uses default)
```

### Explicit Personality Switch

To change the **default personality** for the session:

**Console mode:**
```
/nova    # Switch to Nova as default
/aria    # Switch to Aria as default
```

**Avatar mode (WebSocket):**
Click the personality buttons in the UI, or send a command message:
```json
{
  "type": "command",
  "command": "set_personality",
  "value": "nova"
}
```

## Language Detection

The system automatically detects the language of each message using a lightweight heuristic that supports **Spanglish** (mixed Spanish/English).

### Detection Logic

- Counts Spanish indicators (accented characters, common Spanish words)
- If >30% of words contain Spanish indicators, classifies as Spanish
- Otherwise defaults to English

Examples:
```python
"What is the coolant temperature?"        → "en"
"¿Qué temperatura tiene el refrigerante?" → "es"
"¿Qué es el coolant temperature?"         → "es" (Spanglish, leans Spanish)
"The temperature está high"               → "en" (Spanglish, leans English)
```

For production use, consider integrating the `langdetect` library for more accurate detection.

## Voice Configuration

### PERSONA_VOICE_MAP

Configure voice IDs for each persona and language in `config.py`:

```python
PERSONA_VOICE_MAP = {
    "aria": {
        "en": "your_elevenlabs_voice_id_here",  # Aria English
        "es": "your_elevenlabs_voice_id_here"   # Aria Spanish
    },
    "nova": {
        "en": "v8DWAeuEGQSfwxqdH9t2",  # Nova English (example)
        "es": "your_elevenlabs_voice_id_here"   # Nova Spanish
    }
}
```

### TTS Backend Selection

Set the preferred TTS backend via environment variable:

```bash
export NOVA_TTS_BACKEND=auto        # Default: auto-select
export NOVA_TTS_BACKEND=elevenlabs  # Prefer ElevenLabs
export NOVA_TTS_BACKEND=coqui       # Prefer Coqui TTS (offline)
export NOVA_TTS_BACKEND=pyttsx3     # Prefer pyttsx3 (Windows fallback)
```

**Auto-selection logic:**
1. If `elevenlabs` backend and voice ID configured → use ElevenLabs
2. Else if offline TTS available → use Coqui or pyttsx3
3. Else → error

### Offline TTS

For privacy-first or offline deployments, use Coqui TTS or pyttsx3:

```bash
# Enable offline TTS
export OFFLINE_TTS_ENABLED=true
export OFFLINE_TTS_BACKEND=coqui  # or pyttsx3

# Optional: Specify Coqui model
export COQUI_MODEL_NAME=tts_models/en/ljspeech/tacotron2-DDC
```

See `docs/deployment/OFFLINE_TTS_STT.md` for setup instructions.

## WebSocket Message Format

### Response Message (with persona metadata)

```json
{
  "type": "response",
  "persona": "nova",
  "text": "The weather is sunny with a high of 75°F.",
  "ui": {
    "theme": "nova",
    "accent": "#7b2cbf",
    "glow": "#00d4ff",
    "gradient": ["#00d4ff", "#7b2cbf"]
  },
  "voice": {
    "audio_path": "/tts/abc123.wav",
    "backend": "elevenlabs",
    "voice_id": "v8DWAeuEGQSfwxqdH9t2",
    "lang": "en"
  }
}
```

### Query Message

```json
{
  "type": "query",
  "text": "Nova, what's the temperature?"
}
```

The server will:
1. Detect `"Nova,"` prefix → route to Nova persona
2. Detect language → `"en"`
3. Generate response using Nova's personality and English prompts
4. Generate voice using Nova's English voice ID
5. Return response with persona metadata

## Frontend Integration

### Applying Persona UI

The frontend receives `ui` metadata in response messages and updates the avatar styling:

```javascript
function applyPersonaUI(persona, uiConfig) {
    if (persona === 'nova') {
        // Purple/cyan gradient
        avatarGlow.style.background = 'radial-gradient(circle, rgba(123, 44, 191, 0.3) 0%, transparent 70%)';
        avatarElement.style.background = 'linear-gradient(135deg, #00d4ff 0%, #7b2cbf 100%)';
    } else if (persona === 'aria') {
        // Cyan/green gradient
        avatarGlow.style.background = 'radial-gradient(circle, rgba(0, 255, 136, 0.3) 0%, transparent 70%)';
        avatarElement.style.background = 'linear-gradient(135deg, #00D1FF 0%, #00ff88 100%)';
    }
}
```

### Playing Audio

The frontend fetches and plays audio from the `/tts/<file>` endpoint:

```javascript
function playAudio(audioPath) {
    const audio = new Audio(`http://localhost:5002${audioPath}`);
    audio.play().catch(err => console.error('Audio playback failed:', err));
}
```

**Note:** The HTTP server runs on port 5002 (WebSocket on 5001).

## Driving Contract & Persona Routing

The **DRIVING mode response validator** applies **regardless of which persona is active**. Even if a user addresses Nova during DRIVING mode, the response will be constrained to:

- Maximum 150 characters
- Format: `[Metric] → [Interpretation] → [Action]`
- No questions, no emotional language
- Essential information only

Example:
```
User (while driving): "Nova, what's the coolant temp?"
Nova: "Coolant: 92°C → Normal → OK"
```

This ensures driver safety is maintained across all personas.

## Testing

Run persona routing tests:

```bash
python tests/test_persona_routing.py
```

Tests cover:
- Prefix detection (Nova, Aria)
- Language detection (English, Spanish, Spanglish)
- Persona normalization
- Per-turn routing isolation (default unchanged)

## Troubleshooting

### TTS not working

1. Check `PERSONA_VOICE_MAP` in `config.py`
2. Verify ElevenLabs API key: `echo $ELEVENLABS_KEY`
3. Check backend preference: `echo $NOVA_TTS_BACKEND`
4. Enable debug logging to see TTS router decisions

### Language detection incorrect

The heuristic is simple. For production:
- Install `langdetect`: `pip install langdetect`
- Update `core/personality.py` to use langdetect library

### Frontend not switching persona UI

1. Check browser console for WebSocket messages
2. Verify `ui` metadata is present in response
3. Check `applyPersonaUI()` is being called

### Per-turn routing not working

1. Verify prefix format: `"Nova,"` or `"Aria:"` at start
2. Check console logs for routing messages
3. Test with explicit examples: `"Nova, hello"` vs `"Tell Nova hello"`

## Migration from JOI

The **JOI persona has been renamed to Nova**. If you have existing code or config referencing `"joi"`:

1. Update `config.py`: `DEFAULT_PERSONALITY = "nova"`
2. Update any scripts using `--personality joi` → `--personality nova`
3. Console commands: `/joi` → `/nova`
4. No data migration needed—this is a naming change only

## Future Enhancements

- **STT Integration:** Whisper-based speech input with language auto-detection
- **Voice Cloning:** Per-persona custom voices via Coqui or ElevenLabs
- **Multi-turn Context:** Remember which persona was last addressed
- **Persona-specific Memory:** Separate conversation histories per persona
