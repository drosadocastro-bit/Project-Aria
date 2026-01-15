"""
Unit tests for persona routing functionality
Tests prefix detection, per-turn routing, and language detection
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.personality import (
    detect_target_personality,
    normalize_persona,
    detect_language,
    PERSONALITIES
)


class TestPersonaNormalization:
    """Test persona key normalization and validation."""
    
    def test_normalize_valid_personas(self):
        """Test normalization of valid persona keys."""
        assert normalize_persona("nova") == "nova"
        assert normalize_persona("aria") == "aria"
        assert normalize_persona("NOVA") == "nova"
        assert normalize_persona("Aria") == "aria"
        assert normalize_persona("  nova  ") == "nova"
    
    def test_normalize_invalid_personas(self):
        """Test normalization rejects invalid persona keys."""
        assert normalize_persona("joi") is None  # joi removed
        assert normalize_persona("invalid") is None
        assert normalize_persona("") is None
        assert normalize_persona(None) is None


class TestPrefixDetection:
    """Test persona addressee prefix detection."""
    
    def test_nova_prefix_detection(self):
        """Test detection of Nova prefix."""
        persona, text = detect_target_personality("Nova, what's the weather?")
        assert persona == "nova"
        assert text == "what's the weather?"
        
        persona, text = detect_target_personality("nova: check status")
        assert persona == "nova"
        assert text == "check status"
        
        persona, text = detect_target_personality("NOVA, hello")
        assert persona == "nova"
        assert text == "hello"
    
    def test_aria_prefix_detection(self):
        """Test detection of Aria prefix."""
        persona, text = detect_target_personality("Aria, check coolant")
        assert persona == "aria"
        assert text == "check coolant"
        
        persona, text = detect_target_personality("aria: what's the RPM?")
        assert persona == "aria"
        assert text == "what's the RPM?"
        
        persona, text = detect_target_personality("ARIA, status")
        assert persona == "aria"
        assert text == "status"
    
    def test_no_prefix(self):
        """Test that non-prefixed messages return None."""
        persona, text = detect_target_personality("What's the temperature?")
        assert persona is None
        assert text == "What's the temperature?"
        
        persona, text = detect_target_personality("Tell me about Nova")
        assert persona is None
        assert text == "Tell me about Nova"
    
    def test_prefix_in_middle(self):
        """Test that persona name in middle doesn't trigger detection."""
        persona, text = detect_target_personality("Tell Nova to check status")
        assert persona is None
        assert text == "Tell Nova to check status"
        
        persona, text = detect_target_personality("Ask Aria about this")
        assert persona is None
        assert text == "Ask Aria about this"
    
    def test_empty_input(self):
        """Test handling of empty input."""
        persona, text = detect_target_personality("")
        assert persona is None
        assert text == ""
        
        persona, text = detect_target_personality(None)
        assert persona is None
        assert text is None


class TestLanguageDetection:
    """Test Spanglish-friendly language detection."""
    
    def test_english_detection(self):
        """Test detection of English text."""
        assert detect_language("What is the coolant temperature?") == "en"
        assert detect_language("Check the engine status") == "en"
        assert detect_language("How fast am I going?") == "en"
        assert detect_language("Hello, how are you?") == "en"
    
    def test_spanish_detection(self):
        """Test detection of Spanish text."""
        assert detect_language("¿Qué temperatura tiene el refrigerante?") == "es"
        assert detect_language("¿Cómo está el motor?") == "es"
        assert detect_language("Hola, ¿cómo estás?") == "es"
        assert detect_language("Para revisar el problema") == "es"
        assert detect_language("El coche está muy rápido") == "es"
    
    def test_spanglish_detection(self):
        """Test detection of mixed Spanish/English (Spanglish)."""
        # More Spanish indicators should classify as Spanish
        assert detect_language("¿Qué es el coolant temperature?") == "es"
        assert detect_language("Check el motor, por favor") == "es"
        
        # More English should stay English
        assert detect_language("The temperature está high") == "en"
    
    def test_edge_cases(self):
        """Test edge cases in language detection."""
        assert detect_language("") == "en"  # Default to English
        assert detect_language("123456") == "en"  # Numbers default to English
        assert detect_language("!@#$%") == "en"  # Special chars default to English


class TestPerTurnRouting:
    """Test that per-turn addressing doesn't change default persona."""
    
    def test_per_turn_addressee_isolation(self):
        """
        Test that addressing a persona for one turn doesn't change default.
        This test is conceptual - actual behavior tested in integration.
        """
        # User says: "Nova, explain quantum mechanics"
        persona, text = detect_target_personality("Nova, explain quantum mechanics")
        assert persona == "nova"
        assert text == "explain quantum mechanics"
        
        # Next message without prefix should use default (not Nova)
        persona2, text2 = detect_target_personality("What about thermodynamics?")
        assert persona2 is None  # No addressee, should use session default
        assert text2 == "What about thermodynamics?"
    
    def test_explicit_switch_command(self):
        """
        Test that explicit switch commands (e.g., /nova, /aria) should be
        handled separately in the main application, not in prefix detection.
        """
        # Commands should not be detected as prefixes
        persona, text = detect_target_personality("/nova")
        assert persona is None
        assert text == "/nova"
        
        persona, text = detect_target_personality("/aria")
        assert persona is None
        assert text == "/aria"


class TestDrivingContractPersona:
    """Test that driving contract applies regardless of persona."""
    
    def test_persona_exists(self):
        """Verify both personas exist in PERSONALITIES dict."""
        assert "nova" in PERSONALITIES
        assert "aria" in PERSONALITIES
        
        # Verify joi is removed
        assert "joi" not in PERSONALITIES
    
    def test_both_personas_have_prompts(self):
        """Verify both personas have required prompts."""
        for persona in ["nova", "aria"]:
            assert "system_prompt_en" in PERSONALITIES[persona]
            assert "system_prompt_es" in PERSONALITIES[persona]
            assert "name" in PERSONALITIES[persona]
            assert "greetings" in PERSONALITIES[persona]


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
