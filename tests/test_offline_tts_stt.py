"""
Unit tests for offline TTS and STT modules
Tests use mocks to avoid requiring actual models
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestOfflineTTSBasics:
    """Test basic offline TTS functionality without deep mocking."""
    
    def test_import_modules(self):
        """Test that modules import correctly."""
        from core import offline_tts
        from core import offline_stt
        
        assert hasattr(offline_tts, 'speak')
        assert hasattr(offline_tts, 'speak_async')
        assert hasattr(offline_tts, 'initialize_tts')
        assert hasattr(offline_stt, 'transcribe')
        assert hasattr(offline_stt, 'initialize_stt')
    
    def test_get_backend_info_tts(self):
        """Test TTS backend info retrieval."""
        from core import offline_tts
        
        info = offline_tts.get_backend_info()
        
        assert 'initialized' in info
        assert 'backend' in info
        assert 'coqui_available' in info
        assert 'pyttsx3_available' in info
    
    def test_get_backend_info_stt(self):
        """Test STT backend info retrieval."""
        from core import offline_stt
        
        info = offline_stt.get_backend_info()
        
        assert 'initialized' in info
        assert 'backend' in info


class TestOfflineSTT:
    """Test offline STT functionality with mocked whisper.cpp."""
    
    def test_transcribe_file_not_found(self):
        """Test transcription with missing file."""
        from core import offline_stt
        
        # Set backend as initialized to skip init
        offline_stt._backend_initialized = True
        
        result = offline_stt.transcribe("/nonexistent/file.wav")
        
        assert result['success'] is False
        assert 'error' in result
    
    def test_transcribe_success(self):
        """Test successful transcription."""
        from core import offline_stt
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Hello world from whisper"
        mock_result.stderr = ""
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as audio_file:
            audio_path = audio_file.name
        
        try:
            with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as model_file:
                model_path = model_file.name
            
            with tempfile.NamedTemporaryFile(delete=False) as binary_file:
                binary_path = binary_file.name
            
            try:
                with patch('subprocess.run', return_value=mock_result):
                    offline_stt._backend_initialized = True
                    offline_stt._whisper_cpp_path = Path(binary_path)
                    offline_stt._whisper_model_path = Path(model_path)
                    
                    result = offline_stt.transcribe(audio_path)
                    
                    assert result['success'] is True
                    assert result['text'] == "Hello world from whisper"
                    assert result['language'] == "en"
            finally:
                try:
                    os.unlink(model_path)
                    os.unlink(binary_path)
                except:
                    pass
        finally:
            try:
                os.unlink(audio_path)
            except:
                pass
    
    def test_transcribe_filters_metadata(self):
        """Test transcription filters out metadata lines."""
        from core import offline_stt
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """[00:00.000 --> 00:02.000]  Hello
[00:02.000 --> 00:04.000]  world
Actual transcription here"""
        mock_result.stderr = ""
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as audio_file:
            audio_path = audio_file.name
        
        try:
            with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as model_file, \
                 tempfile.NamedTemporaryFile(delete=False) as binary_file:
                
                try:
                    with patch('subprocess.run', return_value=mock_result):
                        offline_stt._backend_initialized = True
                        offline_stt._whisper_cpp_path = Path(binary_file.name)
                        offline_stt._whisper_model_path = Path(model_file.name)
                        
                        result = offline_stt.transcribe(audio_path)
                        
                        assert result['success'] is True
                        # Should filter out timestamp lines
                        assert '[' not in result['text']
                        assert 'Actual transcription here' in result['text']
                finally:
                    try:
                        os.unlink(model_file.name)
                        os.unlink(binary_file.name)
                    except:
                        pass
        finally:
            try:
                os.unlink(audio_path)
            except:
                pass


class TestOfflineTTSPyttsx3:
    """Test offline TTS with pyttsx3 backend (if available)."""
    
    def test_speak_pyttsx3_backend(self):
        """Test speak() with pyttsx3 backend."""
        from core import offline_tts
        
        mock_engine = Mock()
        
        offline_tts._backend_initialized = True
        offline_tts._current_backend = 'pyttsx3'
        offline_tts._pyttsx3_engine = mock_engine
        
        result = offline_tts.speak("Test text")
        
        assert result['success'] is True
        assert result['backend'] == "pyttsx3"
        assert 'audio_path' in result
        
        # Verify engine was used
        mock_engine.save_to_file.assert_called_once()
        mock_engine.runAndWait.assert_called_once()


@pytest.mark.asyncio
async def test_speak_async_pyttsx3():
    """Test async speak() function."""
    from core import offline_tts
    
    mock_engine = Mock()
    
    offline_tts._backend_initialized = True
    offline_tts._current_backend = 'pyttsx3'
    offline_tts._pyttsx3_engine = mock_engine
    
    result = await offline_tts.speak_async("Async test")
    
    assert result['success'] is True
    assert 'audio_path' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
