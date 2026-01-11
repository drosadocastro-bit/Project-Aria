"""
OBD-II integration for Windows
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import OBD_ENABLED, OBD_PORT, OBD_BAUDRATE

if OBD_ENABLED:
    try:
        import obd
        OBD_AVAILABLE = True
    except ImportError:
        OBD_AVAILABLE = False
        print("⚠️ OBD library not found. Install: pip install obd")
else:
    OBD_AVAILABLE = False


class OBDMonitor:
    """Monitor GTI via OBD-II on Windows."""
    
    def __init__(self):
        self.connection = None
        self.connected = False
        
        if OBD_AVAILABLE:
            self.connect()
    
    def connect(self):
        """Connect to OBD-II adapter."""
        try:
            print(f"🔌 Attempting OBD-II connection on {OBD_PORT}...")
            
            # Try specified port
            self.connection = obd.OBD(portstr=OBD_PORT, baudrate=OBD_BAUDRATE, timeout=5)
            
            if not self.connection.is_connected():
                # Try auto-connect (will scan all COM ports)
                print("⚠️ Trying auto-connect (this may take a moment)...")
                self.connection = obd.OBD()
            
            self.connected = self.connection.is_connected()
            
            if self.connected:
                print(f"✅ Connected to OBD-II: {self.connection.port_name()}")
                print(f"   Protocol: {self.connection.protocol_name()}")
                print(f"   ECU: {self.connection.ecus()}")
            else:
                print("❌ OBD-II connection failed")
                print("   Tips:")
                print("   1. Check OBDLink is plugged into car (engine ON)")
                print("   2. Verify Bluetooth pairing")
                print("   3. Check COM port in Device Manager")
                print(f"   4. Current port setting: {OBD_PORT}")
                
        except Exception as e:
            print(f"❌ OBD-II error: {e}")
            self.connected = False
    
    def get_live_data(self):
        """Get current sensor readings."""
        if not self.connected:
            return None
        
        try:
            data = {}
            
            # Query each sensor (some may not be supported)
            sensors = {
                "rpm": obd.commands.RPM,
                "speed": obd.commands.SPEED,
                "coolant_temp": obd.commands.COOLANT_TEMP,
                "throttle": obd.commands.THROTTLE_POS,
                "fuel_trim_short": obd.commands.SHORT_FUEL_TRIM_1,
                "fuel_trim_long": obd.commands.LONG_FUEL_TRIM_1,
                "intake_temp": obd.commands.INTAKE_TEMP,
                "maf": obd.commands.MAF,
            }
            
            for key, cmd in sensors.items():
                value = self.query(cmd)
                data[key] = value
            
            return data
        except Exception as e:
            print(f"⚠️ OBD read error: {e}")
            return None
    
    def query(self, command):
        """Query single OBD command."""
        try:
            response = self.connection.query(command)
            if response.value is not None:
                # Handle pint quantities
                if hasattr(response.value, 'magnitude'):
                    return round(response.value.magnitude, 1)
                return response.value
            return None
        except:
            return None
    
    def get_dtc_codes(self):
        """Get diagnostic trouble codes."""
        if not self.connected:
            return []
        
        try:
            codes = self.connection.query(obd.commands.GET_DTC)
            if codes.value:
                return [
                    {"code": code[0], "description": code[1]}
                    for code in codes.value
                ]
            return []
        except:
            return []
    
    def format_status(self, data):
        """Format car data for display."""
        if not data:
            return "[Car not connected]"
        
        return f"""[Current GTI Status]:
- RPM: {data.get('rpm', 'N/A')}
- Speed: {data.get('speed', 'N/A')} km/h
- Coolant: {data.get('coolant_temp', 'N/A')}°C
- Throttle: {data.get('throttle', 'N/A')}%
- Fuel Trim (Short): {data.get('fuel_trim_short', 'N/A')}%
- Fuel Trim (Long): {data.get('fuel_trim_long', 'N/A')}%"""


# Global instance
obd_monitor = OBDMonitor()
