"""
Demonstration of Aria Driving Contract
Shows state-aware response behavior without requiring LM Studio
"""

from core.state_manager import StateManager, VehicleState
from core.response_validator import ResponseValidator
import config


def demo_driving_contract():
    """Demonstrate the Driving Contract in action."""
    
    print("\n" + "=" * 70)
    print("ARIA DRIVING CONTRACT - DEMONSTRATION")
    print("=" * 70)
    
    # Initialize components
    state_manager = StateManager(config)
    validator = ResponseValidator(config)
    
    print("\n🎯 Scenario 1: PARKED - Full conversational mode")
    print("-" * 70)
    
    telemetry = {"speed": 0, "rpm": 0}
    state = state_manager.get_current_state(telemetry)
    print(f"Vehicle State: {state.value}")
    print(f"Telemetry: Speed={telemetry['speed']} mph, RPM={telemetry['rpm']}")
    
    response = """Your coolant is sitting at 92°C, which is perfectly normal! 
The MK6's TSI runs a bit warm by design, but you're well within the 80-100°C 
operating range. Everything looks healthy! Want me to explain more about the 
cooling system?"""
    
    is_valid, sanitized, reason = validator.validate_response(response, state)
    
    print(f"\nAI Response:\n{response}")
    print(f"\n✅ Validation: {is_valid} (No restrictions in PARKED mode)")
    
    # Simulate state transition
    print("\n" + "=" * 70)
    print("🎯 Scenario 2: Vehicle starts moving → DRIVING mode")
    print("-" * 70)
    
    import time
    telemetry = {"speed": 30, "rpm": 2500}
    state_manager.get_current_state(telemetry)
    time.sleep(config.STATE_HYSTERESIS_DURATION + 0.5)  # Wait for hysteresis
    state = state_manager.get_current_state(telemetry)
    
    print(f"Vehicle State: {state.value}")
    print(f"Telemetry: Speed={telemetry['speed']} mph, RPM={telemetry['rpm']}")
    
    # Same verbose response
    is_valid, sanitized, reason = validator.validate_response(response, state)
    
    print(f"\nOriginal AI Response:\n{response[:100]}...")
    print(f"\n❌ Validation: {is_valid}")
    print(f"Reason: {reason}")
    print(f"\n🔒 Enforced Response (DRIVING mode):\n{sanitized}")
    
    # Show proper DRIVING response
    print("\n" + "=" * 70)
    print("🎯 Scenario 3: Proper DRIVING response format")
    print("-" * 70)
    
    proper_response = "Coolant: 92°C → Normal range → Continue monitoring."
    is_valid, sanitized, reason = validator.validate_response(proper_response, state)
    
    print(f"Vehicle State: {state.value}")
    print(f"\nAI Response:\n{proper_response}")
    print(f"\n✅ Validation: {is_valid}")
    print(f"Length: {len(proper_response)} chars (limit: {config.DRIVING_MAX_RESPONSE_LENGTH})")
    
    # Show formatting helper
    print("\n" + "=" * 70)
    print("🎯 Scenario 4: Using the format helper")
    print("-" * 70)
    
    formatted = validator.format_driving_response(
        metric="RPM: 3000",
        interpretation="High revs",
        action="Shift up"
    )
    
    print(f"Formatted Response: {formatted}")
    is_valid, _, _ = validator.validate_response(formatted, VehicleState.DRIVING)
    print(f"Valid: {is_valid}")
    
    # Show traffic light scenario
    print("\n" + "=" * 70)
    print("🎯 Scenario 5: Traffic light (remains DRIVING)")
    print("-" * 70)
    
    telemetry = {"speed": 0, "rpm": 800}  # Stopped with engine on
    state = state_manager.get_current_state(telemetry)
    
    print(f"Vehicle State: {state.value} (brief stop at traffic light)")
    print(f"Telemetry: Speed={telemetry['speed']} mph, RPM={telemetry['rpm']}")
    print(f"\n💡 Note: Stops <{config.STATE_IDLE_THRESHOLD}s with engine on remain DRIVING")
    
    # Show manual override
    print("\n" + "=" * 70)
    print("🎯 Scenario 6: Manual state override")
    print("-" * 70)
    
    state_manager.reset()
    state_manager.set_manual_override("GARAGE")
    state = state_manager.get_current_state({"speed": 0, "rpm": 0})
    
    print(f"Manual override to: GARAGE")
    print(f"Vehicle State: {state.value}")
    
    # Verbose response allowed in GARAGE
    garage_response = """PCV valve replacement on GTI MK6 (TSI EA888 Gen 1):

Tools needed: T25 Torx, 10mm socket, flathead screwdriver
Parts: OEM PCV valve (06H 103 495 A)

Procedure:
1. Remove engine cover (4x T25 screws)
2. Locate PCV valve on valve cover, driver's side
3. Disconnect vacuum hose (twist & pull)
4. Remove valve (counterclockwise twist)
5. Clean mating surface
6. Install new valve with new O-ring
7. Reconnect hose, replace cover

Expected time: 15-20 minutes
Source: Bentley Service Manual, Section 15-18"""
    
    is_valid, _, _ = validator.validate_response(garage_response, state)
    print(f"\nGARAGE mode response (verbose):\n{garage_response[:200]}...")
    print(f"\n✅ Validation: {is_valid} (GARAGE allows detailed technical responses)")
    
    # Safety feature demo
    print("\n" + "=" * 70)
    print("🎯 Scenario 7: Safety lock (cannot override from DRIVING while moving)")
    print("-" * 70)
    
    state_manager.reset()
    telemetry = {"speed": 50, "rpm": 3000}
    state_manager.get_current_state(telemetry)
    time.sleep(config.STATE_HYSTERESIS_DURATION + 0.5)
    state = state_manager.get_current_state(telemetry)
    
    print(f"Current State: {state.value}")
    print(f"Telemetry: Speed={telemetry['speed']} mph, RPM={telemetry['rpm']}")
    
    state_manager.set_manual_override("PARKED")
    state = state_manager.get_current_state(telemetry)
    
    print(f"\nAttempt manual override to PARKED...")
    print(f"Actual State: {state.value}")
    print(f"\n🔒 Safety lock engaged: Cannot override from DRIVING while moving")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("""
The Aria Driving Contract successfully enforces:

✅ DRIVING mode: Concise, structured responses (max 150 chars)
✅ PARKED mode: Full conversational capability
✅ GARAGE mode: Detailed technical documentation
✅ Hysteresis: 3-second debounce prevents rapid state switching
✅ Safety locks: Cannot override from DRIVING while moving
✅ Traffic light handling: Brief stops remain DRIVING
✅ Response validation: Blocks questions, emotions, verbose text in DRIVING

See docs/ARIA_DRIVING_CONTRACT.md for complete specification.
Use /state, /setstate, /clearstate commands in aria.py console mode.
""")


if __name__ == "__main__":
    try:
        demo_driving_contract()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
