# Project Aria - GTI AI Copilot

AI companion for your VW GTI MK6 with holographic avatar and intelligent audio.

## Features

- 🤖 **Dual Personalities**: JOI (Blade Runner-inspired) or Aria (car copilot)
- 🗣️ **Voice**: ElevenLabs premium TTS
- 🧠 **LLM**: Local via LM Studio
- 🚗 **OBD-II**: Real-time car data
- 🎛️ **Auto EQ**: Spotify-aware DSP that adjusts EQ per song genre
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
├── aria.py                        # Main AI copilot (console + WebSocket)
├── auto_eq.py                     # 🎛️ Spotify Auto EQ (monitors playback)
├── live_audio_analyzer.py         # 🎧 Real-time system audio classifier
├── test_eq.py                     # Manual EQ preset tester
├── test_ml_classifier.py          # ML classifier test suite
├── config.py                      # Configuration
│
├── core/
│   ├── personality.py             # JOI/Aria personalities
│   ├── voice.py                   # ElevenLabs TTS
│   ├── obd_integration.py         # OBD-II connection
│   ├── state_manager.py           # Vehicle state detection (DRIVING/PARKED/GARAGE)
│   ├── response_validator.py      # DRIVING mode response enforcement
│   ├── audio_intelligence.py      # 🎛️ Genre→EQ mapping engine
│   └── genre_classifier.py        # 🤖 ML genre classifier (GTZAN-trained)
│
├── models/
│   └── genre_classifier_rf.pkl    # Trained Random Forest model (86% accuracy)
│
├── docs/
│   └── ARIA_DRIVING_CONTRACT.md   # Complete operational state specification
│
├── music_dataset/                 # 🎵 Training data & track database
│   ├── track_genre_clusters.csv   # 1,449 Spotify tracks with genres
│   ├── cleaned_track_metadata_with_genres_encoded.csv
│   └── Data/                      # GTZAN dataset (10 genres × 100 tracks)
│       ├── features_30_sec.csv    # 1,000 samples - full track features
│       └── features_3_sec.csv     # 9,990 samples - 3-second segments
│
├── queue/                         # Audio files (auto-created)
├── logs/                          # Logs (auto-created)
├── state/                         # Spotify tokens, history
│
├── start.bat                      # Quick start script
├── setup.bat                      # Windows setup
└── test_obd.bat                   # OBD test script
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

## 🎛️ Audio Intelligence (Auto EQ)

Automatically adjusts EQ based on what's playing on Spotify. Uses a **3-tier detection system** with ML fallback for unknown tracks.

### 🤖 ML Genre Classifier (GTZAN-Trained)

We trained a **Random Forest classifier** on the [GTZAN dataset](http://marsyas.info/downloads/datasets.html) - the "MNIST of music" - achieving **86% accuracy** across 10 genres.

**Training Data:**
| Dataset | Samples | Description |
|---------|---------|-------------|
| GTZAN 30-sec | 1,000 | Full 30-second clips (100 per genre) |
| GTZAN 3-sec | 9,990 | 3-second segments (10× more training data) |
| Spotify tracks | 1,449 | Your music library with genre tags |

**Audio Features Extracted (58 total):**
- Chroma STFT (harmonic content)
- Spectral centroid, bandwidth, rolloff (brightness/timbre)
- MFCCs 1-20 (timbral texture) - most important!
- Zero crossing rate (percussiveness)
- Tempo (BPM)

**Supported Genres:**
`blues` `classical` `country` `disco` `hiphop` `jazz` `metal` `pop` `reggae` `rock`

### Detection Pipeline

```
🎵 Track plays on Spotify
    │
    ├─→ 1️⃣ Spotify API genres (instant, 100% confidence)
    │       "symphonic metal" → metal EQ
    │
    ├─→ 2️⃣ Local database lookup (1,449 tracks)
    │       Track name/artist match → stored genre
    │
    └─→ 3️⃣ ML Classification (fallback for unknown tracks)
            Downloads 30-sec preview → Extract features → Predict genre
            "ML:metal (64%)" → metal EQ
```

### Setup

1. **Install Equalizer APO**: https://sourceforge.net/projects/equalizerapo/
2. **Configure Spotify** in `config.py`:
   ```python
   SPOTIFY_CLIENT_ID = "your_client_id"
   SPOTIFY_CLIENT_SECRET = "your_secret"
   ```
3. **Run Auto EQ**:
   ```cmd
   python auto_eq.py              # Full mode with ML fallback
   python auto_eq.py --driving    # Driving mode (short phrases, 60s cooldown)
   python auto_eq.py --no-voice   # Silent mode
   python auto_eq.py --no-ml      # Disable ML fallback (faster)
   ```

### Live Audio Analyzer (No Spotify Required)

For YouTube, local files, or any system audio:

```cmd
python live_audio_analyzer.py
```

Captures system audio via WASAPI loopback, extracts features in real-time, and applies EQ based on ML classification.

### EQ Presets (19 Total)

| Preset | Genres | Character |
|--------|--------|-----------|
| `rock` | rock, classic rock, hard rock, grunge, aor | Punchy mids, clear highs |
| `metal` | metal, thrash, death metal, nu metal | Scooped mids, crispy highs |
| `electronic` | techno, synthwave, deep house | Balanced electronic |
| `edm` | dubstep, hardstyle, trance, big room | Sub bass + bright highs 🎪 |
| `phonk` | phonk, drift phonk, brazilian phonk | **Heavy bass** + crispy highs 🔊 |
| `lofi` | lo-fi, chillhop, vaporwave | Warm, rolled-off highs 😌 |
| `hip_hop` | hip hop, rap, trap, drill | Bass-forward |
| `latin` | reggaeton, salsa, bachata, urbano | Rhythmic bass |
| `classical` | classical, orchestra, opera | Pure, flat response |
| `jazz` | jazz, blues, smooth jazz | Warm mids |
| `pop` | pop, dance pop, k-pop | Balanced, radio-friendly |
| `acoustic` | folk, indie folk, singer-songwriter | Natural, organic |
| `country` | country, americana, bluegrass | Twangy presence |

### Retrain the Model

If you add more training data:

```cmd
# Delete existing model and retrain
del models\genre_classifier_rf.pkl
python -m core.genre_classifier
```

### Manual Testing

```cmd
python test_ml_classifier.py    # Full test suite
python test_eq.py               # Interactive preset selector
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
- **OBD-II**: Bluetooth adapter paired to Windows (optional)
- **ffmpeg**: For audio playback (included in `ffmpeg/bin/`)
- **Equalizer APO**: For Auto EQ feature (Windows audio DSP)
- **Spotify**: Developer app credentials for Auto EQ

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
