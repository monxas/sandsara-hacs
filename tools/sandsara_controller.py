#!/usr/bin/env python3
"""
Sandsara Mini Pro BLE Controller
Reverse-engineered protocol from HCI snoop capture.

NOTE: The Sandsara Mini Pro requires a persistent BLE connection to keep
running. The connection is held open until you press Ctrl+C.

Usage:
    python3 sandsara_controller.py scan
    python3 sandsara_controller.py play
    python3 sandsara_controller.py pause
    python3 sandsara_controller.py next
    python3 sandsara_controller.py sleep
    python3 sandsara_controller.py speed <0-100>
    python3 sandsara_controller.py led on
    python3 sandsara_controller.py led off
    python3 sandsara_controller.py led color <hex>       # e.g. ff0000 for red
    python3 sandsara_controller.py led gradient <hex1> <hex2>
    python3 sandsara_controller.py status
    python3 sandsara_controller.py interactive
    python3 sandsara_controller.py daemon                # connect, play, and keep alive
"""

import asyncio
import signal
import sys
from datetime import datetime
from bleak import BleakClient, BleakScanner

# --- BLE UUIDs ---
SERVICE_MAIN = "fd31a2be-22e7-11eb-adc1-0242ac120002"
SERVICE_FILE = "fd31abc4-22e7-11eb-adc1-0242ac120002"

CHAR_COMMAND   = "e914c2c0-cde3-4939-adb2-ca61a3cc9b4e"  # Main command char
CHAR_PLAYBACK  = "10b59496-bf86-44a8-ba7a-67d8e26a93eb"  # Playback control
CHAR_DATETIME  = "0ecc71c5-20a8-462f-92d0-0618c5051cf0"  # Datetime sync
CHAR_MODEL     = "caf74386-dd8b-4f54-9dd9-71c75f6d679a"  # Model (read-only)
CHAR_VERSION   = "7b204278-30c3-11eb-adc1-0242ac120002"  # Version (read-only)
CHAR_STATUS    = "9e23e02e-8921-4bf9-84f5-f58fa81c726e"  # Status (read-only)
CHAR_SETTINGS  = "20e01699-0346-45c7-91ae-3ebd8a16a2e6"  # Settings
CHAR_8         = "9d277d03-0855-4d8c-8687-316ebca89a61"
CHAR_9         = "eb940790-03f8-406d-bfc4-2f232cf65f84"

# --- Command bytes ---
CMD_INIT        = 0x00
CMD_SPEED       = 0x05
CMD_LED_TOGGLE  = 0x06
CMD_LED_COLOR   = 0x07

# Playback commands (written to CHAR_PLAYBACK)
PB_INIT   = 0x00
PB_SLEEP  = 0x04
PB_NEXT   = 0x06
PB_PLAY   = 0x07
PB_PAUSE  = 0x08

STATUS_MAP = {
    "1": "calibrating",
    "2": "playing",
    "3": "paused",
    "4": "sleeping",
    "5": "busy",
}

SANDSARA_SERVICE_UUIDS = [SERVICE_MAIN, SERVICE_FILE]


async def find_sandsara(timeout=10):
    """Scan for Sandsara device by service UUID."""
    print(f"Scanning for Sandsara ({timeout}s)...")
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    for addr, (dev, adv) in devices.items():
        svc_uuids = [u.lower() for u in (adv.service_uuids or [])]
        if any(u in svc_uuids for u in SANDSARA_SERVICE_UUIDS):
            print(f"Found Sandsara: {addr} (RSSI: {adv.rssi})")
            return addr
    print("Sandsara not found. Make sure it's powered on and not connected to another device.")
    return None


async def connect_and_init(client: BleakClient):
    """Perform the connection init sequence."""
    # Enable notifications on all notify-capable characteristics
    for service in client.services:
        for char in service.characteristics:
            if "notify" in char.properties:
                try:
                    await client.start_notify(char.uuid, lambda s, d: None)
                except Exception:
                    pass

    # Init sequence: write 0x00 to datetime, playback, and command chars
    await client.write_gatt_char(CHAR_DATETIME, bytes([CMD_INIT]), response=True)
    await client.write_gatt_char(CHAR_PLAYBACK, bytes([PB_INIT]), response=True)
    await client.write_gatt_char(CHAR_COMMAND, bytes([CMD_INIT]), response=True)

    # Sync datetime
    now = datetime.now().isoformat()
    await client.write_gatt_char(CHAR_DATETIME, bytes([0x04]) + now.encode("ascii"), response=True)

    await asyncio.sleep(0.5)


async def cmd_play(client):
    await client.write_gatt_char(CHAR_PLAYBACK, bytes([PB_PLAY]), response=True)
    print("-> Play")

async def cmd_pause(client):
    await client.write_gatt_char(CHAR_PLAYBACK, bytes([PB_PAUSE]), response=True)
    print("-> Pause")

async def cmd_next(client):
    await client.write_gatt_char(CHAR_PLAYBACK, bytes([PB_NEXT]), response=True)
    print("-> Next track")

async def cmd_sleep(client):
    await client.write_gatt_char(CHAR_PLAYBACK, bytes([PB_SLEEP]), response=True)
    print("-> Sleep")

async def cmd_speed(client, speed: int):
    speed = max(0, min(100, speed))
    await client.write_gatt_char(CHAR_COMMAND, bytes([CMD_SPEED, speed]), response=True)
    print(f"-> Speed: {speed}")

async def cmd_led_on(client):
    await client.write_gatt_char(CHAR_COMMAND, bytes([CMD_LED_TOGGLE, 0x01]), response=True)
    print("-> LED on")

async def cmd_led_off(client):
    await client.write_gatt_char(CHAR_COMMAND, bytes([CMD_LED_TOGGLE, 0x00]), response=True)
    print("-> LED off")

async def cmd_led_color(client, hex_color: str):
    """Set solid LED color. hex_color like 'ff0000' for red."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    # Mini Pro ignores count=1 (solid). Use count=2 gradient with same color on both ends.
    # Format: 07 [count=2] [pos1=0, pos2=255] [R1,R2] [G1,G2] [B1,B2]
    payload = bytes([CMD_LED_COLOR, 0x02, 0x00, 0xFF, r, r, g, g, b, b])
    await client.write_gatt_char(CHAR_COMMAND, payload, response=True)
    print(f"-> LED color: #{hex_color} (R={r} G={g} B={b})")

async def cmd_led_gradient(client, hex1: str, hex2: str):
    """Set LED gradient between two colors."""
    hex1 = hex1.lstrip("#")
    hex2 = hex2.lstrip("#")
    r1, g1, b1 = int(hex1[0:2], 16), int(hex1[2:4], 16), int(hex1[4:6], 16)
    r2, g2, b2 = int(hex2[0:2], 16), int(hex2[2:4], 16), int(hex2[4:6], 16)
    # Format: 07 [count=2] [pos1=0, pos2=255] [R1,R2] [G1,G2] [B1,B2]
    payload = bytes([CMD_LED_COLOR, 0x02, 0x00, 0xFF, r1, r2, g1, g2, b1, b2])
    await client.write_gatt_char(CHAR_COMMAND, payload, response=True)
    print(f"-> LED gradient: #{hex1} -> #{hex2}")

async def cmd_status(client):
    model = (await client.read_gatt_char(CHAR_MODEL)).decode("ascii")
    version = (await client.read_gatt_char(CHAR_VERSION)).decode("ascii")
    status_raw = (await client.read_gatt_char(CHAR_STATUS)).decode("ascii")
    settings = (await client.read_gatt_char(CHAR_SETTINGS)).decode("ascii")
    cmd_val = (await client.read_gatt_char(CHAR_COMMAND))
    playlist = (await client.read_gatt_char(CHAR_PLAYBACK)).decode("ascii", errors="replace")

    status = STATUS_MAP.get(status_raw, f"unknown ({status_raw})")
    speed = cmd_val[1] if len(cmd_val) >= 2 and cmd_val[0] == CMD_SPEED else "?"

    print(f"  Model:    {model}")
    print(f"  Firmware: {version}")
    print(f"  Status:   {status}")
    print(f"  Settings: {settings}")
    print(f"  Command:  {cmd_val.hex()}")
    print(f"  Playlist: {playlist}")


async def keep_alive():
    """Block until Ctrl+C."""
    stop = asyncio.Event()
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, stop.set)
    loop.add_signal_handler(signal.SIGTERM, stop.set)
    print("Connection held open. Press Ctrl+C to disconnect.")
    await stop.wait()
    print("\nDisconnecting...")


async def interactive_mode(client):
    """Interactive REPL for controlling the Sandsara."""
    print("\nSandsara Mini Pro - Interactive Mode")
    print("Commands: play, pause, next, sleep, speed <0-100>,")
    print("          led on, led off, led <hex>, gradient <hex1> <hex2>,")
    print("          status, quit")
    print()

    while True:
        try:
            line = await asyncio.get_event_loop().run_in_executor(None, lambda: input("sandsara> "))
        except (EOFError, KeyboardInterrupt):
            break

        parts = line.strip().split()
        if not parts:
            continue

        cmd = parts[0].lower()
        try:
            if cmd == "play":
                await cmd_play(client)
            elif cmd == "pause":
                await cmd_pause(client)
            elif cmd == "next":
                await cmd_next(client)
            elif cmd == "sleep":
                await cmd_sleep(client)
            elif cmd == "speed" and len(parts) >= 2:
                await cmd_speed(client, int(parts[1]))
            elif cmd == "led" and len(parts) >= 2:
                if parts[1] == "on":
                    await cmd_led_on(client)
                elif parts[1] == "off":
                    await cmd_led_off(client)
                else:
                    await cmd_led_color(client, parts[1])
            elif cmd == "gradient" and len(parts) >= 3:
                await cmd_led_gradient(client, parts[1], parts[2])
            elif cmd == "status":
                await cmd_status(client)
            elif cmd in ("quit", "exit", "q"):
                break
            else:
                print("Unknown command. Try: play, pause, next, sleep, speed, led, gradient, status, quit")
        except Exception as e:
            print(f"Error: {e}")


async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    action = sys.argv[1].lower()

    if action == "scan":
        addr = await find_sandsara(timeout=15)
        if addr:
            print(f"\nTo connect, make sure the device is not paired to another phone/device.")
        return

    # Find and connect
    addr = await find_sandsara()
    if not addr:
        return

    print(f"Connecting to {addr}...")
    async with BleakClient(addr, timeout=20) as client:
        print("Connected. Running init sequence...")
        await connect_and_init(client)
        print("Ready.\n")

        if action == "play":
            await cmd_play(client)
            await keep_alive()
        elif action == "pause":
            await cmd_pause(client)
        elif action == "next":
            await cmd_next(client)
            await keep_alive()
        elif action == "sleep":
            await cmd_sleep(client)
        elif action == "speed" and len(sys.argv) >= 3:
            await cmd_speed(client, int(sys.argv[2]))
            await keep_alive()
        elif action == "led":
            if len(sys.argv) >= 3:
                sub = sys.argv[2].lower()
                if sub == "on":
                    await cmd_led_on(client)
                elif sub == "off":
                    await cmd_led_off(client)
                elif sub == "color" and len(sys.argv) >= 4:
                    await cmd_led_color(client, sys.argv[3])
                elif sub == "gradient" and len(sys.argv) >= 5:
                    await cmd_led_gradient(client, sys.argv[3], sys.argv[4])
                else:
                    await cmd_led_color(client, sub)
            await keep_alive()
        elif action == "status":
            await cmd_status(client)
        elif action == "interactive":
            await interactive_mode(client)
        elif action == "daemon":
            await cmd_play(client)
            print("Daemon mode: playing and keeping connection alive.")
            await keep_alive()
        else:
            print(__doc__)

        await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(main())
