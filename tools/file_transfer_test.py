#!/usr/bin/env python3
"""
Sandsara Mini Pro - File Transfer Test Script

Tests the file transfer protocol for sending patterns to the device.
Based on reverse-engineered protocol from original firmware.

Usage:
    python3 file_transfer_test.py scan              # Find Sandsara device
    python3 file_transfer_test.py discover          # Discover file transfer characteristics
    python3 file_transfer_test.py send <file>       # Send a pattern file
    python3 file_transfer_test.py test              # Send a test pattern

Requirements:
    pip install bleak
"""

import asyncio
import struct
import sys
import math
from pathlib import Path

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    print("Please install bleak: pip install bleak")
    sys.exit(1)


# BLE UUIDs for Sandsara Mini Pro
SERVICE_MAIN = "fd31a2be-22e7-11eb-adc1-0242ac120002"
SERVICE_FILE_TRANSFER = "fd31abc4-22e7-11eb-adc1-0242ac120002"

# Main service characteristics (for init)
CHAR_COMMAND = "e914c2c0-cde3-4939-adb2-ca61a3cc9b4e"
CHAR_PLAYBACK = "10b59496-bf86-44a8-ba7a-67d8e26a93eb"
CHAR_DATETIME = "0ecc71c5-20a8-462f-92d0-0618c5051cf0"

# File transfer characteristics (from Mini Pro)
CHAR_FILE_FLAG = "fcbff68e-2af1-11eb-adc1-0242ac120002"
CHAR_FILE_DATA = "fcbffa44-2af1-11eb-adc1-0242ac120002"
CHAR_FILE_UNKNOWN = "27566b01-59c3-4a6f-a40e-c35606b0a29b"
CHAR_FILE_STATUS = "250e79ac-f0d7-43cc-ad6a-63544b5c6663"

# Original firmware UUIDs (may or may not exist on Mini Pro)
CHAR_FILE_EXISTS = "fcbffb52-2af1-11eb-adc1-0242ac120002"
CHAR_FILE_DELETE = "fcbffc24-2af1-11eb-adc1-0242ac120002"
CHAR_FILE_ERROR = "fcbffce2-2af1-11eb-adc1-0242ac120002"

# Transfer parameters
CHUNK_SIZE = 512  # Maximum bytes per BLE write
DEVICE_NAME_PREFIX = "Sand"


class SandsaraFileTransfer:
    """Handle file transfer to Sandsara device."""

    def __init__(self, address: str):
        self.address = address
        self.client: BleakClient | None = None
        self.notifications: asyncio.Queue = asyncio.Queue()
        self.initialized = False

    def _notification_handler(self, sender, data: bytearray):
        """Collect notifications from device."""
        uuid_str = str(getattr(sender, 'uuid', sender))
        short_uuid = uuid_str.split('-')[0] if '-' in uuid_str else uuid_str
        print(f"  [NOTIFY] {short_uuid}: {data.hex()} = {repr(data)}")
        self.notifications.put_nowait((uuid_str, data))

    async def connect(self) -> bool:
        """Connect to device and initialize."""
        print(f"Connecting to {self.address}...")
        self.client = BleakClient(self.address)
        
        try:
            await self.client.connect()
            print(f"Connected: {self.client.is_connected}")
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

        # Enable notifications on all relevant characteristics
        await self._enable_notifications()
        
        # Run init handshake
        await self._init_handshake()
        
        return True

    async def _enable_notifications(self):
        """Enable notifications on all notify-capable characteristics."""
        if not self.client:
            return
            
        print("Enabling notifications...")
        for service in self.client.services:
            for char in service.characteristics:
                if "notify" in char.properties:
                    try:
                        await self.client.start_notify(char.uuid, self._notification_handler)
                        print(f"  Enabled notify on {char.uuid[:8]}...")
                    except Exception as e:
                        print(f"  Failed to enable notify on {char.uuid[:8]}: {e}")

    async def _init_handshake(self):
        """Run the standard init handshake."""
        if not self.client:
            return
            
        print("Running init handshake...")
        try:
            await self.client.write_gatt_char(CHAR_DATETIME, bytes([0x00]), response=True)
            await self.client.write_gatt_char(CHAR_PLAYBACK, bytes([0x00]), response=True)
            await self.client.write_gatt_char(CHAR_COMMAND, bytes([0x00]), response=True)
            
            # Sync datetime
            from datetime import datetime
            now = datetime.now().isoformat()
            await self.client.write_gatt_char(CHAR_DATETIME, b'\x04' + now.encode('ascii'), response=True)
            
            await asyncio.sleep(0.5)
            self.initialized = True
            print("Init complete!")
        except Exception as e:
            print(f"Init failed: {e}")

    async def discover_file_service(self):
        """Discover and print file transfer service characteristics."""
        if not self.client:
            print("Not connected")
            return
            
        print("\n=== File Transfer Service Discovery ===\n")
        
        found_service = False
        for service in self.client.services:
            if SERVICE_FILE_TRANSFER.lower() in service.uuid.lower():
                found_service = True
                print(f"Service: {service.uuid}")
                print(f"  Handle: {service.handle}")
                print()
                
                for char in service.characteristics:
                    print(f"  Characteristic: {char.uuid}")
                    print(f"    Handle: {char.handle}")
                    print(f"    Properties: {', '.join(char.properties)}")
                    
                    # Try to identify known characteristics
                    uuid_short = char.uuid.split('-')[0]
                    known = {
                        'fcbff68e': 'FILE_FLAG (start/end transfer)',
                        'fcbffa44': 'FILE_DATA (chunk data)',
                        '27566b01': 'UNKNOWN (info/progress?)',
                        '250e79ac': 'FILE_STATUS (transfer status)',
                        'fcbffb52': 'FILE_EXISTS (check file)',
                        'fcbffc24': 'FILE_DELETE (delete file)',
                        'fcbffce2': 'FILE_ERROR (error messages)',
                    }
                    if uuid_short in known:
                        print(f"    Known as: {known[uuid_short]}")
                    
                    # Try to read if readable
                    if "read" in char.properties:
                        try:
                            value = await self.client.read_gatt_char(char.uuid)
                            print(f"    Current value: {value.hex()} = {repr(value)}")
                        except Exception as e:
                            print(f"    Read failed: {e}")
                    print()
        
        if not found_service:
            print("File Transfer service not found!")
            print("\nAll services:")
            for service in self.client.services:
                print(f"  {service.uuid}")

    async def wait_for_notification(self, timeout: float = 5.0) -> tuple[str, bytes] | None:
        """Wait for a notification."""
        try:
            return await asyncio.wait_for(self.notifications.get(), timeout)
        except asyncio.TimeoutError:
            return None

    async def send_file(self, filepath: Path, dest_name: str | None = None) -> bool:
        """Send a file to the device."""
        if not self.client or not self.initialized:
            print("Not connected or not initialized")
            return False

        if not filepath.exists():
            print(f"File not found: {filepath}")
            return False

        filename = dest_name or filepath.name
        data = filepath.read_bytes()
        
        print(f"\n=== Sending File ===")
        print(f"Local file: {filepath}")
        print(f"Dest name: {filename}")
        print(f"Size: {len(data)} bytes ({len(data) // CHUNK_SIZE + 1} chunks)")
        print()

        # Clear any pending notifications
        while not self.notifications.empty():
            self.notifications.get_nowait()

        # Step 1: Start transfer - write filename to FILE_FLAG
        print(f"[1] Starting transfer: {filename}")
        try:
            await self.client.write_gatt_char(
                CHAR_FILE_FLAG, 
                filename.encode('ascii'), 
                response=True
            )
        except Exception as e:
            print(f"Failed to start transfer: {e}")
            return False

        # Wait for OK response
        print("    Waiting for response...")
        await asyncio.sleep(0.3)
        
        # Drain notifications and look for response
        response_ok = False
        while not self.notifications.empty():
            uuid, notif_data = self.notifications.get_nowait()
            text = notif_data.decode('ascii', errors='replace')
            if 'ok' in text.lower():
                response_ok = True
                print(f"    Got OK response")
        
        if not response_ok:
            print("    Warning: No OK response received, continuing anyway...")

        # Step 2: Send data in chunks
        print(f"\n[2] Sending data...")
        total_chunks = (len(data) + CHUNK_SIZE - 1) // CHUNK_SIZE
        
        for i in range(0, len(data), CHUNK_SIZE):
            chunk = data[i:i + CHUNK_SIZE]
            chunk_num = i // CHUNK_SIZE + 1
            
            print(f"    Chunk {chunk_num}/{total_chunks} ({len(chunk)} bytes)...", end=' ')
            
            try:
                await self.client.write_gatt_char(CHAR_FILE_DATA, chunk, response=True)
            except Exception as e:
                print(f"FAILED: {e}")
                return False

            # Wait for ACK
            notif = await self.wait_for_notification(timeout=2.0)
            if notif:
                uuid, ack_data = notif
                if ack_data == b'1' or ack_data == b'\x31':
                    print("ACK")
                else:
                    print(f"response: {ack_data.hex()}")
            else:
                print("no ACK (timeout)")
            
            # Small delay between chunks
            await asyncio.sleep(0.05)

        # Step 3: End transfer
        print(f"\n[3] Ending transfer...")
        try:
            await self.client.write_gatt_char(CHAR_FILE_FLAG, bytes([0x00]), response=True)
        except Exception as e:
            print(f"Failed to end transfer: {e}")
            return False

        # Wait for "done" response
        print("    Waiting for completion...")
        await asyncio.sleep(0.5)
        
        transfer_done = False
        while not self.notifications.empty():
            uuid, notif_data = self.notifications.get_nowait()
            text = notif_data.decode('ascii', errors='replace')
            if 'done' in text.lower():
                transfer_done = True
                print(f"    Transfer complete!")
        
        if not transfer_done:
            print("    Warning: No 'done' response received")

        return True

    async def disconnect(self):
        """Disconnect from device."""
        if self.client and self.client.is_connected:
            await self.client.disconnect()
            print("Disconnected")


def create_test_pattern() -> bytes:
    """Create a simple test pattern (circle)."""
    points = []
    num_points = 360
    
    for i in range(num_points):
        # Theta: 0-65535 maps to 0-360°
        theta = int((i / num_points) * 65535)
        
        # Rho: constant radius (0x2C80 = medium radius)
        rho = 0x2C80
        
        # Counter: incrementing
        counter = i
        
        # Pack as big-endian uint16
        point = struct.pack('>HHH', theta, rho, counter)
        points.append(point)
    
    return b''.join(points)


async def scan_for_sandsara() -> str | None:
    """Scan for Sandsara devices."""
    print("Scanning for Sandsara devices...")
    
    devices = await BleakScanner.discover(timeout=10.0)
    
    sandsara_devices = []
    for d in devices:
        name = d.name or ""
        if DEVICE_NAME_PREFIX.lower() in name.lower():
            sandsara_devices.append(d)
            print(f"  Found: {d.name} ({d.address})")
    
    if not sandsara_devices:
        print("No Sandsara devices found")
        # Try service UUID based discovery
        print("\nTrying service-based discovery...")
        devices = await BleakScanner.discover(
            timeout=10.0,
            service_uuids=[SERVICE_MAIN]
        )
        for d in devices:
            print(f"  Found by service: {d.name} ({d.address})")
            sandsara_devices.append(d)
    
    if sandsara_devices:
        return sandsara_devices[0].address
    return None


async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "scan":
        address = await scan_for_sandsara()
        if address:
            print(f"\nUse this address: {address}")
    
    elif command == "discover":
        address = await scan_for_sandsara()
        if not address:
            sys.exit(1)
        
        ft = SandsaraFileTransfer(address)
        if await ft.connect():
            await ft.discover_file_service()
            await ft.disconnect()

    elif command == "send":
        if len(sys.argv) < 3:
            print("Usage: file_transfer_test.py send <filepath> [dest_name]")
            sys.exit(1)
        
        filepath = Path(sys.argv[2])
        dest_name = sys.argv[3] if len(sys.argv) > 3 else None
        
        address = await scan_for_sandsara()
        if not address:
            sys.exit(1)
        
        ft = SandsaraFileTransfer(address)
        if await ft.connect():
            success = await ft.send_file(filepath, dest_name)
            await ft.disconnect()
            sys.exit(0 if success else 1)

    elif command == "test":
        # Create and send a test pattern
        address = await scan_for_sandsara()
        if not address:
            sys.exit(1)
        
        # Create test pattern
        test_data = create_test_pattern()
        test_file = Path("/tmp/sandsara-test-circle.bin")
        test_file.write_bytes(test_data)
        print(f"Created test pattern: {test_file} ({len(test_data)} bytes)")
        
        ft = SandsaraFileTransfer(address)
        if await ft.connect():
            # First discover the service
            await ft.discover_file_service()
            
            print("\n" + "="*60)
            print("Ready to send test pattern. Press Enter to continue...")
            input()
            
            success = await ft.send_file(test_file, "test-circle.bin")
            await ft.disconnect()
            sys.exit(0 if success else 1)

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
