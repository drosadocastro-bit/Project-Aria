# Offline TTS and STT Setup Guide

Complete guide for setting up offline text-to-speech (TTS) and speech-to-text (STT) capabilities in Project Aria.

## Overview

Project Aria supports **optional offline TTS/STT** for:
- **Privacy**: No API calls to cloud services
- **Latency**: Faster response in some cases
- **Cost**: No ElevenLabs API usage
- **Reliability**: Works without internet

**Default behavior**: ElevenLabs TTS remains the default. Offline is **opt-in only** via environment variables.

## Architecture

### TTS Backends
1. **Coqui TTS** (Preferred)
   - Neural TTS with high-quality voices
   - GPU-accelerated (CUDA/DirectML if available)
   - Multiple models and voices
   - ~200MB-2GB depending on model

2. **pyttsx3** (Windows Fallback)
   - Uses Windows SAPI5 voices (Zira, David, etc.)
   - Instant startup, no downloads
   - Lower quality than neural TTS
   - ~10KB memory footprint

### STT Backend
- **whisper.cpp**
  - OpenAI Whisper models optimized in C++
  - Fast CPU inference
  - Multiple model sizes: tiny(75MB) to large(2.9GB)
  - Recommended: small(466MB) or medium(1.5GB)

---

## Installation

### 1. Install Optional Dependencies

```bash
# Install offline TTS/STT packages
pip install -r requirements-offline.txt
```

This installs:
- `TTS` - Coqui TTS library
- `pyttsx3` - Windows system voice TTS
- `pydub` - Audio format handling

### 2. Download Models

#### Windows (PowerShell)
```powershell
# Run interactive model downloader
.\scripts\download_models.ps1
```

#### Linux/macOS (Bash)
```bash
# Make script executable
chmod +x scripts/download_models.sh

# Run interactive model downloader
./scripts/download_models.sh
```

#### Manual Download
If scripts fail, manually download:

**Whisper.cpp models**:
```bash
# Create model directory
mkdir -p ~/.aria/models

# Download small model (recommended)
curl -L -o ~/.aria/models/ggml-small.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin

# OR medium model (better accuracy, slower)
curl -L -o ~/.aria/models/ggml-medium.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin
```

**Coqui TTS models**:
Models auto-download on first use. To pre-cache:
```python
from TTS.api import TTS
TTS("tts_models/en/ljspeech/tacotron2-DDC")  # Downloads ~200MB
```

### 3. Build whisper.cpp

#### Windows
```powershell
# Requirements: Visual Studio 2022 with C++ tools

# Clone repository
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp

# Build with CMake
mkdir build
cd build
cmake ..
cmake --build . --config Release

# Binary will be at: build\bin\Release\main.exe
```

#### Linux/macOS
```bash
# Clone repository
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp

# Build
make

# Binary will be at: ./main
```

**Pre-built binaries**: Check [whisper.cpp releases](https://github.com/ggerganov/whisper.cpp/releases) for Windows builds.

---

## Configuration

### Environment Variables

Add to your shell profile or `.env` file:

```bash
# ========== Offline TTS ==========
export OFFLINE_TTS_ENABLED=true
export OFFLINE_TTS_BACKEND=auto  # auto|coqui|pyttsx3

# Coqui TTS settings
export COQUI_MODEL_NAME="tts_models/en/ljspeech/tacotron2-DDC"
# Or use custom model path:
# export COQUI_MODEL_PATH="/path/to/model"

# pyttsx3 settings (Windows fallback)
export PYTTSX3_RATE=150  # Words per minute
export PYTTSX3_VOLUME=0.9

# ========== Offline STT ==========
export OFFLINE_STT_ENABLED=true
export NOVA_OFFLINE_MODEL_DIR="$HOME/.aria/models"
export WHISPER_MODEL_PATH="$HOME/.aria/models/ggml-small.bin"
export WHISPER_CPP_PATH="$HOME/whisper.cpp/main"
```

### Windows PowerShell
```powershell
# Add to $PROFILE or set per-session
$env:OFFLINE_TTS_ENABLED = "true"
$env:OFFLINE_STT_ENABLED = "true"
$env:NOVA_OFFLINE_MODEL_DIR = "$env:USERPROFILE\.aria\models"
$env:WHISPER_MODEL_PATH = "$env:USERPROFILE\.aria\models\ggml-small.bin"
$env:WHISPER_CPP_PATH = "C:\whisper.cpp\build\bin\Release\main.exe"
```

### config.py
Alternatively, add to `config.py`:

```python
import os

# Offline TTS
os.environ['OFFLINE_TTS_ENABLED'] = 'true'
os.environ['OFFLINE_TTS_BACKEND'] = 'auto'  # auto|coqui|pyttsx3

# Offline STT
os.environ['OFFLINE_STT_ENABLED'] = 'true'
os.environ['WHISPER_MODEL_PATH'] = str(Path.home() / '.aria/models/ggml-small.bin')
os.environ['WHISPER_CPP_PATH'] = str(Path.home() / 'whisper.cpp/main')
```

---

## Usage

### TTS in Python

```python
from core.offline_tts import speak, speak_async, initialize_tts

# Initialize (optional - auto-initializes on first use)
initialize_tts()

# Synchronous TTS
result = speak("Hello, I am Aria")
# Returns: {"audio_path": "static/tts/<uuid>.wav", "backend": "coqui", "success": True}

# Async TTS (for WebSocket responsiveness)
import asyncio
result = await speak_async("Processing your request")

# Force specific backend
initialize_tts(force_backend="pyttsx3")
result = speak("Using Windows voice")
```

### STT in Python

```python
from core.offline_stt import transcribe, initialize_stt

# Initialize (optional)
initialize_stt()

# Transcribe audio file
result = transcribe("recorded_audio.wav", language="en")
# Returns: {
#   "text": "what is the tire pressure",
#   "language": "en",
#   "success": True,
#   "model": "ggml-small.bin"
# }
```

### REST API (/stt endpoint)

```bash
# Upload audio for transcription
curl -X POST http://localhost:5001/stt \
  -F "audio=@voice_input.wav" \
  -F "language=en"

# Response:
# {
#   "text": "show me engine diagnostics",
#   "language": "en",
#   "success": true
# }
```

### WebSocket Integration

The offline TTS automatically returns audio paths compatible with the browser avatar:

```javascript
// In joi_avatar.html or custom UI
const response = await fetch(`/tts/${filename}`);
const audio = new Audio(response.url);
audio.play();
```

---

## Model Selection Guide

### Whisper.cpp Models

| Model | Size | Speed | Accuracy | Use Case |
|-------|------|-------|----------|----------|
| tiny | 75MB | Fastest | Basic | Testing only |
| base | 142MB | Fast | Good | Quick prototyping |
| **small** | **466MB** | **Moderate** | **Very Good** | **Recommended** |
| medium | 1.5GB | Slower | Excellent | High accuracy needed |
| large | 2.9GB | Slowest | Best | Research/offline only |

**Recommendation**: Start with `small`. Upgrade to `medium` if accuracy is insufficient.

### Coqui TTS Models

| Model | Size | Quality | Languages | Speed |
|-------|------|---------|-----------|-------|
| ljspeech/tacotron2-DDC | ~200MB | Good | EN | Fast |
| vctk/vits | ~500MB | Excellent | EN (multi-voice) | Moderate |
| your_tts | ~2GB | Excellent | 16+ langs | Slower |

**Recommendation**: `ljspeech/tacotron2-DDC` for English, `your_tts` for multilingual.

---

## Performance Tips

### GPU Acceleration

**Coqui TTS** can use GPU:
```bash
# Install CUDA-enabled PyTorch (if you have NVIDIA GPU)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# TTS will automatically detect and use CUDA
```

**whisper.cpp** GPU support:
```bash
# Build with CUDA (Linux/Windows with CUDA toolkit)
cd whisper.cpp
make CUDA=1

# Or with CMake
cmake -DWHISPER_CUDA=ON ..
cmake --build . --config Release
```

### Model Caching

- **Coqui**: Models cached in `~/.local/share/tts/` (Linux) or `%LOCALAPPDATA%\tts\` (Windows)
- **Whisper**: Manually place `.bin` files in `NOVA_OFFLINE_MODEL_DIR`

### Memory Usage

| Component | Idle | Active | Peak |
|-----------|------|--------|------|
| pyttsx3 | ~10KB | ~50MB | ~50MB |
| Coqui small | ~500MB | ~1GB | ~1.5GB |
| whisper small | ~1GB | ~2GB | ~3GB |

**Tips**:
- Use pyttsx3 on resource-constrained systems
- Unload models between sessions with `del _coqui_tts` (advanced)
- Small models fine for GTI voice assistant use case

---

## Troubleshooting

### TTS Issues

**"Coqui TTS not installed"**
```bash
pip install TTS
# If fails, try:
pip install --upgrade pip setuptools wheel
pip install TTS
```

**"No TTS backend available"**
- Ensure at least one backend installed: `pip install TTS` OR `pip install pyttsx3`
- Check logs for initialization errors

**Coqui model download fails**
```python
# Manually download and specify path
export COQUI_MODEL_PATH="/path/to/downloaded/model"
```

**pyttsx3 "No module named 'win32com'"** (Windows)
```bash
pip install pywin32
```

### STT Issues

**"whisper.cpp binary not found"**
- Build whisper.cpp (see instructions above)
- Set `WHISPER_CPP_PATH` to binary location
- On Windows, ensure `.exe` extension: `main.exe`

**"Whisper model not found"**
- Download models using `download_models.sh/ps1`
- Set `WHISPER_MODEL_PATH` to `.bin` file
- Verify file exists: `ls $WHISPER_MODEL_PATH`

**Transcription timeout**
- Large audio files (>60s) may timeout
- Use smaller model (`ggml-small.bin` instead of `large`)
- Increase timeout in `offline_stt.py` if needed

**Poor transcription quality**
- Upgrade to `medium` or `large` model
- Ensure audio is clear (check with Audacity)
- Try different `language` parameter

### Performance Issues

**Slow TTS generation**
- Use GPU acceleration (see above)
- Switch to pyttsx3 for instant responses: `export OFFLINE_TTS_BACKEND=pyttsx3`
- Use smaller Coqui model

**High memory usage**
- Reduce model sizes
- Use cleanup: `from core.offline_tts import cleanup_old_files; cleanup_old_files()`
- Monitor with `htop` (Linux) or Task Manager (Windows)

---

## Jetson Orin Nano Deployment

Future phase for embedded deployment:

### TensorRT Conversion (Planned)

**Coqui TTS to TensorRT**:
```bash
# Export ONNX first
python -m TTS.utils.export_model --model_path model.pth --out_path model.onnx

# Convert to TensorRT (on Jetson)
trtexec --onnx=model.onnx --saveEngine=model.trt --fp16
```

**Whisper to TensorRT**:
- Use [whisper-tensorrt](https://github.com/NVIDIA/TensorRT/tree/main/demo/Whisper) pipeline
- Or [faster-whisper](https://github.com/guillaumekln/faster-whisper) with CTranslate2

### Optimizations for Jetson
- Use INT8 quantization for speed
- Enable DLA (Deep Learning Accelerator) for parallel GPU/DLA inference
- Target <2s latency for TTS+STT round-trip

**Documentation will be updated** when Jetson hardware is integrated (Phase 2 roadmap).

---

## Testing

### Run Unit Tests
```bash
# Test offline TTS/STT with mocks (no models required)
python -m pytest tests/test_offline_tts_stt.py -v

# Test with actual models (slow)
python -m pytest tests/test_offline_tts_stt.py -v --run-slow
```

### Manual Testing

**TTS**:
```python
python -c "from core.offline_tts import speak; result = speak('Testing offline TTS'); print(result)"
```

**STT**:
```bash
# Record 5 seconds with ffmpeg
ffmpeg -f alsa -i default -t 5 test_audio.wav  # Linux
# Or use Windows Sound Recorder

# Transcribe
python -c "from core.offline_stt import transcribe; print(transcribe('test_audio.wav'))"
```

---

## FAQ

**Q: Can I mix online and offline?**  
A: Yes! Use `OFFLINE_TTS_ENABLED=false` with `OFFLINE_STT_ENABLED=true` or vice versa.

**Q: Which TTS sounds better?**  
A: Coqui TTS > ElevenLabs > pyttsx3 (subjective, depends on voice/model).

**Q: Is offline faster?**  
A: Mixed. pyttsx3 is instant. Coqui ~1-3s. ElevenLabs ~0.5-2s. Whisper ~2-10s depending on model/length.

**Q: Can I use custom voices?**  
A: Yes! Coqui supports voice cloning. See [Coqui TTS docs](https://github.com/coqui-ai/TTS).

**Q: Does this work on Raspberry Pi?**  
A: Yes, but use `tiny` or `base` models. Pi 4 can run small models slowly (~10-30s).

**Q: What about macOS?**  
A: Fully supported. Use `say` command as alternative to pyttsx3 (future enhancement).

---

## Additional Resources

- [Coqui TTS Documentation](https://tts.readthedocs.io/)
- [whisper.cpp GitHub](https://github.com/ggerganov/whisper.cpp)
- [Whisper Model Card](https://github.com/openai/whisper)
- [pyttsx3 Documentation](https://pyttsx3.readthedocs.io/)

---

## Support

For issues or questions:
1. Check this documentation
2. Review logs in `logs/aria.log`
3. Open GitHub issue with logs and environment details
4. Tag: `offline-tts`, `offline-stt`, or `deployment`

---

**Last Updated**: 2026-01-13  
**Tested On**: Windows 11, Ubuntu 22.04, Python 3.10-3.12
