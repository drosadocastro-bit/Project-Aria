"""
Live Audio Stream Analyzer - Real-time genre classification from system audio
Works without Spotify API by capturing system audio output
"""

import sys
import time
import numpy as np
from pathlib import Path
from collections import deque
import threading

sys.path.insert(0, str(Path(__file__).parent))

from core.audio_intelligence import (
    GenreEQMapper,
    EQ_PRESETS,
    apply_eq_to_apo,
    GTZAN_TO_EQ,
    get_ml_classifier
)

# Configuration
SAMPLE_RATE = 22050  # Standard for librosa/GTZAN
CHUNK_DURATION = 5   # Seconds of audio to analyze per chunk
ANALYSIS_INTERVAL = 10  # Seconds between analyses (avoid constant CPU usage)
CONFIDENCE_THRESHOLD = 0.6  # Minimum confidence to apply EQ change


class LiveAudioAnalyzer:
    """
    Captures system audio and classifies genre in real-time.
    Uses Windows WASAPI loopback for audio capture.
    """
    
    def __init__(self):
        self.classifier = get_ml_classifier()
        self.running = False
        self.current_preset = "flat"
        self.last_analysis_time = 0
        self.audio_buffer = deque(maxlen=SAMPLE_RATE * CHUNK_DURATION)
        
        # Check dependencies
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Verify required packages are installed."""
        self.has_soundcard = False
        self.has_librosa = False
        
        try:
            import soundcard
            self.has_soundcard = True
            print("✅ soundcard available for audio capture")
        except ImportError:
            print("⚠️ soundcard not installed: pip install soundcard")
        
        try:
            import librosa
            self.has_librosa = True
            print("✅ librosa available for feature extraction")
        except ImportError:
            print("⚠️ librosa not installed: pip install librosa")
        
        if self.classifier and self.classifier.is_trained:
            print(f"✅ ML classifier ready (accuracy: {self.classifier.accuracy:.0%})")
        else:
            print("⚠️ ML classifier not trained - run: python -m core.genre_classifier")
    
    def get_loopback_device(self):
        """Get the system audio loopback device."""
        if not self.has_soundcard:
            return None
        
        import soundcard as sc
        
        try:
            # Try to get the default loopback device (WASAPI on Windows)
            for mic in sc.all_microphones(include_loopback=True):
                if "loopback" in mic.name.lower() or "stereo mix" in mic.name.lower():
                    print(f"🔊 Using loopback: {mic.name}")
                    return mic
            
            # Fallback: use default microphone
            default_mic = sc.default_microphone()
            print(f"🔊 Using default microphone: {default_mic.name}")
            return default_mic
        except Exception as e:
            print(f"⚠️ Error getting loopback device: {e}")
            return None
    
    def extract_features(self, audio_data):
        """Extract GTZAN-compatible features from audio buffer."""
        if not self.has_librosa:
            return None
        
        import librosa
        
        y = np.array(audio_data).astype(np.float32)
        
        # Normalize
        if np.max(np.abs(y)) > 0:
            y = y / np.max(np.abs(y))
        
        features = []
        
        try:
            # Chroma STFT
            chroma = librosa.feature.chroma_stft(y=y, sr=SAMPLE_RATE)
            features.extend([chroma.mean(), chroma.var()])
            
            # RMS Energy
            rms = librosa.feature.rms(y=y)
            features.extend([rms.mean(), rms.var()])
            
            # Spectral Centroid
            cent = librosa.feature.spectral_centroid(y=y, sr=SAMPLE_RATE)
            features.extend([cent.mean(), cent.var()])
            
            # Spectral Bandwidth
            bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=SAMPLE_RATE)
            features.extend([bandwidth.mean(), bandwidth.var()])
            
            # Spectral Rolloff
            rolloff = librosa.feature.spectral_rolloff(y=y, sr=SAMPLE_RATE)
            features.extend([rolloff.mean(), rolloff.var()])
            
            # Zero Crossing Rate
            zcr = librosa.feature.zero_crossing_rate(y)
            features.extend([zcr.mean(), zcr.var()])
            
            # Harmony and Perceptr (using harmonic/percussive separation)
            y_harm, y_perc = librosa.effects.hpss(y)
            features.extend([y_harm.mean(), y_harm.var()])
            features.extend([y_perc.mean(), y_perc.var()])
            
            # Tempo
            tempo, _ = librosa.beat.beat_track(y=y, sr=SAMPLE_RATE)
            features.append(float(tempo))
            
            # MFCCs (20 coefficients)
            mfccs = librosa.feature.mfcc(y=y, sr=SAMPLE_RATE, n_mfcc=20)
            for i in range(20):
                features.extend([mfccs[i].mean(), mfccs[i].var()])
            
            return np.array(features)
        
        except Exception as e:
            print(f"⚠️ Feature extraction error: {e}")
            return None
    
    def classify_audio(self, audio_data):
        """Classify genre from audio data."""
        if not self.classifier or not self.classifier.is_trained:
            return None, 0.0
        
        features = self.extract_features(audio_data)
        if features is None:
            return None, 0.0
        
        result = self.classifier.predict_with_confidence(features)
        return result['genre'], result['confidence']
    
    def analyze_and_apply_eq(self):
        """Analyze current audio buffer and apply EQ if needed."""
        if len(self.audio_buffer) < SAMPLE_RATE * 2:  # Need at least 2 seconds
            return
        
        audio_data = list(self.audio_buffer)
        genre, confidence = self.classify_audio(audio_data)
        
        if genre and confidence >= CONFIDENCE_THRESHOLD:
            preset = GTZAN_TO_EQ.get(genre, "v_shape")
            
            if preset != self.current_preset:
                print(f"\n🎵 Detected: {genre} ({confidence:.0%})")
                print(f"🎛️ Applying EQ: {preset}")
                apply_eq_to_apo(EQ_PRESETS[preset], preset)
                self.current_preset = preset
    
    def start_capture(self):
        """Start capturing and analyzing system audio."""
        if not self.has_soundcard or not self.has_librosa:
            print("❌ Missing dependencies for live capture")
            print("   Install: pip install soundcard librosa")
            return
        
        import soundcard as sc
        
        device = self.get_loopback_device()
        if not device:
            print("❌ No audio device found")
            return
        
        print("\n" + "=" * 60)
        print("  🎧 LIVE AUDIO ANALYZER - System Audio Classification")
        print(f"  📊 Analysis interval: {ANALYSIS_INTERVAL}s")
        print(f"  🎯 Confidence threshold: {CONFIDENCE_THRESHOLD:.0%}")
        print("  Press Ctrl+C to stop")
        print("=" * 60)
        
        self.running = True
        
        try:
            # Capture from loopback (system audio output)
            device = self.get_loopback_device()
            if not device:
                print("❌ No loopback device found")
                return
            
            with device.recorder(samplerate=SAMPLE_RATE, channels=1, blocksize=1024) as mic:
                while self.running:
                    # Record audio chunk
                    data = mic.record(numframes=1024)
                    self.audio_buffer.extend(data.flatten())
                    
                    # Check if it's time to analyze
                    current_time = time.time()
                    if current_time - self.last_analysis_time >= ANALYSIS_INTERVAL:
                        self.analyze_and_apply_eq()
                        self.last_analysis_time = current_time
        
        except KeyboardInterrupt:
            print("\n\n👋 Stopping live analyzer...")
            apply_eq_to_apo(EQ_PRESETS["flat"], "flat")
            print("   Reset to flat EQ")
        except Exception as e:
            print(f"\n❌ Error: {e}")
        finally:
            self.running = False
    
    def stop(self):
        """Stop the capture loop."""
        self.running = False


def main():
    print("=" * 60)
    print("  Aria Live Audio Analyzer")
    print("  Real-time genre classification from system audio")
    print("=" * 60)
    
    analyzer = LiveAudioAnalyzer()
    
    if not analyzer.has_soundcard:
        print("\n📦 Installing soundcard for audio capture...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "soundcard", "-q"])
        print("   Restart the script after installation")
        return
    
    analyzer.start_capture()


if __name__ == "__main__":
    main()
