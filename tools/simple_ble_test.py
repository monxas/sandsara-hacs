#!/usr/bin/env python3
"""
Sandsara Mini Pro - Simple BLE Connection Test

Minimal script to test basic BLE connectivity and file transfer service discovery.
Run this on a machine with direct Bluetooth access (not in a container).

Usage:
    python3 simple_ble_test.py                    # Auto-scan and test
    python3 simple_ble_test.py 94:B9:7E:F1:10:76  # Connect to specific MAC

Requirements:
    pip install bleak
"""

import asyncio
import sys

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    print("Error: bleak not installed. Run: pip install bleak")
    sys.exit(1)

# Known UUIDs
SERVICE_FILE_TRANSFER = "fd31abc4-22e7-11eb-adc1-0242ac120002"
CHAR_FILE_FLAG = "fcbff68e-2af1-11eb-adc1-0242ac120002"
CHAR_FILE_DATA = "fcbffa44-2af1-11eb-adc1-0242ac120002"

# Known Sandsara MAC (from Home Assistant)
KNOWN_MAC = "94:B9:7E:F1:10:76"


async def scan():
    """Scan for Sandsara devices."""
    print("Scanning for BLE devices (10s)...")
    devices = await BleakScanner.discover(timeout=10.0)
    
    print(f"\nFound {len(devices)} devices:")
    sandsara = None
    for d in devices:
        name = d.name or "(no name)"
        marker = ""
        if "sand" in name.lower() or d.address.upper() == KNOWN_MAC:
            marker = " ← SANDSARA"
            sandsara = d
        print(f"  {d.address} - {name}{marker}")
    
    return sandsara


async def test_connection(address: str):
    """Connect and discover file transfer service."""
    print(f"\n{'='*50}")
    print(f"Connecting to {address}...")
    
    client = BleakClient(address)
    try:
        await client.connect(timeout=15.0)
        print(f"Connected: {client.is_connected}")
        
        # List all services
        print(f"\nDiscovered {len(client.services)} services:")
        file_service = None
        
        for service in client.services:
            uuid = service.uuid
            is_file = SERVICE_FILE_TRANSFER.lower() in uuid.lower()
            marker = " ← FILE TRANSFER SERVICE" if is_file else ""
            print(f"\n  Service: {uuid}{marker}")
            
            if is_file:
                file_service = service
            
            for char in service.characteristics:
                props = ", ".join(char.properties)
                
                # Identify known chars
                known = ""
                if CHAR_FILE_FLAG.lower() in char.uuid.lower():
                    known = " [FILE_FLAG]"
                elif CHAR_FILE_DATA.lower() in char.uuid.lower():
                    known = " [FILE_DATA]"
                
                print(f"    Char: {char.uuid}")
                print(f"          Props: {props}{known}")
                
                if "read" in char.properties:
                    try:
                        val = await client.read_gatt_char(char.uuid)
                        print(f"          Value: {val.hex()} = {repr(val)}")
                    except Exception as e:
                        print(f"          Read error: {e}")
        
        if file_service:
            print(f"\n✓ File Transfer Service FOUND!")
            print(f"  Protocol should work as documented.")
        else:
            print(f"\n✗ File Transfer Service NOT FOUND")
            print(f"  Expected UUID: {SERVICE_FILE_TRANSFER}")
        
        return file_service is not None
        
    except Exception as e:
        print(f"Connection failed: {e}")
        return False
    finally:
        if client.is_connected:
            await client.disconnect()
            print("\nDisconnected")


async def main():
    address = sys.argv[1] if len(sys.argv) > 1 else None
    
    if not address:
        device = await scan()
        if device:
            address = device.address
        else:
            print(f"\nNo Sandsara found. Try known MAC: {KNOWN_MAC}")
            address = KNOWN_MAC
    
    await test_connection(address)


if __name__ == "__main__":
    asyncio.run(main())
