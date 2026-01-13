# Download offline TTS/STT models for Project Aria (Windows)
# Run this script to download recommended models for offline operation

Write-Host "Project Aria - Offline Model Downloader" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""

# Get model directory from env or use default
$ModelDir = if ($env:NOVA_OFFLINE_MODEL_DIR) { $env:NOVA_OFFLINE_MODEL_DIR } else { "$env:USERPROFILE\.aria\models" }

Write-Host "Model directory: " -NoNewline
Write-Host $ModelDir -ForegroundColor Yellow
Write-Host ""

# Create directory if it doesn't exist
New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null

# ========== Whisper.cpp Models ==========

Write-Host "1. Whisper.cpp STT Models" -ForegroundColor Green
Write-Host "   Recommended: small or medium"
Write-Host "   Sizes: tiny(75MB) base(142MB) small(466MB) medium(1.5GB) large(2.9GB)"
Write-Host ""

$WhisperChoice = Read-Host "Download whisper.cpp model? (small/medium/base/skip) [small]"
if ([string]::IsNullOrWhiteSpace($WhisperChoice)) { $WhisperChoice = "small" }

if ($WhisperChoice -ne "skip") {
    $WhisperModel = "ggml-$WhisperChoice.bin"
    $WhisperUrl = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$WhisperModel"
    $WhisperPath = Join-Path $ModelDir $WhisperModel
    
    if (Test-Path $WhisperPath) {
        Write-Host "   Model already exists: $WhisperModel" -ForegroundColor Yellow
    } else {
        Write-Host "   Downloading " -NoNewline
        Write-Host $WhisperModel -ForegroundColor Yellow -NoNewline
        Write-Host "..."
        
        try {
            Invoke-WebRequest -Uri $WhisperUrl -OutFile $WhisperPath
            Write-Host "   ✅ Downloaded $WhisperModel" -ForegroundColor Green
        } catch {
            Write-Host "   ❌ Download failed: $_" -ForegroundColor Red
        }
    }
    
    Write-Host "   Set environment variable:"
    Write-Host "   `$env:WHISPER_MODEL_PATH = '$WhisperPath'"
} else {
    Write-Host "   Skipped whisper.cpp model download" -ForegroundColor Yellow
}

Write-Host ""

# ========== Coqui TTS Models ==========

Write-Host "2. Coqui TTS Models" -ForegroundColor Green
Write-Host "   Models will be auto-downloaded on first use by TTS library"
Write-Host "   Default: tts_models/en/ljspeech/tacotron2-DDC (~200MB)"
Write-Host ""
Write-Host "   Popular models:"
Write-Host "   - tts_models/en/ljspeech/tacotron2-DDC (English, female, ~200MB)"
Write-Host "   - tts_models/en/vctk/vits (Multi-voice English, ~500MB)"
Write-Host "   - tts_models/multilingual/multi-dataset/your_tts (~2GB, many languages)"
Write-Host ""

$CoquiChoice = Read-Host "Pre-download Coqui model now? (y/N)"

if ($CoquiChoice -match "^[Yy]$") {
    Write-Host "   This requires Python and TTS package installed"
    Write-Host "   Installing TTS if not present..."
    
    try {
        python -c "import TTS" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "   Installing TTS package..."
            pip install TTS
        }
        
        Write-Host "   Downloading default model (this may take a few minutes)..."
        python -c "from TTS.api import TTS; TTS('tts_models/en/ljspeech/tacotron2-DDC')"
        Write-Host "   ✅ Coqui TTS model cached" -ForegroundColor Green
    } catch {
        Write-Host "   ❌ Failed: $_" -ForegroundColor Red
    }
} else {
    Write-Host "   Skipped. Models will download on first use." -ForegroundColor Yellow
}

Write-Host ""

# ========== whisper.cpp Binary ==========

Write-Host "3. whisper.cpp Binary" -ForegroundColor Green
Write-Host "   whisper.cpp needs to be built from source or use pre-built binaries"
Write-Host "   Repository: https://github.com/ggerganov/whisper.cpp"
Write-Host ""
Write-Host "   Windows build instructions:"
Write-Host "   1. Install Visual Studio 2022 with C++ tools"
Write-Host "   2. Clone: git clone https://github.com/ggerganov/whisper.cpp"
Write-Host "   3. Open Developer Command Prompt"
Write-Host "   4. cd whisper.cpp && mkdir build && cd build"
Write-Host "   5. cmake .."
Write-Host "   6. cmake --build . --config Release"
Write-Host ""
Write-Host "   OR download pre-built binaries from releases page"
Write-Host ""

$BuildChoice = Read-Host "Clone whisper.cpp repository? (y/N)"

if ($BuildChoice -match "^[Yy]$") {
    $WhisperDir = "$env:USERPROFILE\whisper.cpp"
    
    if (Test-Path $WhisperDir) {
        Write-Host "   whisper.cpp already cloned" -ForegroundColor Yellow
    } else {
        Write-Host "   Cloning whisper.cpp..."
        git clone https://github.com/ggerganov/whisper.cpp $WhisperDir
    }
    
    Write-Host ""
    Write-Host "   Manual build required. See above instructions." -ForegroundColor Yellow
    Write-Host "   After building, set:"
    Write-Host "   `$env:WHISPER_CPP_PATH = '$WhisperDir\build\bin\Release\main.exe'"
} else {
    Write-Host "   Skipped. Build manually or download pre-built binaries" -ForegroundColor Yellow
}

Write-Host ""

# ========== Summary ==========

Write-Host "==========================================" -ForegroundColor Green
Write-Host "Summary" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Model directory: $ModelDir"
Write-Host ""
Write-Host "Downloaded models:"

if (Test-Path $ModelDir) {
    Get-ChildItem -Path $ModelDir | Format-Table Name, Length, LastWriteTime
} else {
    Write-Host "  (no models downloaded)"
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Set environment variables (add to your PowerShell profile or config.py):"
Write-Host "     `$env:NOVA_OFFLINE_MODEL_DIR = '$ModelDir'"
Write-Host "     `$env:WHISPER_MODEL_PATH = '$ModelDir\ggml-small.bin'"
Write-Host "     `$env:WHISPER_CPP_PATH = 'C:\path\to\whisper.cpp\main.exe'"
Write-Host ""
Write-Host "  2. Enable offline mode:"
Write-Host "     `$env:OFFLINE_TTS_ENABLED = 'true'"
Write-Host "     `$env:OFFLINE_STT_ENABLED = 'true'"
Write-Host ""
Write-Host "  3. See docs/deployment/OFFLINE_TTS_STT.md for full setup"
Write-Host ""
Write-Host "✅ Setup complete!" -ForegroundColor Green
