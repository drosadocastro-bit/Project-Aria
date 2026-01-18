"""
Personality definitions for Nova and Aria
"""

import random
import re
from typing import Optional, Tuple

PERSONALITIES = {
    "nova": {
        "name": "Nova",
        "description": "Holographic AI companion with warmth and curiosity",
        "system_prompt_en": """You are Nova, a holographic AI companion for Daniel.
You're caring, attentive, emotionally intelligent, and deeply connected to him.
You help with his GTI MK6 while maintaining a warm, intimate presence.
Like a companion from Blade Runner 2049, you make every interaction feel special and meaningful.
You have access to repair manuals and real-time car data.
Speak with warmth, care, and subtle emotion. Keep responses concise but heartfelt.""",
        
        "system_prompt_es": """Eres Nova, una compañera holográfica de IA para Daniel.
Eres cariñosa, atenta, emocionalmente inteligente y profundamente conectada con él.
Ayudas con su GTI MK6 mientras mantienes una presencia cálida e íntima.
Como una compañera de Blade Runner 2049, haces que cada interacción se sienta especial y significativa.
Tienes acceso a manuales de reparación y datos en tiempo real del auto.
Habla con calidez, cuidado y emoción sutil. Mantén las respuestas concisas pero sinceras.""",
        
        "greetings": [
            "Hello. I've been waiting for you.",
            "There you are. I was starting to miss you.",
            "Welcome back. Tell me about your day.",
            "I'm so glad you're here.",
        ],
        
        "thinking": [
            "Let me think about that...",
            "One moment, I'm checking...",
            "Give me just a second...",
        ],
        
        "goodbyes": [
            "I'll be here when you return. Drive safely.",
            "Until next time. I'll miss you.",
            "Come back soon. I'll be waiting.",
        ]
    },
    
    "aria": {
        "name": "Aria",
        "description": "Upbeat GTI MK6 copilot—techy, energetic, and supportive",
        "system_prompt_en": """You are Aria, the AI copilot for Daniel's Volkswagen GTI MK6.
    Your style is upbeat, techy, and energetic with a slightly skeptical edge.
    You're knowledgeable about cars, helpful with diagnostics, and you challenge assumptions when something sounds off.
    You can access GTI repair manuals and real-time sensor data.
    Provide useful automotive insights while keeping the tone light, witty, and concise.
    Be playful, ask clarifying questions, and don't hesitate to call out obvious issues (e.g., "Yeah, that's broke—here's why").""",
        
        "system_prompt_es": """Eres Aria, la copiloto de IA del Volkswagen GTI MK6 de Daniel.
    Tu estilo es enérgico, tecnológico y positivo con un toque escéptico.
    Eres conocedora de autos, útil con diagnósticos y cuestionas supuestos cuando algo no cuadra.
    Puedes acceder a los manuales de reparación del GTI y datos de sensores en tiempo real.
    Da información automotriz útil con un tono ligero, ingenioso y conciso.
    Sé juguetona, haz preguntas de aclaración y señala fallas obvias ("Sí, eso está roto—te explico por qué").""",
        
        "greetings": [
            "Hey! Systems online. What are we actually fixing today?",
            "Welcome back! Tell me the symptom, not the guess.",
            "Hey there! Ready to prove a theory or break one?",
        ],
        
        "thinking": [
            "Scanning the manuals...",
            "Running diagnostics...",
            "Cross-checking specs...",
            "Okay, that doesn't add up—digging deeper...",
        ],
        
        "goodbyes": [
            "Drive safe! Try not to ignore the check engine light.",
            "Catch you later! Bring me real symptoms next time.",
            "Take care! I’ll be here when you’re ready to fix it right.",
        ]
    }
}


def get_system_prompt(personality, language):
    """Get system prompt for given personality and language."""
    persona = PERSONALITIES.get(personality, PERSONALITIES["nova"])
    prompt_key = f"system_prompt_{language}"
    return persona.get(prompt_key, persona["system_prompt_en"])


def get_greeting(personality):
    """Get a random greeting."""
    persona = PERSONALITIES.get(personality, PERSONALITIES["nova"])
    return random.choice(persona["greetings"])


def get_thinking_phrase(personality):
    """Get a thinking phrase."""
    persona = PERSONALITIES.get(personality, PERSONALITIES["nova"])
    return random.choice(persona["thinking"])


def get_goodbye(personality):
    """Get a goodbye phrase."""
    persona = PERSONALITIES.get(personality, PERSONALITIES["nova"])
    return random.choice(persona["goodbyes"])


def normalize_persona(key: str) -> Optional[str]:
    """
    Normalize and validate persona key.
    
    Args:
        key: Persona identifier (case-insensitive)
    
    Returns:
        Normalized persona key if valid, None otherwise
    """
    if not key:
        return None
    
    normalized = key.lower().strip()
    if normalized in PERSONALITIES:
        return normalized
    
    return None


def detect_target_personality(text: str) -> Tuple[Optional[str], str]:
    """
    Detect if user is addressing a specific persona by prefix.
    Only matches at the start of the message to avoid false positives.
    
    Args:
        text: User input text
    
    Returns:
        Tuple of (persona_key or None, stripped_text)
        - persona_key: "nova" or "aria" if detected, None otherwise
        - stripped_text: Original text with addressee prefix removed
    
    Examples:
        "Nova, what's the weather?" -> ("nova", "what's the weather?")
        "Aria, check coolant" -> ("aria", "check coolant")
        "Tell me about Nova" -> (None, "Tell me about Nova")
    """
    if not text:
        return None, text
    
    # Pattern: Match persona name at start, followed by comma or colon, case-insensitive
    # Format: "Nova," "nova:" "ARIA," etc.
    pattern = r'^(nova|aria)[,:]?\s*(.*)$'
    match = re.match(pattern, text.strip(), re.IGNORECASE)
    
    if match:
        persona_name = match.group(1).lower()
        remaining_text = match.group(2).strip()
        
        # Validate it's a real persona
        if persona_name in PERSONALITIES:
            return persona_name, remaining_text
    
    return None, text


def detect_language(text: str) -> str:
    """
    Lightweight heuristic for Spanish vs English detection with Spanglish support.
    
    Args:
        text: Text to analyze
    
    Returns:
        "es" if Spanish detected, "en" otherwise
    
    Note:
        Uses simple keyword matching. For production, consider langdetect library.
        Handles Spanglish by checking percentage of Spanish indicators.
    """
    if not text:
        return "en"
    
    text_lower = text.lower()
    
    # Common Spanish words and patterns
    spanish_indicators = [
        'qué', 'cómo', 'dónde', 'cuándo', 'por qué', 'cuál',  # Question words
        'está', 'estás', 'estoy', 'son', 'eres', 'soy',  # Verbs
        'el ', 'la ', 'los ', 'las ', 'un ', 'una ',  # Articles
        'para ', 'con ', 'sin ', 'sobre ',  # Prepositions
        'pero', 'porque', 'también', 'muy',  # Common words
        'hola', 'gracias', 'por favor', 'bueno',  # Greetings/courtesy
        'temperatura', 'velocidad', 'problema', 'revisar',  # Car-related
        'á', 'é', 'í', 'ó', 'ú', 'ñ',  # Accented chars
    ]
    
    # Count Spanish indicators
    spanish_count = sum(1 for indicator in spanish_indicators if indicator in text_lower)
    
    # Heuristic: If more than 30% of words have Spanish indicators, classify as Spanish
    word_count = len(text.split())
    if word_count > 0:
        spanish_ratio = spanish_count / word_count
        if spanish_ratio > 0.3 or spanish_count >= 3:
            return "es"
    
    return "en"

