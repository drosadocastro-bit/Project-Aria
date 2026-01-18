"""
DSP Controller - Hardware EQ preset switching for B2 Audio DSP
Supports direct USB/serial protocol (preferred) and Android automation fallback.
"""

import serial
import subprocess
import logging
from typing import Optional, Dict, Any
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class B2AudioDSP:
    """
    B2 Audio DSP controller via USB/serial protocol.
    Protocol must be reverse-engineered via Wireshark/USB sniffing.
    """
    
    def __init__(self, port: str = "COM3", baudrate: int = 115200, protocol_file: Optional[str] = None):
        """
        Args:
            port: Serial port (e.g., COM3 on Windows, /dev/ttyUSB0 on Linux)
            baudrate: Common values: 9600, 115200, 230400
            protocol_file: JSON file with captured command sequences
        """
        self.port = port
        self.baudrate = baudrate
        self.serial: Optional[serial.Serial] = None
        self.protocol: Dict[str, Any] = {}
        
        if protocol_file and Path(protocol_file).exists():
            with open(protocol_file, 'r') as f:
                self.protocol = json.load(f)
            logger.info(f"Loaded B2 protocol from {protocol_file}")
    
    def connect(self) -> bool:
        """Open serial connection to DSP."""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            logger.info(f"Connected to B2 DSP on {self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to B2 DSP: {e}")
            return False
    
    def disconnect(self):
        """Close serial connection."""
        if self.serial and self.serial.is_open:
            self.serial.close()
            logger.info("Disconnected from B2 DSP")
    
    def send_raw_command(self, command: bytes) -> Optional[bytes]:
        """
        Send raw byte sequence to DSP.
        
        Args:
            command: Byte sequence (from Wireshark capture)
        
        Returns:
            Response bytes if available
        """
        if not self.serial or not self.serial.is_open:
            logger.error("DSP not connected")
            return None
        
        try:
            self.serial.write(command)
            self.serial.flush()
            
            # Read response (adjust timeout as needed)
            response = self.serial.read(256)
            logger.debug(f"Sent: {command.hex()} | Response: {response.hex()}")
            return response
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return None
    
    def set_preset(self, preset_id: int) -> bool:
        """
        Switch to DSP preset by ID.
        
        Args:
            preset_id: Preset number (0-7 or whatever B2 supports)
        
        Returns:
            True if command sent successfully
        """
        # Check if we have a known protocol command
        if "preset_change" in self.protocol:
            template = bytes.fromhex(self.protocol["preset_change"]["template"])
            # Replace placeholder byte with preset_id
            command = template.replace(b'\x00', preset_id.to_bytes(1, 'big'), 1)
            response = self.send_raw_command(command)
            return response is not None
        
        # Fallback: log warning
        logger.warning(f"No protocol defined for preset change. Preset ID: {preset_id}")
        return False
    
    def set_preset_by_name(self, name: str, preset_mapping: Dict[str, int]) -> bool:
        """
        Switch preset by genre/profile name.
        
        Args:
            name: Preset name (e.g., "bass_boost", "v_shape")
            preset_mapping: Dict mapping names to DSP preset IDs
        
        Returns:
            True if successful
        """
        preset_id = preset_mapping.get(name)
        if preset_id is None:
            logger.error(f"Unknown preset name: {name}")
            return False
        
        logger.info(f"Switching to preset '{name}' (ID: {preset_id})")
        return self.set_preset(preset_id)


class B2AndroidController:
    """
    B2 Audio DSP control via Android app automation (fallback method).
    Requires Waydroid + adb on Jetson or separate Android device.
    """
    
    def __init__(self, adb_device: Optional[str] = None):
        """
        Args:
            adb_device: Device ID for adb (None = use default device)
        """
        self.adb_device = adb_device
        self.package = "com.b2audio.dsp"  # Update with actual package name
    
    def _adb_cmd(self, args: list) -> bool:
        """Execute adb command."""
        cmd = ["adb"]
        if self.adb_device:
            cmd += ["-s", self.adb_device]
        cmd += args
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                logger.error(f"ADB command failed: {result.stderr}")
                return False
            return True
        except Exception as e:
            logger.error(f"ADB error: {e}")
            return False
    
    def set_preset_by_tap(self, preset_name: str, coordinates: tuple) -> bool:
        """
        Switch preset by tapping screen coordinates.
        
        Args:
            preset_name: For logging
            coordinates: (x, y) screen tap position
        
        Returns:
            True if tap sent successfully
        """
        x, y = coordinates
        logger.info(f"Tapping preset '{preset_name}' at ({x}, {y})")
        
        # Wake screen + tap
        self._adb_cmd(["shell", "input", "keyevent", "KEYCODE_WAKEUP"])
        return self._adb_cmd(["shell", "input", "tap", str(x), str(y)])
    
    def set_preset_by_intent(self, preset_id: int) -> bool:
        """
        Switch preset via Android intent (if B2 app supports it).
        
        Args:
            preset_id: Preset number
        
        Returns:
            True if intent sent
        """
        logger.info(f"Sending intent for preset {preset_id}")
        return self._adb_cmd([
            "shell", "am", "broadcast",
            "-a", f"{self.package}.PRESET_CHANGE",
            "--ei", "preset_id", str(preset_id)
        ])


class DSPController:
    """
    Unified DSP controller with auto-fallback.
    Tries direct USB protocol first, falls back to Android automation.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: Dict with DSP settings (from config.py)
        """
        self.method = config.get("DSP_METHOD", "usb")  # "usb" or "android"
        self.preset_mapping = config.get("DSP_PRESET_MAPPING", {})
        
        if self.method == "usb":
            self.controller = B2AudioDSP(
                port=config.get("DSP_PORT", "COM3"),
                baudrate=config.get("DSP_BAUDRATE", 115200),
                protocol_file=config.get("DSP_PROTOCOL_FILE")
            )
            if not self.controller.connect():
                logger.warning("USB connection failed, falling back to Android")
                self.method = "android"
                self.controller = B2AndroidController(config.get("ADB_DEVICE"))
        else:
            self.controller = B2AndroidController(config.get("ADB_DEVICE"))
    
    def set_preset(self, preset_name: str) -> bool:
        """
        Switch DSP preset by name.
        
        Args:
            preset_name: Genre/profile name (e.g., "bass_boost")
        
        Returns:
            True if successful
        """
        if self.method == "usb":
            return self.controller.set_preset_by_name(preset_name, self.preset_mapping)
        else:
            # Android fallback: map to coordinates or intent
            if hasattr(self.controller, 'set_preset_by_intent'):
                preset_id = self.preset_mapping.get(preset_name)
                if preset_id is not None:
                    return self.controller.set_preset_by_intent(preset_id)
            return False
    
    def cleanup(self):
        """Cleanup resources."""
        if hasattr(self.controller, 'disconnect'):
            self.controller.disconnect()


# Example protocol mapping (populate after Wireshark capture)
EXAMPLE_PROTOCOL = {
    "preset_change": {
        "description": "Switch to preset ID",
        "template": "A50300FF00B8",  # Example hex, replace \x00 with preset_id
        "example": "A50300FF02B8",  # Preset 2
        "notes": "Captured from USB analyzer, checksum may be last byte"
    },
    "volume_set": {
        "template": "A50400FF00C9",
        "notes": "Volume 0-100"
    }
}
