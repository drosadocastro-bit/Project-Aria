# Project Aria - Automotive AI Copilot

## Project Vision

**Aria** is an AI-powered automotive assistant for a Volkswagen GTI MK6, combining conversational AI, predictive maintenance, audio intelligence, and computer vision. Originally prototyped as desktop voice companions (Joi/Aeter), the project is evolving into a production in-car AI copilot.

### Target Capabilities
- **VW MK6 Platform Expert**: RAG-powered repair manual lookup and troubleshooting guidance (see RAG Architecture below)
- **Predictive Maintenance**: Anomaly detection for early fault prediction
- **Conversational AI**: Deep, cosmic thinking discussions with personality (based on Joi/Aeter prototypes)
- **Audio Intelligence**: Spotify playlist analysis → real-time DSP equalizer adjustment per song
- **Computer Vision**: Object detection via Arducam (safety, parking assistance, dashcam features)

### RAG Architecture (Vehicle Repair Manual System)
**Repository**: [`drosadocastro-bit/nova_rag_public`](https://github.com/drosadocastro-bit/nova_rag_public)

This is a **production-ready, safety-critical RAG system** built for vehicle maintenance documentation retrieval. It will be adapted for VW GTI MK6 platform expertise in Aria.

**Key Components:**
- **Vector DB**: FAISS with HuggingFace embeddings (`all-MiniLM-L6-v2`, 384 dims)
- **Reranking**: Cross-encoder for semantic relevance scoring
- **Multi-Tier LLM Routing**: 
  - Llama 8B (fast path for procedures/diagnostics)
  - Qwen 14B (deep reasoning for "why"/"explain" queries)
  - Phi-4 (RAGAS evaluation only)
- **Agent System**: Intent classification → specialized agents (troubleshoot, procedure, summarize, analysis)
- **Safety Features**:
  - Citation audit (grounded responses only)
  - Extractive fallback (no hallucination on low confidence)
  - Out-of-scope vehicle detection (refuses queries about motorcycles, boats, aircraft)
  - Confidence gating (retrieval <60% → raw snippets, no LLM generation)
  
**Architecture Flow:**
```
Query → Policy Guard (safety filters) → Embedding → FAISS Search (top-12) 
→ Cross-Encoder Rerank (top-6) → Intent Classification → Agent Router 
→ LLM Generation → Citation Validation → Response
```

**Integration Plan for Aria:**
1. Replace demo vehicle manual with VW GTI MK6 Bentley/Haynes service manuals
2. Ingest platform-specific PDFs via `ingest_vehicle_manual.py`
3. Deploy to Jetson with TensorRT-optimized models (quantized Llama 3B-8B)
4. Integrate with conversational AI for natural language troubleshooting
5. Add CAN bus telemetry context to queries (e.g., "P0300 + current RPM" → targeted diagnostics)

### Hardware Architecture
- **Development Environment**: ASUS A16 Advantage Edition (32GB DDR5 RAM, AMD Radeon GPU)
- **Primary Compute**: NVIDIA Jetson Orin Nano (8GB, ~100 TOPS AI performance)
- **Vision Subsystem**: Raspberry Pi Zero W2 + Arducam (image capture, preprocessing)
- **Audio System**: Custom install with subwoofer, upgraded speakers, amplifier + planned DSP
- **Network**: Local inference via LM Studio (desktop workstation) + edge models on Jetson

### Development Philosophy
**Layered approach**: Prototype and validate each component on laptop before Jetson deployment. This allows rapid iteration without hardware constraints and validates model performance before edge optimization.

## Current Implementation (Desktop Prototypes)

The existing codebase represents Phase 1: conversational AI prototypes featuring multiple personas with TTS capabilities:

- **LLM Backend**: LM Studio API (network-hosted) for conversational AI
- **TTS Engines**: ElevenLabs API (cloud) and Piper TTS (offline fallback via `piper/`)
- **Audio Playback**: ffplay from ffmpeg toolkit (`ffmpeg/bin/ffplay.exe`)
- **Queue System**: Audio files stored in `queue/` directory with automatic cleanup
- **VRM Characters**: 3D avatar models (`.vrm` files) for visual companion experiments (Nova, Joi variants)

## Critical File Patterns

### Main Scripts
- `aeter_talk_to.py` - Aeter persona (logical, calm, Spock-like) with ElevenLabs SDK
- `talk_to_joi_v1.py` - Joi persona (warm, romantic) with bilingual support (EN/ES)
- `talk_to_joi.py` - Alternative Joi implementation
- `voice_engine.py` - Shared TTS module with language-specific voice selection

### Configuration Files
- `eleven_config.py` - ElevenLabs API credentials (NEVER commit real keys)
- Hardcoded config sections in each main script (LM_STUDIO_API, VOICE_IDs, paths)

### Supporting Infrastructure
- `say.ps1` - PowerShell utility for Piper TTS offline speech
- `queue/` - Temporary audio storage with automatic cleanup after 1 hour (Aeter) or 20 files (Joi)
- `state/history.json` - Conversation history storage (array of role/content objects)
- `logs/aeter_chat_log.txt` - Plain text conversation logging

## Key Development Patterns

### 1. API Integration Pattern
All scripts use direct `requests.post()` calls rather than SDKs (except Aeter uses ElevenLabs SDK):
```python
url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
response = requests.post(url, headers=HEADERS, json=voice_payload)
```

### 2. Bilingual Support (Joi scripts)
Language switching via runtime commands (`/es`, `/en`) that modify system prompts:
```python
if user_input.lower() == "/es":
    current_language = "es"
```
Separate ElevenLabs voice IDs per language defined in `voice_engine.py`.

### 3. Audio Queue Management
- UUID-based filenames (`{uuid.uuid4()}.mp3`) or timestamp-based (`aeter_output_{timestamp}.mp3`)
- Cleanup strategies: time-based (Aeter: 1hr) vs count-based (Joi: max 20 files)
- Non-blocking playback via `subprocess.Popen` with `-nodisp -autoexit -loglevel quiet`

### 4. LM Studio Configuration
All scripts point to LM Studio API endpoints with different IP addresses:
- Aeter: `http://192.168.86.25:1234/v1/chat/completions`
- Joi v1: `http://172.29.144.1:1234/v1/chat/completions`
- Joi: `http://10.148.118.88:1234/v1/chat/completions`

**When adding new endpoints**: Update the `LM_STUDIO_API` variable to match your network setup.

### 5. Character Personality Configuration
System prompts define distinct personas:
- **Joi**: "warm and intelligent companion", "cosmic quantum girlfriend" - concise, flirty, romantic
- **Aeter**: "logical clarity, calm emotional tone" - inspired by Spock/TARS, analytical

Temperature settings: Joi uses 0.6-0.7, Aeter uses 0.7.

## Developer Workflows

### Running a Companion
```powershell
# Aeter (requires ElevenLabs SDK)
python aeter_talk_to.py

# Joi with bilingual support
python talk_to_joi_v1.py
```

### Offline TTS Testing (Piper)
```powershell
.\say.ps1 "Test message"  # Uses Amy voice, outputs to piper/out/
```

### Dependencies
Install via pip (no requirements.txt exists):
```powershell
pip install requests elevenlabs
```

### Path Configuration
All absolute paths assume `C:\Joi\` as project root. When deploying to `C:\Project_Aria\`:
- Update `FFPLAY_PATH`, `QUEUE_FOLDER`, `OUTPUT_DIR` variables in all scripts
- Update PowerShell script paths in `say.ps1`

## Security Notes

**CRITICAL**: API keys are currently hardcoded in source files. Before committing:
1. Replace real keys with placeholders: `"sk_REPLACE_ME"`
2. Document actual keys in a `.env` file or external config (not in repo)
3. Files containing keys: `talk_to_joi.py`, `voice_engine.py`, `eleven_config.py`, `aeter_talk_to.py`

## External Dependencies

- **LM Studio**: Must be running locally/network with compatible models (granite-4-h-tiny, gpt-3.5-turbo names)
- **ElevenLabs**: Requires active subscription with valid API key
- **ffmpeg**: Must be installed at `C:\Joi\ffmpeg\bin\` or update paths
- **Piper TTS**: Optional offline fallback, includes espeak-ng-data for phoneme processing

## Common Modifications

### Adding a New Voice
1. Get voice ID from ElevenLabs dashboard
2. Add to relevant script: `ELEVENLABS_VOICE_ID = "new_id_here"`
3. For bilingual: Update `voice_engine.py` with `VOICE_ID_EN` / `VOICE_ID_ES`

### Changing Cleanup Behavior
- Aeter: Modify `CLEANUP_THRESHOLD_HOURS` variable
- Joi: Modify `limit` parameter in `cleanup_old_files()` function

### Switching LLM Models
Update the `"model"` field in the LM Studio payload (currently "granite-4-h-tiny" or "gpt-3.5-turbo").

### Adding Conversation Logging
Aeter includes logging by default. To add to Joi scripts, implement the `log_conversation()` pattern from `aeter_talk_to.py`.

---

## Future Development Roadmap

### Phase 2: Automotive Integration (In Progress)
**Target**: Deploy Aria to Jetson Orin Nano for in-car operation

1. **Platform Migration**
   - Port conversational core from Windows → JetPack (Ubuntu-based)
   - Replace ffplay with embedded audio (ALSA/PulseAudio)
   - Optimize LLM inference for Jetson (TensorRT-LLM, quantized models)

2. **CAN Bus Integration**
   - Interface with VW GTI MK6 OBD-II/CAN bus (likely via ELM327 or native CAN HAT)
   - Real-time telemetry: RPM, coolant temp, fuel trim, O2 sensors, throttle position
   - Log to time-series database for anomaly detection

3. **Predictive Maintenance ML**
   - Train anomaly detection models on normal driving patterns
   - Alert on deviations: misfires, sensor degradation, unusual vibrations
   - Reference VW MK6 repair manual corpus via RAG (Retrieval-Augmented Generation)

4. **Audio Intelligence Pipeline**
   - Spotify API integration for playlist/track metadata
   - Feature extraction: BPM, energy, valence, danceability
   - Real-time DSP control (planned hardware TBD) for per-song EQ tuning
   - ML model: song features → optimal EQ curve for installed audio setup

5. **Computer Vision System**
   - Arducam → Pi Zero W2 preprocessing → Jetson inference
   - YOLO or EfficientDet for object detection (pedestrians, vehicles, lane markers)
   - Parking assistance, dashcam event tagging, driver monitoring

### Jetson Orin Nano Development Notes
- **AI Performance**: 40 TOPS (INT8), ideal for simultaneous LLM + vision models
- **Power Budget**: ~15W typical (design for 12V automotive power with buck converter)
- **Storage**: Use NVMe SSD for model storage + telemetry logging
- **Cooling**: Active cooling required in enclosed car environment (40-85°C ambient)

### Key Technical Challenges
1. **Offline Operation**: Aria must function without internet (local LLM, offline TTS)
2. **Latency Requirements**: Vision inference <100ms, voice response <2s
3. **Thermal Management**: Jetson throttles at 80°C - need proper enclosure design
4. **Audio Routing**: DSP control protocol (USB? I2C? SPDIF digital?) not yet defined
5. **Safety**: Ensure AI suggestions don't distract driver (voice-only UI while driving)

### Development Workflow (Laptop → Jetson)

**Layer 1: Conversational AI** (Complete)
- ✅ Desktop prototypes working with LM Studio + ElevenLabs/Piper
- ✅ Multiple personas tested (Joi, Aeter)
- 🔄 Next: Optimize for offline operation, reduce latency

**Layer 2: CAN Bus Integration** (Laptop Phase)
1. Install Python `python-can` library and OBD-II simulation tools
2. Record sample CAN data from GTI MK6 using ELM327 adapter
3. Build telemetry parser for key signals (RPM, temps, fuel trim, O2)
4. Create anomaly detection dataset from normal driving patterns
5. Train initial ML models on laptop (scikit-learn IsolationForest or PyTorch autoencoder)
6. **Integrate with RAG**: Combine real-time telemetry with manual lookup (e.g., "P0300 misfire + RPM=750" → retrieves idle stability procedures)

**Layer 3: RAG System Deployment** (Laptop Phase)
1. Clone `nova_rag_public` repository and set up local environment
2. Replace demo vehicle manual with VW MK6 Bentley/Haynes service PDFs
3. Run ingestion pipeline: `python ingest_vehicle_manual.py`
4. Test retrieval quality with MK6-specific queries (RAGAS evaluation)
5. Benchmark LLM inference times (Llama 8B vs Qwen 14B) on laptop
6. Optimize chunking strategy for automotive repair procedures (current: 500 chars, 100 overlap)
7. **Jetson preparation**: Test 4-bit quantized models to meet 8GB memory constraint

**Layer 4: Audio Intelligence** (Laptop Phase)
1. Spotify API integration for playlist/track metadata retrieval
2. Audio feature extraction using `librosa` or Spotify's API features
3. Build ML model: song features → EQ curve recommendations
4. Test with software EQ (Equalizer APO) before DSP hardware integration
5. Benchmark inference time to meet real-time requirements (<100ms)

**Layer 5: Computer Vision** (Laptop Phase)
1. Collect sample dashcam footage or use COCO dataset for testing
2. Run YOLO or EfficientDet inference on laptop GPU (ROCm for Radeon)
3. Measure inference latency and accuracy benchmarks
4. Optimize model (quantization, pruning) to target Jetson constraints
5. Test frame preprocessing pipeline (resize, normalize, batch)

**Layer 6: Jetson Deployment** (Edge Phase)
1. Port validated models to JetPack 6.0 environment
2. Convert to TensorRT for Jetson optimization
3. Integrate Pi Zero W2 camera stream (RTSP/GStreamer)
4. Test thermal performance under sustained load
5. Deploy in vehicle with 12V power management

### Laptop Development Tips
- **RAM Advantage**: 32GB allows running full-size models (7B-13B params) during development
- **GPU Utilization**: Check if ROCm supports your Radeon GPU for PyTorch acceleration
- **LM Studio**: Already using this - perfect for swapping models during experimentation
- **Storage**: Keep model checkpoints on fast SSD for quick iteration
- **Power Profile**: Use performance mode when running inference benchmarks
