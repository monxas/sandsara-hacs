#!/usr/bin/env python3
"""
Sandsara test server: holds BLE connection and watches a command file.
Write a command to /tmp/sandsara_cmd to execute it.
"""
import asyncio
import os
from datetime import datetime
from bleak import BleakClient, BleakScanner

SANDSARA_SERVICE = "fd31a2be-22e7-11eb-adc1-0242ac120002"
CHAR_COMMAND  = "e914c2c0-cde3-4939-adb2-ca61a3cc9b4e"
CHAR_PLAYBACK = "10b59496-bf86-44a8-ba7a-67d8e26a93eb"
CHAR_DATETIME = "0ecc71c5-20a8-462f-92d0-0618c5051cf0"
CHAR_SETTINGS = "20e01699-0346-45c7-91ae-3ebd8a16a2e6"
CHAR_STATUS   = "9e23e02e-8921-4bf9-84f5-f58fa81c726e"
CHAR_8        = "9d277d03-0855-4d8c-8687-316ebca89a61"
CHAR_9        = "eb940790-03f8-406d-bfc4-2f232cf65f84"

CHAR_MAP = {
    "cmd": CHAR_COMMAND, "pb": CHAR_PLAYBACK, "dt": CHAR_DATETIME,
    "settings": CHAR_SETTINGS, "status": CHAR_STATUS,
    "c8": CHAR_8, "c9": CHAR_9,
}

CMD_FILE = "/tmp/sandsara_cmd"
LOG_FILE = "/tmp/sandsara_log"

def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

async def main():
    log("Scanning...")
    devices = await BleakScanner.discover(timeout=10, return_adv=True)
    addr = None
    for a, (dev, adv) in devices.items():
        if any(SANDSARA_SERVICE in u.lower() for u in (adv.service_uuids or [])):
            addr = a
            break
    if not addr:
        log("Not found")
        return

    log(f"Connecting to {addr}...")
    async with BleakClient(addr, timeout=20) as client:
        def on_notify(sender, data):
            uuid_str = str(sender.uuid) if hasattr(sender, 'uuid') else str(sender)
            short = uuid_str.split('-')[0]
            log(f"  NOTIFY [{short}]: {data.hex()} ({list(data)})")

        for service in client.services:
            for char in service.characteristics:
                if "notify" in char.properties:
                    try: await client.start_notify(char.uuid, on_notify)
                    except: pass

        await client.write_gatt_char(CHAR_DATETIME, bytes([0x00]), response=True)
        await client.write_gatt_char(CHAR_PLAYBACK, bytes([0x00]), response=True)
        await client.write_gatt_char(CHAR_COMMAND, bytes([0x00]), response=True)
        now = datetime.now().isoformat()
        await client.write_gatt_char(CHAR_DATETIME, b"\x04" + now.encode("ascii"), response=True)
        await asyncio.sleep(0.5)

        log("Connected and initialized. Waiting for commands in /tmp/sandsara_cmd")
        log("Commands: play, pause, next, sleep, speed <N>, led_on, led_off, led <hex>, gradient <h1> <h2>, quit")

        # Remove stale command file
        try: os.remove(CMD_FILE)
        except: pass

        while client.is_connected:
            if os.path.exists(CMD_FILE):
                with open(CMD_FILE) as f:
                    cmd = f.read().strip()
                os.remove(CMD_FILE)
                if not cmd:
                    continue
                log(f"CMD: {cmd}")
                parts = cmd.split()
                action = parts[0].lower()
                try:
                    if action == "play":
                        await client.write_gatt_char(CHAR_PLAYBACK, bytes([0x07]), response=True)
                        log("-> Play sent")
                    elif action == "pause":
                        await client.write_gatt_char(CHAR_PLAYBACK, bytes([0x08]), response=True)
                        log("-> Pause sent")
                    elif action == "next":
                        await client.write_gatt_char(CHAR_PLAYBACK, bytes([0x06]), response=True)
                        log("-> Next sent")
                    elif action == "sleep":
                        await client.write_gatt_char(CHAR_PLAYBACK, bytes([0x04]), response=True)
                        log("-> Sleep sent")
                    elif action == "speed" and len(parts) >= 2:
                        v = max(0, min(100, int(parts[1])))
                        await client.write_gatt_char(CHAR_COMMAND, bytes([0x05, v]), response=True)
                        log(f"-> Speed {v} sent")
                    elif action == "led_on":
                        await client.write_gatt_char(CHAR_COMMAND, bytes([0x06, 0x01]), response=True)
                        log("-> LED on sent")
                    elif action == "led_off":
                        await client.write_gatt_char(CHAR_COMMAND, bytes([0x06, 0x00]), response=True)
                        log("-> LED off sent")
                    elif action == "led" and len(parts) >= 2:
                        h = parts[1].lstrip("#")
                        r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
                        await client.write_gatt_char(CHAR_COMMAND, bytes([0x07, 0x01, 0x01, r, g, b]), response=True)
                        log(f"-> LED #{h} sent")
                    elif action == "gradient" and len(parts) >= 3:
                        h1, h2 = parts[1].lstrip("#"), parts[2].lstrip("#")
                        r1,g1,b1 = int(h1[0:2],16),int(h1[2:4],16),int(h1[4:6],16)
                        r2,g2,b2 = int(h2[0:2],16),int(h2[2:4],16),int(h2[4:6],16)
                        await client.write_gatt_char(CHAR_COMMAND, bytes([0x07,0x02,0x00,0xff,r1,r2,g1,g2,b1,b2]), response=True)
                        log(f"-> Gradient #{h1} -> #{h2} sent")
                    elif action == "raw" and len(parts) >= 3:
                        char_name = parts[1]
                        data = bytes.fromhex(parts[2])
                        char_uuid = CHAR_MAP.get(char_name, CHAR_COMMAND)
                        await client.write_gatt_char(char_uuid, data, response=True)
                        log(f"-> Raw {char_name} {data.hex()} sent")
                    elif action == "read" and len(parts) >= 2:
                        char_name = parts[1]
                        char_uuid = CHAR_MAP.get(char_name)
                        if char_uuid:
                            val = await client.read_gatt_char(char_uuid)
                            log(f"-> Read {char_name}: {val.hex()} | ascii={val.decode('ascii','replace')} | list={list(val)}")
                        else:
                            log(f"Unknown char: {char_name}. Use: {list(CHAR_MAP.keys())}")
                    elif action == "write" and len(parts) >= 3:
                        char_name = parts[1]
                        char_uuid = CHAR_MAP.get(char_name)
                        if char_uuid:
                            if parts[2].startswith('"') or parts[2].startswith("'"):
                                data = " ".join(parts[2:]).strip("'\"").encode("ascii")
                            else:
                                data = bytes.fromhex(parts[2])
                            await client.write_gatt_char(char_uuid, data, response=True)
                            log(f"-> Write {char_name}: {data.hex()} | ascii={data.decode('ascii','replace')}")
                        else:
                            log(f"Unknown char: {char_name}. Use: {list(CHAR_MAP.keys())}")
                    elif action == "readall":
                        for name, uuid in CHAR_MAP.items():
                            try:
                                val = await client.read_gatt_char(uuid)
                                log(f"  {name}: {val.hex()} | ascii={val.decode('ascii','replace')} | list={list(val)}")
                            except Exception as e:
                                log(f"  {name}: ERROR {e}")
                    elif action == "quit":
                        log("Quitting")
                        break
                    else:
                        log(f"Unknown command: {cmd}")
                except Exception as e:
                    log(f"Error: {e}")
            await asyncio.sleep(0.3)

asyncio.run(main())
