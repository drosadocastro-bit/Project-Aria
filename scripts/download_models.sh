#!/bin/bash
# Download offline TTS/STT models for Project Aria
# Run this script to download recommended models for offline operation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Project Aria - Offline Model Downloader${NC}"
echo "=========================================="
echo ""

# Get model directory from env or use default
MODEL_DIR="${NOVA_OFFLINE_MODEL_DIR:-$HOME/.aria/models}"

echo -e "Model directory: ${YELLOW}$MODEL_DIR${NC}"
echo ""

# Create directory if it doesn't exist
mkdir -p "$MODEL_DIR"

# ========== Whisper.cpp Models ==========

echo -e "${GREEN}1. Whisper.cpp STT Models${NC}"
echo "   Recommended: small or medium"
echo "   Sizes: tiny(75MB) base(142MB) small(466MB) medium(1.5GB) large(2.9GB)"
echo ""

read -p "Download whisper.cpp model? (small/medium/base/skip) [small]: " WHISPER_CHOICE
WHISPER_CHOICE=${WHISPER_CHOICE:-small}

if [ "$WHISPER_CHOICE" != "skip" ]; then
    WHISPER_MODEL="ggml-${WHISPER_CHOICE}.bin"
    WHISPER_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/${WHISPER_MODEL}"
    
    if [ -f "$MODEL_DIR/$WHISPER_MODEL" ]; then
        echo -e "${YELLOW}   Model already exists: $WHISPER_MODEL${NC}"
    else
        echo -e "   Downloading ${YELLOW}$WHISPER_MODEL${NC}..."
        curl -L -o "$MODEL_DIR/$WHISPER_MODEL" "$WHISPER_URL"
        echo -e "${GREEN}   ✅ Downloaded $WHISPER_MODEL${NC}"
    fi
    
    echo "   Set environment variable:"
    echo "   export WHISPER_MODEL_PATH=$MODEL_DIR/$WHISPER_MODEL"
else
    echo -e "${YELLOW}   Skipped whisper.cpp model download${NC}"
fi

echo ""

# ========== Coqui TTS Models ==========

echo -e "${GREEN}2. Coqui TTS Models${NC}"
echo "   Models will be auto-downloaded on first use by TTS library"
echo "   Default: tts_models/en/ljspeech/tacotron2-DDC (~200MB)"
echo ""
echo "   Popular models:"
echo "   - tts_models/en/ljspeech/tacotron2-DDC (English, female, ~200MB)"
echo "   - tts_models/en/vctk/vits (Multi-voice English, ~500MB)"
echo "   - tts_models/multilingual/multi-dataset/your_tts (~2GB, many languages)"
echo ""

read -p "Pre-download Coqui model now? (y/N): " COQUI_CHOICE

if [[ "$COQUI_CHOICE" =~ ^[Yy]$ ]]; then
    echo "   This requires Python and TTS package installed"
    echo "   Installing TTS if not present..."
    
    if ! python3 -c "import TTS" 2>/dev/null; then
        echo "   Installing TTS package..."
        pip install TTS
    fi
    
    echo "   Downloading default model (this may take a few minutes)..."
    python3 -c "from TTS.api import TTS; TTS('tts_models/en/ljspeech/tacotron2-DDC')"
    echo -e "${GREEN}   ✅ Coqui TTS model cached${NC}"
else
    echo -e "${YELLOW}   Skipped. Models will download on first use.${NC}"
fi

echo ""

# ========== whisper.cpp Binary ==========

echo -e "${GREEN}3. whisper.cpp Binary${NC}"
echo "   whisper.cpp needs to be built from source"
echo "   Repository: https://github.com/ggerganov/whisper.cpp"
echo ""

if command -v git &> /dev/null; then
    read -p "Clone and build whisper.cpp now? (y/N): " BUILD_WHISPER
    
    if [[ "$BUILD_WHISPER" =~ ^[Yy]$ ]]; then
        WHISPER_DIR="$HOME/whisper.cpp"
        
        if [ -d "$WHISPER_DIR" ]; then
            echo -e "${YELLOW}   whisper.cpp already cloned${NC}"
        else
            echo "   Cloning whisper.cpp..."
            git clone https://github.com/ggerganov/whisper.cpp "$WHISPER_DIR"
        fi
        
        echo "   Building..."
        cd "$WHISPER_DIR"
        make
        
        if [ -f "./main" ]; then
            echo -e "${GREEN}   ✅ Built whisper.cpp${NC}"
            echo "   Binary: $WHISPER_DIR/main"
            echo "   Set environment variable:"
            echo "   export WHISPER_CPP_PATH=$WHISPER_DIR/main"
        else
            echo -e "${RED}   ❌ Build failed${NC}"
        fi
    else
        echo -e "${YELLOW}   Skipped. Build manually:${NC}"
        echo "   git clone https://github.com/ggerganov/whisper.cpp"
        echo "   cd whisper.cpp && make"
    fi
else
    echo -e "${YELLOW}   git not found. Clone manually from:${NC}"
    echo "   https://github.com/ggerganov/whisper.cpp"
fi

echo ""

# ========== Summary ==========

echo -e "${GREEN}=========================================="
echo "Summary"
echo "==========================================${NC}"
echo ""
echo "Model directory: $MODEL_DIR"
echo ""
echo "Downloaded models:"
ls -lh "$MODEL_DIR" 2>/dev/null || echo "  (no models downloaded)"
echo ""
echo "Next steps:"
echo "  1. Set environment variables in your shell or config.py:"
echo "     export NOVA_OFFLINE_MODEL_DIR=$MODEL_DIR"
echo "     export WHISPER_MODEL_PATH=$MODEL_DIR/ggml-small.bin"
echo "     export WHISPER_CPP_PATH=$HOME/whisper.cpp/main"
echo ""
echo "  2. Enable offline mode:"
echo "     export OFFLINE_TTS_ENABLED=true"
echo "     export OFFLINE_STT_ENABLED=true"
echo ""
echo "  3. See docs/deployment/OFFLINE_TTS_STT.md for full setup"
echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
