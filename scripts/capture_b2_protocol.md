# B2 Audio DSP Protocol Reverse Engineering Guide

## Recommended Workflow: Windows Prototype → Jetson Deploy

**Best Practice:** Reverse engineer the protocol on Windows first, then deploy to Jetson.

1. **Windows PC** - Wireshark + B2 app → capture protocol → test in Python
2. **Copy** `b2_protocol.json` to Jetson
3. **Jetson** - Same code, just change `COM3` to `/dev/ttyUSB0`

Why Windows first?
- Easier USB capture tools (USBPcap GUI)
- B2 Audio app may have Windows/Android version (easier than Linux)
- Faster iteration cycle for testing commands
- Protocol is portable once documented

---

## Windows Quick Start (5 Steps)

### 1. Find B2 DSP COM Port
```cmd
REM Open Device Manager (devmgmt.msc)
REM Look under "Ports (COM & LPT)" for B2 device
REM Note the COM port number (e.g., COM3)

REM Or use PowerShell:
Get-WmiObject Win32_SerialPort | Select-Object Name,DeviceID
```

### 2. Install Wireshark with USBPcap
- Download from [wireshark.org](https://www.wireshark.org/download.html)
- **Important:** Check "USBPcap" during installation
- Reboot after install

### 3. Capture Preset Changes
1. Open Wireshark
2. Start capture on USB interface (looks like "USBPcap1")
3. Open B2 Audio app
4. Change preset: 1 → 2 → 3 → 4 (one at a time, slowly)
5. Stop capture
6. Save as `b2_capture.pcapng`

### 4. Analyze Patterns
**Filter:** `usb.transfer_type == 0x02`

Look for hex sequences that change by 1 byte:
```
Preset 1: A5 03 00 FF 01 B8
Preset 2: A5 03 00 FF 02 B9  ← Byte 4 increments
Preset 3: A5 03 00 FF 03 BA
          ↑              ↑
       Start byte    Checksum
```

Right-click packet → Copy → Bytes as Hex Stream

### 5. Test Command in Python
```python
from core.dsp_controller import B2AudioDSP

dsp = B2AudioDSP(port="COM3", baudrate=115200)
if dsp.connect():
    # Send captured command for preset 2
    dsp.send_raw_command(bytes.fromhex("A50300FF02B9"))
    # Did preset change? Success!
```

If it works, document in `config/b2_protocol.json` and deploy to Jetson.

---

## Tools Required
- **Wireshark** (with USBPcap on Windows or usbmon on Linux)
- **B2 Audio DSP** connected via USB
- **B2 Audio mobile app** or PC software

## Step 1: Capture USB Traffic

### Windows (USBPcap)
1. Install Wireshark with USBPcap driver
2. Open Wireshark → Capture → Options
3. Select the USB interface with B2 DSP
4. Start capture
5. Open B2 app and **change presets manually** (1 → 2 → 3, etc.)
6. Stop capture after cycling through all presets

### Linux (usbmon)
```bash
# Find B2 DSP bus number
lsusb | grep -i b2

# Start capture (replace X with bus number)
sudo wireshark -k -i usbmonX

# Or use tshark for CLI
sudo tshark -i usbmonX -w b2_capture.pcapng
```

### Jetson (adb bridge method if using Android app)
```bash
# Capture Android USB traffic
adb shell "tcpdump -i any -U -w - 'tcp port 12345'" | wireshark -k -i -
```

## Step 2: Analyze Packets

### Filter USB Control Transfers
```
usb.transfer_type == 0x02  # Bulk transfers
usb.transfer_type == 0x00  # Control transfers
```

### Look for Patterns
- **Preset 1 → Preset 2**: Compare hex data for single-byte changes
- **Checksum bytes**: Usually last 1-2 bytes (XOR, CRC, sum)
- **Command structure**: Common format is `[START] [CMD] [LEN] [DATA] [CHECKSUM]`

### Export Packet Bytes
Right-click packet → Copy → Bytes as Hex Stream

Example capture for preset change:
```
Preset 1: A5 03 00 FF 01 B8
Preset 2: A5 03 00 FF 02 B9
Preset 3: A5 03 00 FF 03 BA
          ↑  ↑  ↑  ↑  ↑  ↑
          |  |  |  |  |  Checksum (increments)
          |  |  |  |  Preset ID
          |  |  |  Padding/flag
          |  |  Length or subcmd
          |  Command ID
          Start byte
```

## Step 3: Reverse Checksum Algorithm

### Common Methods
1. **Simple Sum**: Sum all bytes, truncate to 1 byte
2. **XOR**: XOR all data bytes
3. **CRC-8/16**: Use online calculator with captured data

### Test Script
```python
import serial

# Test command from capture
cmd = bytes.fromhex("A50300FF02B9")

ser = serial.Serial('COM3', 115200, timeout=1)
ser.write(cmd)
response = ser.read(256)
print(f"Response: {response.hex()}")
```

If DSP responds or changes preset → protocol confirmed!

## Step 4: Document Protocol

Create `config/b2_protocol.json`:
```json
{
  "preset_change": {
    "template": "A50300FF00B8",
    "checksum_offset": 5,
    "checksum_type": "sum",
    "notes": "Replace byte 4 with preset_id (0-7)"
  },
  "volume_set": {
    "template": "A50400FF00C9",
    "range": "0-100",
    "notes": "Byte 4 = volume level"
  },
  "eq_band": {
    "template": "A50800FF000000000000",
    "notes": "Bytes 4-5: band (0-9), Bytes 6-7: gain (-12 to +12 dB)"
  }
}
```

## Step 5: Integration

Update `config.py`:
```python
# DSP Control
DSP_METHOD = "usb"  # "usb" or "android"
DSP_PORT = "COM3"
DSP_BAUDRATE = 115200
DSP_PROTOCOL_FILE = "config/b2_protocol.json"
DSP_PRESET_MAPPING = {
    "neutral": 0,
    "bass_boost": 1,
    "v_shape": 2,
    "warm": 3,
    "bright": 4,
    "smiley": 5,
    "vocal": 6,
    "flat": 7,
}
```

Use in `auto_eq.py`:
```python
from core.dsp_controller import DSPController

dsp = DSPController(config.__dict__)
dsp.set_preset("bass_boost")  # Sends USB command
```

## Troubleshooting

### No USB Packets Visible
- Check if DSP uses HID protocol (use `usbhid-dump` on Linux)
- Try USB 2.0 port (3.0 may have capture issues)
- Ensure B2 software is communicating (not Bluetooth mode)

### Commands Don't Work
- Verify baudrate (try 9600, 38400, 115200, 230400)
- Check parity/stop bits (8N1 is common)
- DSP may require initialization sequence before accepting commands

### Checksum Errors
- Use `crc_algorithms.py` to brute-force CRC polynomials
- Check if checksum covers all bytes or just data payload

## Alternative: Android Intent Sniffing

If USB protocol is too complex, monitor Android app intents:
```bash
adb logcat | grep -i "b2audio\|preset\|intent"
```

Look for broadcasted intents you can replay via `adb shell am broadcast`.
