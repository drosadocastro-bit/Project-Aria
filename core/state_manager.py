"""
State Manager for Aria - Operational State Detection
Implements DRIVING/PARKED/GARAGE state transitions with hysteresis
"""

import time
from enum import Enum
from typing import Optional, Dict, Any


class VehicleState(Enum):
    """Vehicle operational states."""
    PARKED = "PARKED"
    DRIVING = "DRIVING"
    GARAGE = "GARAGE"


class StateManager:
    """
    Manages Aria's operational state based on vehicle telemetry.
    
    States:
    - PARKED: Vehicle stationary, engine off or parking brake engaged
    - DRIVING: Vehicle in motion or temporarily stopped (traffic lights)
    - GARAGE: Maintenance/diagnostic mode (manual or sustained PARKED)
    """
    
    def __init__(self, config):
        """
        Initialize state manager with configuration.
        
        Args:
            config: Configuration module with state parameters
        """
        self.config = config
        
        # Current state
        self._current_state = VehicleState.PARKED  # Conservative default
        self._state_entry_time = time.time()
        
        # Hysteresis tracking
        self._last_speed = 0.0
        self._last_state_change = time.time()
        self._speed_above_threshold_since = None
        self._stopped_since = None
        
        # Manual override
        self._manual_override_active = False
        self._manual_override_state = None
    
    def get_current_state(self, telemetry: Optional[Dict[str, Any]] = None) -> VehicleState:
        """
        Get current vehicle state based on telemetry.
        
        Args:
            telemetry: Dictionary with keys: 'speed', 'rpm', etc.
                      If None, uses last known state or manual override.
        
        Returns:
            Current VehicleState
        """
        # Manual override takes precedence (with safety checks)
        if self._manual_override_active and self._manual_override_state:
            # Safety: Cannot override FROM DRIVING unless vehicle is stopped
            if self._current_state == VehicleState.DRIVING:
                if telemetry and telemetry.get('speed', 0) > 0:
                    # Vehicle still moving, ignore override
                    return self._current_state
            
            return self._manual_override_state
        
        # If no telemetry available, return last known state (conservative)
        if not telemetry:
            return self._current_state
        
        # Extract telemetry
        speed = telemetry.get('speed', 0) or 0  # Handle None values
        rpm = telemetry.get('rpm', 0) or 0
        
        # Determine if engine is running
        engine_running = rpm > 0
        
        # Current timestamp
        now = time.time()
        
        # Compute new state with hysteresis
        new_state = self._compute_state_with_hysteresis(
            speed, engine_running, now
        )
        
        # Check for PARKED → GARAGE auto-transition
        if new_state == VehicleState.PARKED:
            time_in_parked = now - self._state_entry_time
            if time_in_parked > self.config.STATE_GARAGE_TIMEOUT:
                new_state = VehicleState.GARAGE
        
        # Update state if changed
        if new_state != self._current_state:
            self._current_state = new_state
            self._state_entry_time = now
            self._last_state_change = now
        
        return self._current_state
    
    def _compute_state_with_hysteresis(
        self, speed: float, engine_running: bool, now: float
    ) -> VehicleState:
        """
        Compute state with hysteresis to prevent rapid switching.
        
        Args:
            speed: Current speed in mph
            engine_running: Whether engine is running (RPM > 0)
            now: Current timestamp
        
        Returns:
            Computed VehicleState
        """
        # GARAGE state requires manual override or timeout
        if self._current_state == VehicleState.GARAGE:
            # Stay in GARAGE unless vehicle starts moving
            if speed >= self.config.STATE_SPEED_THRESHOLD:
                return VehicleState.DRIVING
            return VehicleState.GARAGE
        
        # Track speed above threshold duration
        if speed >= self.config.STATE_SPEED_THRESHOLD:
            if self._speed_above_threshold_since is None:
                self._speed_above_threshold_since = now
            
            # Check hysteresis duration
            duration = now - self._speed_above_threshold_since
            if duration >= self.config.STATE_HYSTERESIS_DURATION:
                self._stopped_since = None  # Reset stopped timer
                return VehicleState.DRIVING
        else:
            # Below threshold, reset timer
            self._speed_above_threshold_since = None
        
        # Track stopped duration
        if speed == 0:
            if self._stopped_since is None:
                self._stopped_since = now
            
            stopped_duration = now - self._stopped_since
            
            # DRIVING → PARKED transition
            # Requires: stopped AND (engine off OR stopped > idle threshold)
            if self._current_state == VehicleState.DRIVING:
                if not engine_running:
                    # Engine off = definitely parked
                    return VehicleState.PARKED
                elif stopped_duration > self.config.STATE_IDLE_THRESHOLD:
                    # Stopped too long = parked (not just a traffic light)
                    return VehicleState.PARKED
                else:
                    # Brief stop with engine on = still DRIVING (traffic light)
                    return VehicleState.DRIVING
            
            # Already PARKED, stay PARKED
            return VehicleState.PARKED
        else:
            # Moving (but below DRIVING threshold)
            self._stopped_since = None
            
            # If currently PARKED and started moving, go to DRIVING
            if self._current_state == VehicleState.PARKED:
                if speed > 0:  # Any movement
                    # Wait for hysteresis before full DRIVING state
                    return self._current_state
        
        # Default: maintain current state
        return self._current_state
    
    def set_manual_override(self, state: Optional[str] = None):
        """
        Set manual state override.
        
        Args:
            state: "PARKED", "GARAGE", "DRIVING", or None to disable override
        """
        if state is None:
            self._manual_override_active = False
            self._manual_override_state = None
        else:
            if not self.config.STATE_MANUAL_OVERRIDE_ENABLED:
                raise ValueError("Manual override is disabled in configuration")
            
            try:
                override_state = VehicleState[state.upper()]
                self._manual_override_active = True
                self._manual_override_state = override_state
            except KeyError:
                raise ValueError(f"Invalid state: {state}. Must be PARKED, GARAGE, or DRIVING")
    
    def is_manual_override_active(self) -> bool:
        """Check if manual override is currently active."""
        return self._manual_override_active
    
    def get_state_info(self, telemetry: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get detailed state information for debugging/display.
        
        Args:
            telemetry: Current telemetry data
        
        Returns:
            Dictionary with state details
        """
        current_state = self.get_current_state(telemetry)
        now = time.time()
        
        return {
            "state": current_state.value,
            "time_in_state": now - self._state_entry_time,
            "manual_override": self._manual_override_active,
            "last_speed": self._last_speed,
            "telemetry_available": telemetry is not None,
        }
    
    def reset(self):
        """Reset state manager to initial PARKED state."""
        self._current_state = VehicleState.PARKED
        self._state_entry_time = time.time()
        self._last_state_change = time.time()
        self._speed_above_threshold_since = None
        self._stopped_since = None
        self._manual_override_active = False
        self._manual_override_state = None


# Helper function for easy integration
def create_state_manager(config) -> StateManager:
    """
    Create and return a StateManager instance.
    
    Args:
        config: Configuration module
    
    Returns:
        Initialized StateManager
    """
    return StateManager(config)
