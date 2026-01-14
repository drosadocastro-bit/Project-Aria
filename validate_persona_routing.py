#!/usr/bin/env python3
"""
Manual validation script for persona routing implementation.
Tests core functionality without requiring LM Studio.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("  PERSONA ROUTING - VALIDATION SCRIPT")
print("=" * 60)
print()

# Test 1: Import all modules
print("Test 1: Importing modules...")
try:
    from core.personality import (
        detect_target_personality,
        normalize_persona,
        detect_language,
        PERSONALITIES,
        get_system_prompt,
        get_greeting
    )
    from core.tts_router import get_voice_config, get_persona_ui_config
    print("✅ All imports successful")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

print()

# Test 2: Verify PERSONALITIES dict
print("Test 2: Verifying PERSONALITIES dictionary...")
try:
    assert 'nova' in PERSONALITIES, "nova not found in PERSONALITIES"
    assert 'aria' in PERSONALITIES, "aria not found in PERSONALITIES"
    assert 'joi' not in PERSONALITIES, "joi should be removed from PERSONALITIES"
    
    for persona in ['nova', 'aria']:
        assert 'name' in PERSONALITIES[persona], f"{persona} missing 'name'"
        assert 'system_prompt_en' in PERSONALITIES[persona], f"{persona} missing 'system_prompt_en'"
        assert 'system_prompt_es' in PERSONALITIES[persona], f"{persona} missing 'system_prompt_es'"
        assert 'greetings' in PERSONALITIES[persona], f"{persona} missing 'greetings'"
    
    print("✅ PERSONALITIES structure valid")
    print(f"   - Nova: {PERSONALITIES['nova']['name']}")
    print(f"   - Aria: {PERSONALITIES['aria']['name']}")
except AssertionError as e:
    print(f"❌ {e}")
    sys.exit(1)

print()

# Test 3: Persona detection
print("Test 3: Testing persona prefix detection...")
test_cases = [
    ("Nova, what's the weather?", "nova", "what's the weather?"),
    ("Aria, check coolant", "aria", "check coolant"),
    ("nova: hello", "nova", "hello"),
    ("ARIA: status", "aria", "status"),
    ("Tell me about Nova", None, "Tell me about Nova"),
    ("What about Aria?", None, "What about Aria?"),
    ("", None, ""),
]

all_passed = True
for input_text, expected_persona, expected_text in test_cases:
    persona, text = detect_target_personality(input_text)
    if persona == expected_persona and text == expected_text:
        print(f"   ✅ '{input_text[:30]}...' -> persona={persona}")
    else:
        print(f"   ❌ '{input_text}' -> Expected ({expected_persona}, '{expected_text}'), got ({persona}, '{text}')")
        all_passed = False

if all_passed:
    print("✅ All prefix detection tests passed")
else:
    print("❌ Some prefix detection tests failed")
    sys.exit(1)

print()

# Test 4: Language detection
print("Test 4: Testing language detection...")
lang_tests = [
    ("What is the coolant temperature?", "en"),
    ("How fast am I going?", "en"),
    ("¿Qué temperatura tiene el refrigerante?", "es"),
    ("¿Cómo está el motor?", "es"),
    ("Hola, ¿cómo estás?", "es"),
    ("El coche está muy rápido", "es"),
    ("The car is running", "en"),
]

all_passed = True
for text, expected_lang in lang_tests:
    lang = detect_language(text)
    if lang == expected_lang:
        print(f"   ✅ '{text[:40]}...' -> {lang}")
    else:
        print(f"   ❌ '{text}' -> Expected {expected_lang}, got {lang}")
        all_passed = False

if all_passed:
    print("✅ All language detection tests passed")
else:
    print("❌ Some language detection tests failed")
    sys.exit(1)

print()

# Test 5: Persona normalization
print("Test 5: Testing persona normalization...")
norm_tests = [
    ("nova", "nova"),
    ("NOVA", "nova"),
    ("aria", "aria"),
    ("Aria", "aria"),
    ("  nova  ", "nova"),
    ("joi", None),
    ("invalid", None),
    ("", None),
]

all_passed = True
for input_key, expected in norm_tests:
    result = normalize_persona(input_key)
    if result == expected:
        print(f"   ✅ '{input_key}' -> {result}")
    else:
        print(f"   ❌ '{input_key}' -> Expected {expected}, got {result}")
        all_passed = False

if all_passed:
    print("✅ All normalization tests passed")
else:
    print("❌ Some normalization tests failed")
    sys.exit(1)

print()

# Test 6: System prompts
print("Test 6: Testing system prompt retrieval...")
try:
    for persona in ['nova', 'aria']:
        for lang in ['en', 'es']:
            prompt = get_system_prompt(persona, lang)
            assert len(prompt) > 50, f"Prompt too short for {persona}/{lang}"
            assert persona.upper() in prompt or PERSONALITIES[persona]['name'] in prompt, f"Persona name not in prompt"
    
    print("✅ System prompts valid for all persona/language combinations")
except AssertionError as e:
    print(f"❌ {e}")
    sys.exit(1)

print()

# Test 7: UI configuration
print("Test 7: Testing UI configuration...")
try:
    for persona in ['nova', 'aria']:
        ui_config = get_persona_ui_config(persona)
        assert 'theme' in ui_config, f"Missing 'theme' for {persona}"
        assert 'accent' in ui_config, f"Missing 'accent' for {persona}"
        assert 'glow' in ui_config, f"Missing 'glow' for {persona}"
        assert 'gradient' in ui_config, f"Missing 'gradient' for {persona}"
        print(f"   ✅ {persona}: theme={ui_config['theme']}, accent={ui_config['accent']}")
    
    print("✅ UI configuration valid")
except AssertionError as e:
    print(f"❌ {e}")
    sys.exit(1)

print()

# Test 8: Voice configuration
print("Test 8: Testing voice configuration...")
try:
    for persona in ['nova', 'aria']:
        for lang in ['en', 'es']:
            voice_config = get_voice_config(persona, lang)
            assert 'voice_id' in voice_config, f"Missing 'voice_id'"
            assert 'backend' in voice_config, f"Missing 'backend'"
            assert 'lang' in voice_config, f"Missing 'lang'"
            assert 'persona' in voice_config, f"Missing 'persona'"
            assert voice_config['persona'] == persona, f"Persona mismatch"
            assert voice_config['lang'] == lang, f"Language mismatch"
    
    print("✅ Voice configuration structure valid")
except AssertionError as e:
    print(f"❌ {e}")
    sys.exit(1)

print()

# Test 9: Per-turn routing simulation
print("Test 9: Simulating per-turn routing logic...")
default_personality = "nova"

conversation = [
    "Nova, what's quantum mechanics?",
    "Aria, check the oil temp",
    "What about the coolant?",  # Should use default (nova)
    "/nova",  # Explicit switch (simulated)
    "Tell me about space",  # Uses nova
]

print("   Simulating conversation:")
for i, user_input in enumerate(conversation, 1):
    if user_input.startswith("/"):
        # Explicit switch command
        if user_input == "/nova":
            default_personality = "nova"
            print(f"   {i}. User: {user_input}")
            print(f"      → Switched default to nova")
        elif user_input == "/aria":
            default_personality = "aria"
            print(f"   {i}. User: {user_input}")
            print(f"      → Switched default to aria")
    else:
        # Detect per-turn persona
        target_persona, stripped_text = detect_target_personality(user_input)
        response_persona = target_persona if target_persona else default_personality
        
        print(f"   {i}. User: {user_input}")
        if target_persona:
            print(f"      → Routing to {response_persona} (per-turn)")
        else:
            print(f"      → Using default persona: {response_persona}")

print("✅ Per-turn routing simulation successful")

print()
print("=" * 60)
print("  ✅ ALL VALIDATION TESTS PASSED")
print("=" * 60)
print()
print("Implementation is ready for manual testing with LM Studio:")
print("  1. Console mode: python aria.py --mode console --personality nova")
print("  2. Avatar mode: python aria.py --mode avatar")
print("  3. Open static/nova_avatar.html in browser")
print()
