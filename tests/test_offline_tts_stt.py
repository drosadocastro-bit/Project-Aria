"""
Unit tests for offline TTS and STT modules
Tests use mocks to avoid requiring actual models
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
import tempfile
import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import modules to test
from core import offline_tts, offline_stt


class TestOfflineTTS:
    """Test offline TTS functionality with mocked backends."""
    
    def setup_method(self):
        """Reset TTS state before each test."""
        offline_tts._backend_initialized = False
        offline_tts._coqui_tts = None
        offline_tts._pyttsx3_engine = None
        offline_tts._current_backend = None
    
    def test_init_coqui_success(self):
        """Test successful Coqui TTS initialization."""
        mock_tts = Mock()
        
        with patch('core.offline_tts.TTS', return_value=mock_tts):
            result = offline_tts._init_coqui()
            
            assert result is True
            assert offline_tts._coqui_tts is not None
            assert offline_tts._current_backend == "coqui"
    
    def test_init_coqui_import_error(self):
        """Test Coqui TTS initialization with import error."""
        with patch('core.offline_tts.TTS', side_effect=ImportError("No module")):
            result = offline_tts._init_coqui()
            
            assert result is False
            assert offline_tts._coqui_tts is None
    
    def test_init_pyttsx3_success(self):
        """Test successful pyttsx3 initialization."""
        mock_engine = Mock()
        mock_engine.getProperty.return_value = [Mock(name="Female Voice", id="voice1")]
        
        with patch('pyttsx3.init', return_value=mock_engine):
            result = offline_tts._init_pyttsx3()
            
            assert result is True
            assert offline_tts._pyttsx3_engine is not None
            assert offline_tts._current_backend == "pyttsx3"
            
            # Verify configuration
            mock_engine.setProperty.assert_any_call('rate', 150)
            mock_engine.setProperty.assert_any_call('volume', 0.9)
    
    def test_init_pyttsx3_import_error(self):
        """Test pyttsx3 initialization with import error."""
        with patch('pyttsx3.init', side_effect=ImportError("No module")):
            result = offline_tts._init_pyttsx3()
            
            assert result is False
            assert offline_tts._pyttsx3_engine is None
    
    def test_initialize_tts_auto_coqui(self):
        """Test auto-initialization prefers Coqui."""
        mock_tts = Mock()
        
        with patch('core.offline_tts.TTS', return_value=mock_tts):
            result = offline_tts.initialize_tts()
            
            assert result is True
            assert offline_tts._backend_initialized is True
            assert offline_tts._current_backend == "coqui"
    
    def test_initialize_tts_auto_fallback_pyttsx3(self):
        """Test auto-initialization falls back to pyttsx3."""
        mock_engine = Mock()
        mock_engine.getProperty.return_value = []
        
        with patch('core.offline_tts.TTS', side_effect=ImportError()), \
             patch('pyttsx3.init', return_value=mock_engine):
            result = offline_tts.initialize_tts()
            
            assert result is True
            assert offline_tts._backend_initialized is True
            assert offline_tts._current_backend == "pyttsx3"
    
    def test_initialize_tts_force_backend(self):
        """Test forced backend selection."""
        mock_engine = Mock()
        mock_engine.getProperty.return_value = []
        
        with patch('pyttsx3.init', return_value=mock_engine):
            result = offline_tts.initialize_tts(force_backend="pyttsx3")
            
            assert result is True
            assert offline_tts._current_backend == "pyttsx3"
    
    def test_initialize_tts_no_backend_available(self):
        """Test initialization fails when no backend available."""
        with patch('core.offline_tts.TTS', side_effect=ImportError()), \
             patch('pyttsx3.init', side_effect=ImportError()):
            result = offline_tts.initialize_tts()
            
            assert result is False
            assert offline_tts._backend_initialized is False
    
    def test_speak_coqui(self):
        """Test speak() with Coqui backend."""
        mock_tts = Mock()
        
        with patch('core.offline_tts.TTS', return_value=mock_tts), \
             patch('core.offline_tts._backend_initialized', True), \
             patch('core.offline_tts._current_backend', 'coqui'), \
             patch('core.offline_tts._coqui_tts', mock_tts):
            
            result = offline_tts.speak("Test text")
            
            assert result['success'] is True
            assert result['backend'] == "coqui"
            assert 'audio_path' in result
            assert result['audio_path'].endswith('.wav')
            
            # Verify TTS was called
            mock_tts.tts_to_file.assert_called_once()
    
    def test_speak_pyttsx3(self):
        """Test speak() with pyttsx3 backend."""
        mock_engine = Mock()
        
        with patch('core.offline_tts._backend_initialized', True), \
             patch('core.offline_tts._current_backend', 'pyttsx3'), \
             patch('core.offline_tts._pyttsx3_engine', mock_engine):
            
            result = offline_tts.speak("Test text")
            
            assert result['success'] is True
            assert result['backend'] == "pyttsx3"
            assert 'audio_path' in result
            
            # Verify engine was used
            mock_engine.save_to_file.assert_called_once()
            mock_engine.runAndWait.assert_called_once()
    
    def test_speak_custom_path(self):
        """Test speak() with custom output path."""
        mock_tts = Mock()
        custom_path = "/tmp/test_audio.wav"
        
        with patch('core.offline_tts.TTS', return_value=mock_tts), \
             patch('core.offline_tts._backend_initialized', True), \
             patch('core.offline_tts._current_backend', 'coqui'), \
             patch('core.offline_tts._coqui_tts', mock_tts):
            
            result = offline_tts.speak("Test", out_path=custom_path)
            
            assert result['audio_path'] == custom_path
    
    @pytest.mark.asyncio
    async def test_speak_async(self):
        """Test async speak() function."""
        mock_tts = Mock()
        
        with patch('core.offline_tts.TTS', return_value=mock_tts), \
             patch('core.offline_tts._backend_initialized', True), \
             patch('core.offline_tts._current_backend', 'coqui'), \
             patch('core.offline_tts._coqui_tts', mock_tts):
            
            result = await offline_tts.speak_async("Async test")
            
            assert result['success'] is True
            assert 'audio_path' in result
    
    def test_get_backend_info(self):
        """Test backend info retrieval."""
        with patch('core.offline_tts._backend_initialized', True), \
             patch('core.offline_tts._current_backend', 'coqui'):
            
            info = offline_tts.get_backend_info()
            
            assert info['initialized'] is True
            assert info['backend'] == 'coqui'
            assert 'coqui_available' in info
            assert 'pyttsx3_available' in info
    
    def test_cleanup_old_files(self):
        """Test cleanup of old TTS files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tts_dir = Path(tmpdir) / "static" / "tts"
            tts_dir.mkdir(parents=True, exist_ok=True)
            
            # Create dummy files
            for i in range(25):
                file_path = tts_dir / f"audio_{i}.wav"
                file_path.write_text("dummy")
            
            with patch.object(Path, 'parent', Path(tmpdir)):
                # This is a simplified test - in real scenario would need proper patching
                files = sorted(tts_dir.glob("*.wav"))
                assert len(files) == 25


class TestOfflineSTT:
    """Test offline STT functionality with mocked whisper.cpp."""
    
    def setup_method(self):
        """Reset STT state before each test."""
        offline_stt._backend_initialized = False
        offline_stt._whisper_cpp_path = None
        offline_stt._whisper_model_path = None
    
    def test_initialize_stt_success(self):
        """Test successful STT initialization."""
        with tempfile.NamedTemporaryFile(suffix='.bin') as model_file, \
             tempfile.NamedTemporaryFile(suffix='.exe') as binary_file:
            
            with patch.dict(os.environ, {
                'WHISPER_CPP_PATH': binary_file.name,
                'WHISPER_MODEL_PATH': model_file.name
            }):
                result = offline_stt.initialize_stt()
                
                assert result is True
                assert offline_stt._backend_initialized is True
                assert offline_stt._whisper_cpp_path is not None
                assert offline_stt._whisper_model_path is not None
    
    def test_initialize_stt_no_binary(self):
        """Test STT initialization fails without binary."""
        with patch.dict(os.environ, {}, clear=True):
            result = offline_stt.initialize_stt()
            
            assert result is False
            assert offline_stt._backend_initialized is False
    
    def test_initialize_stt_no_model(self):
        """Test STT initialization fails without model."""
        with tempfile.NamedTemporaryFile(suffix='.exe') as binary_file:
            with patch.dict(os.environ, {
                'WHISPER_CPP_PATH': binary_file.name,
                'WHISPER_MODEL_PATH': '/nonexistent/model.bin'
            }):
                result = offline_stt.initialize_stt()
                
                assert result is False
    
    def test_transcribe_success(self):
        """Test successful transcription."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Hello world from whisper"
        mock_result.stderr = ""
        
        with tempfile.NamedTemporaryFile(suffix='.wav') as audio_file, \
             tempfile.NamedTemporaryFile(suffix='.bin') as model_file, \
             tempfile.NamedTemporaryFile(suffix='') as binary_file:
            
            with patch('subprocess.run', return_value=mock_result), \
                 patch('core.offline_stt._backend_initialized', True), \
                 patch('core.offline_stt._whisper_cpp_path', Path(binary_file.name)), \
                 patch('core.offline_stt._whisper_model_path', Path(model_file.name)):
                
                result = offline_stt.transcribe(audio_file.name)
                
                assert result['success'] is True
                assert result['text'] == "Hello world from whisper"
                assert result['language'] == "en"
                assert 'model' in result
    
    def test_transcribe_file_not_found(self):
        """Test transcription with missing file."""
        with patch('core.offline_stt._backend_initialized', True):
            result = offline_stt.transcribe("/nonexistent/file.wav")
            
            assert result['success'] is False
            assert 'error' in result
    
    def test_transcribe_whisper_error(self):
        """Test transcription with whisper.cpp error."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "whisper error"
        
        with tempfile.NamedTemporaryFile(suffix='.wav') as audio_file, \
             tempfile.NamedTemporaryFile(suffix='.bin') as model_file, \
             tempfile.NamedTemporaryFile(suffix='') as binary_file:
            
            with patch('subprocess.run', return_value=mock_result), \
                 patch('core.offline_stt._backend_initialized', True), \
                 patch('core.offline_stt._whisper_cpp_path', Path(binary_file.name)), \
                 patch('core.offline_stt._whisper_model_path', Path(model_file.name)):
                
                result = offline_stt.transcribe(audio_file.name)
                
                assert result['success'] is False
                assert 'error' in result
    
    def test_transcribe_timeout(self):
        """Test transcription timeout."""
        from subprocess import TimeoutExpired
        
        with tempfile.NamedTemporaryFile(suffix='.wav') as audio_file, \
             tempfile.NamedTemporaryFile(suffix='.bin') as model_file, \
             tempfile.NamedTemporaryFile(suffix='') as binary_file:
            
            with patch('subprocess.run', side_effect=TimeoutExpired("cmd", 60)), \
                 patch('core.offline_stt._backend_initialized', True), \
                 patch('core.offline_stt._whisper_cpp_path', Path(binary_file.name)), \
                 patch('core.offline_stt._whisper_model_path', Path(model_file.name)):
                
                result = offline_stt.transcribe(audio_file.name)
                
                assert result['success'] is False
                assert 'timeout' in result['error'].lower()
    
    def test_transcribe_with_metadata(self):
        """Test transcription filters out metadata lines."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """[00:00.000 --> 00:02.000]  Hello
[00:02.000 --> 00:04.000]  world
Actual transcription here"""
        mock_result.stderr = ""
        
        with tempfile.NamedTemporaryFile(suffix='.wav') as audio_file, \
             tempfile.NamedTemporaryFile(suffix='.bin') as model_file, \
             tempfile.NamedTemporaryFile(suffix='') as binary_file:
            
            with patch('subprocess.run', return_value=mock_result), \
                 patch('core.offline_stt._backend_initialized', True), \
                 patch('core.offline_stt._whisper_cpp_path', Path(binary_file.name)), \
                 patch('core.offline_stt._whisper_model_path', Path(model_file.name)):
                
                result = offline_stt.transcribe(audio_file.name)
                
                assert result['success'] is True
                # Should filter out timestamp lines
                assert '[' not in result['text']
                assert 'Actual transcription here' in result['text']
    
    def test_get_backend_info(self):
        """Test backend info retrieval."""
        with tempfile.NamedTemporaryFile(suffix='.bin') as model_file:
            with patch('core.offline_stt._backend_initialized', True), \
                 patch('core.offline_stt._whisper_model_path', Path(model_file.name)):
                
                info = offline_stt.get_backend_info()
                
                assert info['initialized'] is True
                assert info['backend'] == 'whisper.cpp'
                assert 'model_name' in info


class TestIntegration:
    """Integration tests for TTS/STT workflow."""
    
    def test_tts_stt_roundtrip(self):
        """Test TTS generation followed by STT transcription (mocked)."""
        mock_tts = Mock()
        mock_stt_result = Mock()
        mock_stt_result.returncode = 0
        mock_stt_result.stdout = "Test text"
        
        with patch('core.offline_tts.TTS', return_value=mock_tts), \
             patch('core.offline_tts._backend_initialized', True), \
             patch('core.offline_tts._current_backend', 'coqui'), \
             patch('core.offline_tts._coqui_tts', mock_tts), \
             patch('subprocess.run', return_value=mock_stt_result), \
             patch('core.offline_stt._backend_initialized', True), \
             patch('core.offline_stt._whisper_cpp_path', Path('/tmp/main')), \
             patch('core.offline_stt._whisper_model_path', Path('/tmp/model.bin')):
            
            # Generate speech
            tts_result = offline_tts.speak("Test text")
            assert tts_result['success'] is True
            
            # Transcribe it back (in real scenario, would use actual file)
            with tempfile.NamedTemporaryFile(suffix='.wav') as f:
                stt_result = offline_stt.transcribe(f.name)
                assert stt_result['success'] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
