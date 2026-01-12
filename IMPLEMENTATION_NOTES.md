# Aria Driving Contract - Implementation Notes

## Overview

This document provides technical notes for the Aria Driving Contract implementation completed on 2026-01-12.

## What Was Implemented

The Aria Driving Contract (Copilot Covenant) is a safety-first operational framework that adapts Aria's behavior based on vehicle state. The implementation includes:

### 1. State Management System
**File**: `core/state_manager.py`

- **VehicleState enum**: Three operational states (PARKED, DRIVING, GARAGE)
- **StateManager class**: Manages state transitions with hysteresis
- **OBD integration**: Uses real-time telemetry (speed, RPM) for state detection
- **Hysteresis logic**: 3-second debounce prevents rapid state switching
- **Traffic light handling**: Brief stops with engine running remain in DRIVING state
- **Manual override**: Supports manual state override with safety locks

**Key Safety Features**:
- Cannot override FROM DRIVING while vehicle is moving (speed > 0)
- Conservative default: PARKED when telemetry unavailable
- Configurable thresholds for all state transitions

### 2. Response Validation System
**File**: `core/response_validator.py`

- **ResponseValidator class**: Enforces DRIVING mode constraints
- **Length validation**: Maximum 150 characters in DRIVING mode
- **Pattern detection**: Blocks questions, affectionate terms, narrative markers, emojis
- **Format enforcement**: Encourages `[Metric] → [Interpretation] → [Action]` structure
- **Sanitization**: Attempts to clean responses before fallback
- **Format helper**: Utility function to generate compliant DRIVING responses

**Prohibited in DRIVING**:
- Questions (ending with `?`)
- Affectionate terms (love, dear, honey, etc.)
- Narrative markers (actually, you know, basically, etc.)
- Emojis and emoticons
- Responses exceeding 150 characters

### 3. Integration with Aria
**File**: `aria.py` (modified)

- Imported state_manager and response_validator modules
- Added state detection before LLM query
- Modified system prompt for DRIVING mode (adds safety instructions)
- Reduced max_tokens from 512 to 100 in DRIVING mode
- Added response validation after LLM generation
- Automatic sanitization/fallback for invalid DRIVING responses

**New Console Commands**:
- `/state` - Display current vehicle state and diagnostic info
- `/setstate [STATE]` - Manually override state (PARKED, GARAGE, DRIVING)
- `/clearstate` - Clear manual override, return to automatic detection

### 4. Configuration
**Files**: `config.py`, `config.example.py`

New configuration parameters:
```python
STATE_SPEED_THRESHOLD = 5.0          # mph
STATE_IDLE_THRESHOLD = 10.0          # seconds
STATE_GARAGE_TIMEOUT = 1800          # seconds (30 min)
STATE_HYSTERESIS_DURATION = 3.0      # seconds
DRIVING_MAX_RESPONSE_LENGTH = 150    # characters
DRIVING_ALLOW_QUESTIONS = False
DRIVING_ALLOW_EMOTION = False
STATE_MANUAL_OVERRIDE_ENABLED = True
STATE_MANUAL_OVERRIDE_VALUE = None
```

### 5. Documentation
**Files**: `docs/ARIA_DRIVING_CONTRACT.md`, `README.md`

- Complete operational specification (219 lines)
- State definitions with examples
- Transition rules and hysteresis explanation
- Response format requirements
- Safety philosophy
- Implementation notes

### 6. Testing & Validation
**Files**: `test_driving_contract.py`, `demo_driving_contract.py`, `test_driving.bat`

- **Unit tests**: State manager, response validator
- **Integration tests**: Full system behavior
- **Demonstration script**: 7 interactive scenarios
- **Windows batch runner**: Easy testing on Windows
- **All tests passing**: 100% success rate

## Technical Architecture

```
User Input
    ↓
OBD Telemetry → StateManager.get_current_state()
    ↓                           ↓
    ├─ Speed >= 5 mph → DRIVING
    ├─ Speed = 0, Engine off → PARKED
    └─ Manual override or timeout → GARAGE
    ↓
State-Modified System Prompt
    ↓
LLM (LM Studio) with reduced tokens in DRIVING
    ↓
Response
    ↓
ResponseValidator.validate_response(response, state)
    ↓
    ├─ DRIVING: Enforce constraints, sanitize/fallback
    ├─ PARKED: No restrictions
    └─ GARAGE: No restrictions
    ↓
Output to User
```

## State Transition Logic

### PARKED → DRIVING
- Speed >= 5 mph for >= 3 seconds (hysteresis)
- Engine running (RPM > 0)

### DRIVING → PARKED
- Speed = 0 mph AND (engine off OR stopped > 10 seconds)
- Brief stops (< 10s) with engine on remain DRIVING

### PARKED → GARAGE
- Manual override OR
- Sustained PARKED state > 30 minutes

### GARAGE → PARKED/DRIVING
- Manual override only (no automatic exit from GARAGE)

## Usage Examples

### Testing State Transitions
```python
from core.state_manager import StateManager
import config

sm = StateManager(config)

# Vehicle starts moving
telemetry = {"speed": 30, "rpm": 2500}
state = sm.get_current_state(telemetry)
# After hysteresis: state = VehicleState.DRIVING

# Stopped at traffic light (brief, engine on)
telemetry = {"speed": 0, "rpm": 800}
state = sm.get_current_state(telemetry)
# state = VehicleState.DRIVING (still)

# Parked (engine off)
telemetry = {"speed": 0, "rpm": 0}
state = sm.get_current_state(telemetry)
# state = VehicleState.PARKED
```

### Testing Response Validation
```python
from core.response_validator import ResponseValidator
from core.state_manager import VehicleState
import config

rv = ResponseValidator(config)

# Valid DRIVING response
response = "Coolant: 92°C → Normal range → Continue monitoring."
is_valid, sanitized, reason = rv.validate_response(response, VehicleState.DRIVING)
# is_valid = True

# Invalid DRIVING response (too long, has question)
response = "Your coolant temp looks great! Everything is running smoothly. Want me to explain more?"
is_valid, sanitized, reason = rv.validate_response(response, VehicleState.DRIVING)
# is_valid = False, sanitized = "Monitoring."
```

### Console Mode
```bash
$ python aria.py

💜 JOI: Hello. I've been waiting for you.

You: /state
🚦 Vehicle State: PARKED
   Time in state: 12.3s
   Manual override: False
   Telemetry: Not available

You: /setstate DRIVING
🔧 Manual override set to: DRIVING

You: What's my coolant temp?
💜 JOI: Monitoring.
# (If no OBD connected, falls back to minimal response)
```

## Known Limitations

1. **OBD Dependency**: State detection requires functional OBD-II connection. Without it, defaults to PARKED.
2. **Hysteresis Timing**: 3-second delay means state changes aren't instantaneous (by design for safety).
3. **LLM Compliance**: The system prompts the LLM to follow DRIVING rules, but validation catches non-compliance. However, some LLMs may struggle with strict formatting requirements.
4. **Parking Brake Detection**: Currently not implemented (OBD-II doesn't typically expose this). Future enhancement possible with CAN bus integration.

## Future Enhancements

1. **CAN Bus Integration**: Direct access to parking brake, gear position for more accurate state detection
2. **Learning Mode**: Adapt DRIVING response strictness based on user preferences over time
3. **Audio Cues**: Audible state transitions (e.g., chime when entering DRIVING mode)
4. **Location-Based Override**: Automatically enter GARAGE mode when at home (GPS-based)
5. **Advanced Sanitization**: ML-based response rewriting instead of simple fallback

## Testing Checklist

Before deployment, verify:
- [ ] `python test_driving_contract.py` passes all tests
- [ ] `python demo_driving_contract.py` runs without errors
- [ ] `python aria.py` imports successfully
- [ ] OBD-II connection functional (if using automatic state detection)
- [ ] `/state`, `/setstate`, `/clearstate` commands work in console mode
- [ ] DRIVING mode enforces 150-char limit
- [ ] PARKED mode allows verbose responses
- [ ] Manual override safety lock prevents DRIVING→PARKED while moving

## Maintenance Notes

### Adjusting Thresholds
Edit `config.py`:
- `STATE_SPEED_THRESHOLD`: Increase for higher speed before DRIVING mode
- `STATE_IDLE_THRESHOLD`: Increase to tolerate longer stops as DRIVING
- `DRIVING_MAX_RESPONSE_LENGTH`: Adjust response length limit
- `STATE_HYSTERESIS_DURATION`: Adjust debounce timing

### Adding Prohibited Patterns
Edit `core/response_validator.py`:
- `AFFECTIONATE_TERMS`: Add terms to block list
- `NARRATIVE_MARKERS`: Add phrases to block list
- Modify `EMOJIS_PATTERN` regex for additional emoji ranges

### Debugging State Transitions
Enable verbose logging in `state_manager.py` by adding print statements in `_compute_state_with_hysteresis()`.

## Support

For issues or questions:
1. Check `docs/ARIA_DRIVING_CONTRACT.md` for specification details
2. Run `test_driving_contract.py` to verify system functionality
3. Use `/state` command in console mode for real-time diagnostics
4. Review `TROUBLESHOOTING.md` for common issues

---

**Implementation Date**: 2026-01-12  
**Version**: 1.0  
**Status**: Complete and tested ✅
