"""
Test script for Aria Driving Contract implementation
Tests state manager and response validator functionality
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from core.state_manager import StateManager, VehicleState
from core.response_validator import ResponseValidator
import config


def test_state_manager():
    """Test state manager state transitions."""
    print("=" * 60)
    print("Testing State Manager")
    print("=" * 60)
    
    sm = StateManager(config)
    
    # Test 1: Initial state (no telemetry)
    print("\n1. Initial state (no telemetry):")
    state = sm.get_current_state(None)
    print(f"   State: {state.value} (Expected: PARKED)")
    assert state == VehicleState.PARKED, "Initial state should be PARKED"
    
    # Test 2: PARKED → DRIVING transition
    print("\n2. PARKED → DRIVING transition:")
    telemetry = {"speed": 0, "rpm": 800}  # Engine on, stopped
    state = sm.get_current_state(telemetry)
    print(f"   Speed=0, RPM=800: {state.value} (Expected: PARKED)")
    
    # Need to wait for hysteresis duration (3 seconds in config)
    import time
    telemetry = {"speed": 10, "rpm": 2000}  # Moving
    state = sm.get_current_state(telemetry)
    print(f"   Speed=10, RPM=2000 (first call): {state.value}")
    
    # Wait for hysteresis to pass
    time.sleep(config.STATE_HYSTERESIS_DURATION + 0.5)
    
    state = sm.get_current_state(telemetry)
    print(f"   Speed=10, RPM=2000 (after {config.STATE_HYSTERESIS_DURATION}s): {state.value} (Expected: DRIVING)")
    assert state == VehicleState.DRIVING, "Should transition to DRIVING when moving"
    
    # Test 3: Traffic light scenario (remain DRIVING)
    print("\n3. Traffic light scenario (brief stop, engine on):")
    telemetry = {"speed": 0, "rpm": 800}  # Stopped at light
    state = sm.get_current_state(telemetry)
    print(f"   Speed=0, RPM=800 (brief): {state.value} (Expected: DRIVING)")
    # Note: Will be DRIVING due to short duration
    
    # Test 4: Manual override
    print("\n4. Manual override:")
    sm.set_manual_override("GARAGE")
    # Override won't work while moving (safety feature)
    state = sm.get_current_state({"speed": 10, "rpm": 2000})
    print(f"   Manual override to GARAGE (moving): {state.value} (Expected: DRIVING - safety lock)")
    assert state == VehicleState.DRIVING, "Should not override from DRIVING while moving (safety)"
    
    # Override should work when stopped
    state = sm.get_current_state({"speed": 0, "rpm": 0})
    print(f"   Manual override to GARAGE (stopped): {state.value} (Expected: GARAGE)")
    assert state == VehicleState.GARAGE, "Manual override should work when stopped"
    
    sm.set_manual_override(None)
    print("   Manual override cleared")
    
    # Test 5: State info
    print("\n5. State information:")
    info = sm.get_state_info({"speed": 0, "rpm": 0})
    print(f"   State: {info['state']}")
    print(f"   Time in state: {info['time_in_state']:.2f}s")
    print(f"   Manual override: {info['manual_override']}")
    
    print("\n✅ State Manager tests passed!\n")


def test_response_validator():
    """Test response validator for DRIVING mode."""
    print("=" * 60)
    print("Testing Response Validator")
    print("=" * 60)
    
    rv = ResponseValidator(config)
    
    # Test 1: Valid DRIVING response
    print("\n1. Valid DRIVING response:")
    response = "Coolant: 92°C → Normal range → Continue monitoring."
    is_valid, sanitized, reason = rv.validate_response(response, VehicleState.DRIVING)
    print(f"   Response: {response}")
    print(f"   Valid: {is_valid} (Expected: True)")
    assert is_valid, "Valid DRIVING response should pass"
    
    # Test 2: Too long DRIVING response
    print("\n2. Too long DRIVING response:")
    response = "Your coolant temperature is currently sitting at 92 degrees Celsius, which is perfectly normal and healthy for your GTI MK6. The TSI engine runs a bit warm by design, so no worries!"
    is_valid, sanitized, reason = rv.validate_response(response, VehicleState.DRIVING)
    print(f"   Response: {response[:50]}...")
    print(f"   Valid: {is_valid} (Expected: False)")
    print(f"   Sanitized: {sanitized}")
    print(f"   Reason: {reason}")
    assert not is_valid, "Too long response should fail"
    assert sanitized == "Monitoring.", "Should use fallback"
    
    # Test 3: Question in DRIVING mode
    print("\n3. Question in DRIVING mode:")
    response = "Temperature is 92°C. Want me to monitor it?"
    is_valid, sanitized, reason = rv.validate_response(response, VehicleState.DRIVING)
    print(f"   Response: {response}")
    print(f"   Valid: {is_valid} (Expected: False)")
    print(f"   Reason: {reason}")
    assert not is_valid, "Question should fail in DRIVING"
    
    # Test 4: Affectionate term in DRIVING mode
    print("\n4. Affectionate term in DRIVING mode:")
    response = "Temperature looks good, love. Keep driving safe!"
    is_valid, sanitized, reason = rv.validate_response(response, VehicleState.DRIVING)
    print(f"   Response: {response}")
    print(f"   Valid: {is_valid} (Expected: False)")
    print(f"   Reason: {reason}")
    assert not is_valid, "Affectionate term should fail in DRIVING"
    
    # Test 5: Valid PARKED response (no restrictions)
    print("\n5. Valid PARKED response (no restrictions):")
    response = "Your coolant is sitting at 92°C, which is perfectly normal! The MK6's TSI runs a bit warm by design. Want me to explain more about the cooling system?"
    is_valid, sanitized, reason = rv.validate_response(response, VehicleState.PARKED)
    print(f"   Response: {response[:50]}...")
    print(f"   Valid: {is_valid} (Expected: True)")
    assert is_valid, "PARKED mode should allow longer, conversational responses"
    
    # Test 6: Sanitization
    print("\n6. Response sanitization:")
    response = "Actually, you know, the coolant temp is 92°C which is totally normal! 😊"
    sanitized = rv.sanitize_for_driving(response)
    print(f"   Original: {response}")
    print(f"   Sanitized: {sanitized}")
    assert "Actually" not in sanitized, "Should remove narrative markers"
    assert "you know" not in sanitized, "Should remove narrative markers"
    assert "😊" not in sanitized, "Should remove emojis"
    
    # Test 7: Format helper
    print("\n7. Format helper:")
    formatted = rv.format_driving_response(
        "Coolant: 92°C",
        "Normal range",
        "Continue monitoring"
    )
    print(f"   Formatted: {formatted}")
    assert "→" in formatted or ":" in formatted, "Should be formatted"
    assert len(formatted) <= config.DRIVING_MAX_RESPONSE_LENGTH, "Should fit length limit"
    
    print("\n✅ Response Validator tests passed!\n")


def test_integration():
    """Test integration of state manager and validator."""
    print("=" * 60)
    print("Testing Integration")
    print("=" * 60)
    
    import time
    
    sm = StateManager(config)
    rv = ResponseValidator(config)
    
    print("\n1. DRIVING scenario:")
    telemetry = {"speed": 60, "rpm": 3000}
    # Need to wait for hysteresis
    sm.get_current_state(telemetry)
    time.sleep(config.STATE_HYSTERESIS_DURATION + 0.5)
    state = sm.get_current_state(telemetry)
    
    print(f"   Telemetry: Speed={telemetry['speed']} mph, RPM={telemetry['rpm']}")
    print(f"   State: {state.value}")
    
    # Simulate AI response
    ai_response = "Hey! Your coolant temp is looking really good at 92°C. Everything is running smoothly, just keep an eye on it for me, okay?"
    is_valid, sanitized, reason = rv.validate_response(ai_response, state)
    
    print(f"   AI Response: {ai_response[:50]}...")
    print(f"   Valid: {is_valid}")
    print(f"   Sanitized: {sanitized}")
    
    assert not is_valid, "Should reject verbose response in DRIVING"
    
    print("\n2. PARKED scenario:")
    telemetry = {"speed": 0, "rpm": 0}
    sm.reset()  # Reset to ensure clean state
    state = sm.get_current_state(telemetry)
    print(f"   Telemetry: Speed={telemetry['speed']} mph, RPM={telemetry['rpm']}")
    print(f"   State: {state.value}")
    
    is_valid, sanitized, reason = rv.validate_response(ai_response, state)
    
    print(f"   AI Response: {ai_response[:50]}...")
    print(f"   Valid: {is_valid}")
    
    assert is_valid, "Should accept verbose response in PARKED"
    
    print("\n✅ Integration tests passed!\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("ARIA DRIVING CONTRACT - TEST SUITE")
    print("=" * 60 + "\n")
    
    try:
        test_state_manager()
        test_response_validator()
        test_integration()
        
        print("=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\nThe Aria Driving Contract implementation is working correctly!")
        print("\nNext steps:")
        print("1. Run aria.py to test in console mode")
        print("2. Use /state command to check vehicle state")
        print("3. Use /setstate DRIVING to test DRIVING mode responses")
        print("4. Connect OBD-II for automatic state detection")
        print("\nSee docs/ARIA_DRIVING_CONTRACT.md for full specification.")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
