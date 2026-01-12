"""
Response Validator for Aria - DRIVING Mode Enforcement
Validates and sanitizes responses based on vehicle state
"""

import re
from typing import Optional, Tuple
from core.state_manager import VehicleState


class ResponseValidator:
    """
    Validates and enforces response constraints for DRIVING mode.
    
    In DRIVING state:
    - Enforces maximum length
    - Blocks questions, affectionate language, narrative markers
    - Ensures safety-first communication
    """
    
    # Prohibited patterns in DRIVING mode
    AFFECTIONATE_TERMS = [
        'love', 'dear', 'honey', 'sweetheart', 'darling',
        'babe', 'baby', 'sweetie', 'beloved'
    ]
    
    NARRATIVE_MARKERS = [
        'you know', 'actually', 'basically', 'honestly',
        'to be honest', 'fun fact', 'interestingly',
        'by the way', 'speaking of'
    ]
    
    EMOJIS_PATTERN = re.compile(
        r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF'
        r'\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF'
        r'\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF'
        r'\U00002600-\U000027BF\U0001F1E0-\U0001F1FF]|[:;]-?[()DP]'
    )
    
    def __init__(self, config):
        """
        Initialize validator with configuration.
        
        Args:
            config: Configuration module with response constraints
        """
        self.config = config
        self.max_length = config.DRIVING_MAX_RESPONSE_LENGTH
        self.allow_questions = config.DRIVING_ALLOW_QUESTIONS
        self.allow_emotion = config.DRIVING_ALLOW_EMOTION
    
    def validate_response(
        self, response: str, state: VehicleState
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate response for given vehicle state.
        
        Args:
            response: The AI-generated response text
            state: Current VehicleState
        
        Returns:
            Tuple of (is_valid, sanitized_response, violation_reason)
            - is_valid: True if response passes validation
            - sanitized_response: Cleaned/fallback response if needed
            - violation_reason: Description of why validation failed (or None)
        """
        # PARKED and GARAGE modes have no restrictions
        if state in [VehicleState.PARKED, VehicleState.GARAGE]:
            return True, response, None
        
        # DRIVING mode enforcement
        if state == VehicleState.DRIVING:
            return self._validate_driving_response(response)
        
        # Unknown state - default to strict (DRIVING) rules
        return self._validate_driving_response(response)
    
    def _validate_driving_response(self, response: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate response against DRIVING mode constraints.
        
        Returns:
            (is_valid, sanitized_response, violation_reason)
        """
        if not response or not response.strip():
            # Empty responses are acceptable in DRIVING
            return True, "", None
        
        response = response.strip()
        
        # Check 1: Length limit
        if len(response) > self.max_length:
            return False, "Monitoring.", f"Exceeds max length ({len(response)} > {self.max_length})"
        
        # Check 2: No questions (unless explicitly allowed)
        if not self.allow_questions:
            if '?' in response:
                # Check if it's actually a question (ends with ?)
                if response.rstrip().endswith('?'):
                    return False, "Monitoring.", "Contains question"
        
        # Check 3: No affectionate terms (unless emotion allowed)
        if not self.allow_emotion:
            response_lower = response.lower()
            for term in self.AFFECTIONATE_TERMS:
                if term in response_lower:
                    return False, "Monitoring.", f"Contains affectionate term: {term}"
        
        # Check 4: No narrative markers
        response_lower = response.lower()
        for marker in self.NARRATIVE_MARKERS:
            if marker in response_lower:
                return False, "Monitoring.", f"Contains narrative marker: {marker}"
        
        # Check 5: No emojis/emoticons
        if self.EMOJIS_PATTERN.search(response):
            return False, "Monitoring.", "Contains emoji/emoticon"
        
        # Check 6: Validate preferred format (State → Interpretation → Action)
        # This is a soft check - we don't enforce but we validate structure
        if not self._has_structured_format(response):
            # Allow if it's very short (likely acknowledgment)
            if len(response) > 50:  # Arbitrary threshold
                # Not strictly invalid, but could be improved
                # For now, we'll allow it but flag it
                pass
        
        # All checks passed
        return True, response, None
    
    def _has_structured_format(self, response: str) -> bool:
        """
        Check if response follows the recommended format.
        Format: [Metric/State] → [Interpretation] → [Action]
        
        Returns:
            True if response appears to follow structured format
        """
        # Check for arrow/colon separators (common in structured responses)
        has_arrow = '→' in response or '->' in response
        has_colon = ':' in response
        
        # Check for multiple segments (sentences or phrases)
        segments = len([s for s in response.split('.') if s.strip()])
        has_multiple_segments = segments >= 2
        
        # If very short, assume it's an acknowledgment (valid)
        if len(response) < 30:
            return True
        
        # Structured if it has separators or multiple segments
        return has_arrow or (has_colon and has_multiple_segments)
    
    def sanitize_for_driving(self, response: str) -> str:
        """
        Attempt to sanitize a response for DRIVING mode.
        If sanitization fails, return fallback minimal response.
        
        Args:
            response: Original response
        
        Returns:
            Sanitized or fallback response
        """
        if not response or not response.strip():
            return "Monitoring."
        
        response = response.strip()
        
        # Remove emojis
        response = self.EMOJIS_PATTERN.sub('', response)
        
        # Remove affectionate terms (simple replacement)
        for term in self.AFFECTIONATE_TERMS:
            # Use word boundaries to avoid partial matches
            pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
            response = pattern.sub('', response)
        
        # Remove narrative markers
        for marker in self.NARRATIVE_MARKERS:
            pattern = re.compile(re.escape(marker) + r'[,\s]*', re.IGNORECASE)
            response = pattern.sub('', response)
        
        # Clean up extra whitespace
        response = ' '.join(response.split())
        response = re.sub(r'\s+([,.!])', r'\1', response)  # Fix spacing before punctuation
        
        # Truncate if still too long
        if len(response) > self.max_length:
            # Try to truncate at sentence boundary
            sentences = response.split('.')
            truncated = ""
            for sentence in sentences:
                if len(truncated + sentence + '.') <= self.max_length:
                    truncated += sentence + '.'
                else:
                    break
            
            if truncated and len(truncated.strip()) > 20:  # Reasonable minimum
                response = truncated.strip()
            else:
                # Can't truncate reasonably - use fallback
                return "Monitoring."
        
        # Validate sanitized response
        is_valid, _, _ = self._validate_driving_response(response)
        
        if is_valid:
            return response
        else:
            # Sanitization failed, use fallback
            return "Monitoring."
    
    def get_fallback_response(self, reason: str = "non-essential") -> str:
        """
        Get appropriate fallback response for DRIVING mode.
        
        Args:
            reason: Reason for fallback (non-essential, error, etc.)
        
        Returns:
            Minimal acknowledgment response
        """
        # Provide variety in fallback responses
        fallbacks = {
            "non-essential": "Monitoring.",
            "error": "Acknowledged.",
            "unknown": "Monitoring.",
            "invalid": "Monitoring.",
        }
        
        return fallbacks.get(reason, "Monitoring.")
    
    def format_driving_response(
        self, metric: str, interpretation: str, action: str
    ) -> str:
        """
        Helper to format a proper DRIVING mode response.
        
        Args:
            metric: Current state/metric (e.g., "Coolant: 92°C")
            interpretation: Interpretation (e.g., "Normal range")
            action: Recommended action (e.g., "Continue monitoring")
        
        Returns:
            Formatted response string
        """
        response = f"{metric} → {interpretation} → {action}"
        
        # Ensure it fits length constraint
        if len(response) > self.max_length:
            # Try shorter arrow
            response = f"{metric}: {interpretation}. {action}"
            
            if len(response) > self.max_length:
                # Last resort: truncate action
                available = self.max_length - len(f"{metric}: {interpretation}. ")
                action = action[:available].rstrip()
                response = f"{metric}: {interpretation}. {action}"
        
        return response


# Helper function for easy integration
def create_response_validator(config) -> ResponseValidator:
    """
    Create and return a ResponseValidator instance.
    
    Args:
        config: Configuration module
    
    Returns:
        Initialized ResponseValidator
    """
    return ResponseValidator(config)
