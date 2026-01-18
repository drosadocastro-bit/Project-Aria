"""
B2 Audio DSP Protocol Testing Script
Quick test for captured USB commands before full integration.

Usage:
    python scripts/test_b2_dsp.py --port COM3 --test-preset 2
    python scripts/test_b2_dsp.py --port COM3 --scan
"""

import sys
import argparse
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.dsp_controller import B2AudioDSP


def test_connection(port: str, baudrate: int):
    """Test basic serial connection to B2 DSP."""
    print(f"\n🔌 Testing connection to {port} at {baudrate} baud...")
    
    dsp = B2AudioDSP(port=port, baudrate=baudrate)
    if dsp.connect():
        print("✅ Connection successful!")
        dsp.disconnect()
        return True
    else:
        print("❌ Connection failed!")
        return False


def test_raw_command(port: str, baudrate: int, hex_command: str):
    """Test a raw hex command."""
    print(f"\n📡 Sending command: {hex_command}")
    
    dsp = B2AudioDSP(port=port, baudrate=baudrate)
    if not dsp.connect():
        print("❌ Connection failed!")
        return False
    
    try:
        cmd_bytes = bytes.fromhex(hex_command)
        response = dsp.send_raw_command(cmd_bytes)
        if response:
            print(f"✅ Response received: {response.hex()}")
        else:
            print("⚠️  No response (may be normal for some DSPs)")
        return True
    except Exception as e:
        print(f"❌ Command failed: {e}")
        return False
    finally:
        dsp.disconnect()


def test_preset(port: str, baudrate: int, preset_id: int):
    """Test preset change using configured protocol."""
    print(f"\n🎛️  Testing preset change to ID {preset_id}...")
    
    # Load protocol file if exists
    protocol_file = Path(__file__).parent.parent / "config" / "b2_protocol.json"
    
    dsp = B2AudioDSP(
        port=port,
        baudrate=baudrate,
        protocol_file=str(protocol_file) if protocol_file.exists() else None
    )
    
    if not dsp.connect():
        print("❌ Connection failed!")
        return False
    
    try:
        success = dsp.set_preset(preset_id)
        if success:
            print(f"✅ Preset {preset_id} command sent!")
        else:
            print("❌ Preset change failed (no protocol defined?)")
        return success
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        dsp.disconnect()


def scan_baudrates(port: str):
    """Scan common baudrates to find the right one."""
    common_baudrates = [9600, 19200, 38400, 57600, 115200, 230400, 460800]
    
    print(f"\n🔍 Scanning baudrates on {port}...\n")
    
    for baudrate in common_baudrates:
        print(f"   Trying {baudrate}...", end=" ")
        dsp = B2AudioDSP(port=port, baudrate=baudrate)
        if dsp.connect():
            print("✅ Connected!")
            dsp.disconnect()
            time.sleep(0.5)
        else:
            print("❌")
    
    print("\nℹ️  Note: Connection success doesn't guarantee correct baudrate.")
    print("   Send a test command to verify.")


def interactive_mode(port: str, baudrate: int):
    """Interactive command testing."""
    print(f"\n🖥️  Interactive Mode - Connected to {port}")
    print("   Commands:")
    print("     hex <command>  - Send raw hex (e.g., 'hex A50300FF02B9')")
    print("     preset <id>    - Change preset (e.g., 'preset 2')")
    print("     quit           - Exit")
    
    dsp = B2AudioDSP(port=port, baudrate=baudrate)
    if not dsp.connect():
        print("❌ Connection failed!")
        return
    
    try:
        while True:
            cmd = input("\n> ").strip().lower()
            
            if cmd == "quit":
                break
            
            elif cmd.startswith("hex "):
                hex_cmd = cmd[4:].replace(" ", "")
                try:
                    response = dsp.send_raw_command(bytes.fromhex(hex_cmd))
                    if response:
                        print(f"   Response: {response.hex()}")
                    else:
                        print("   No response")
                except Exception as e:
                    print(f"   Error: {e}")
            
            elif cmd.startswith("preset "):
                try:
                    preset_id = int(cmd[7:])
                    dsp.set_preset(preset_id)
                    print(f"   Preset {preset_id} sent")
                except Exception as e:
                    print(f"   Error: {e}")
            
            else:
                print("   Unknown command")
    
    finally:
        dsp.disconnect()
        print("\n👋 Disconnected")


def main():
    parser = argparse.ArgumentParser(description="Test B2 Audio DSP protocol")
    parser.add_argument("--port", default="COM3", help="Serial port (COM3, /dev/ttyUSB0, etc.)")
    parser.add_argument("--baudrate", type=int, default=115200, help="Baudrate (default: 115200)")
    parser.add_argument("--test-preset", type=int, metavar="ID", help="Test preset change")
    parser.add_argument("--hex", metavar="COMMAND", help="Send raw hex command")
    parser.add_argument("--scan", action="store_true", help="Scan common baudrates")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    
    args = parser.parse_args()
    
    # Scan mode
    if args.scan:
        scan_baudrates(args.port)
        return
    
    # Connection test
    if not args.test_preset and not args.hex and not args.interactive:
        test_connection(args.port, args.baudrate)
        return
    
    # Interactive mode
    if args.interactive:
        interactive_mode(args.port, args.baudrate)
        return
    
    # Test preset
    if args.test_preset is not None:
        test_preset(args.port, args.baudrate, args.test_preset)
    
    # Test hex command
    if args.hex:
        test_raw_command(args.port, args.baudrate, args.hex)


if __name__ == "__main__":
    main()
