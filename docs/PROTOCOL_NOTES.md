# Sandsara Mini Pro BLE Protocol - Reverse Engineering Notes

**Last updated:** 2026-02-03
**Device:** Sandsara Mini Pro
**Firmware:** v6.3.1
**Model string:** "mini"
**BLE MAC (from phone HCI):** 94:b9:7e:f1:10:76 (Espressif ESP32)
**macOS BLE identifier:** CA154077-B968-BA29-B9A6-03F3E6E56B6F

---

## BLE GATT Profile

### Service: Main (`fd31a2be-22e7-11eb-adc1-0242ac120002`)

| Characteristic | UUID | Properties | Description |
|---|---|---|---|
| CHAR_COMMAND | `e914c2c0-cde3-4939-adb2-ca61a3cc9b4e` | write, notify, read | Main command char (LED, brightness, speed, etc.) |
| CHAR_PLAYBACK | `10b59496-bf86-44a8-ba7a-67d8e26a93eb` | write, notify, read | Playback control (play/pause/next/sleep) |
| CHAR_DATETIME | `0ecc71c5-20a8-462f-92d0-0618c5051cf0` | write, notify, read | Datetime sync + device info |
| CHAR_MODEL | `caf74386-dd8b-4f54-9dd9-71c75f6d679a` | read | Model name (returns "mini") |
| CHAR_VERSION | `7b204278-30c3-11eb-adc1-0242ac120002` | read | Firmware version (returns "6.3.1") |
| CHAR_STATUS | `9e23e02e-8921-4bf9-84f5-f58fa81c726e` | read | Device status code (ASCII) |
| CHAR_SETTINGS | `20e01699-0346-45c7-91ae-3ebd8a16a2e6` | write, read | Settings CSV string (read-only in practice) |
| CHAR_POSITION | `9d277d03-0855-4d8c-8687-316ebca89a61` | write, notify, read | Unknown (writing 0x00 crashes connection!) |
| CHAR_SENSOR | `eb940790-03f8-406d-bfc4-2f232cf65f84` | write, notify, read | Sensor/position data (floods notifications every ~1s) |

### Service: File Transfer (`fd31abc4-22e7-11eb-adc1-0242ac120002`)

| Characteristic | UUID | Properties | Description |
|---|---|---|---|
| File send flag | `fcbff68e-...` | write, notify | File transfer flag |
| File unknown | `27566b01-...` | write, notify | Unknown |
| File send data | `fcbffa44-...` | write, notify | File data transfer |
| File status | `250e79ac-...` | write, notify, read | File transfer status |

---

## Connection Init Sequence (REQUIRED)

All writes MUST use **Write Request** (`response=True`), NOT Write Command. The device ignores Write Commands.

1. Enable notifications on ALL notify-capable characteristics (write 0x0100 to their CCCDs)
2. Write `0x00` to CHAR_DATETIME
3. Write `0x00` to CHAR_PLAYBACK
4. Write `0x00` to CHAR_COMMAND
5. Write `0x04` + ISO timestamp (ASCII) to CHAR_DATETIME
   - Example: `\x04` + `"2026-02-02T21:43:23.353032"`
6. Wait ~500ms for device to send init notifications

**CRITICAL:** The device requires a persistent BLE connection. It stops when you disconnect.

### Init Notifications Received

After init, the device sends several notification bursts:

1. **CHAR_COMMAND** `0xFF` - connection ACK
2. **CHAR_PLAYBACK** `0xFF` - connection ACK
3. **CHAR_DATETIME** `0xFF` - connection ACK
4. **CHAR_PLAYBACK** `0x03 "1,-1"` - status (3=paused) + current track info
5. **CHAR_SENSOR** `0x07 0x00` - sensor init
6. **CHAR_DATETIME** `0x0B "100,0"` - settings (brightness=100, unknown=0)
7. **CHAR_DATETIME** `0x00 "Sand Sandsara Mini" ... "25252525" ... "1809,0"` - device info blob
8. **CHAR_DATETIME** `0xFE` - init complete
9. **CHAR_PLAYBACK** `0x00 0xFF ... "1,-1" ...` - full playlist state
10. **CHAR_COMMAND** config blob (see below)
11. **CHAR_DATETIME** `0xFE` - final ACK

---

## Confirmed Commands

### Playback Control (write to CHAR_PLAYBACK)

| Byte | Command | Status |
|---|---|---|
| `0x00` | Init | CONFIRMED |
| `0x04` | Sleep | CONFIRMED |
| `0x06` | Next track | CONFIRMED |
| `0x07` | Play | CONFIRMED |
| `0x08` | Pause | CONFIRMED |

**WARNING:** Writing any other command byte (e.g., 0x01, 0x02, 0x03, 0x05) to CHAR_PLAYBACK will crash/disconnect the device!

### Command Characteristic (write to CHAR_COMMAND)

| Bytes | Command | Config Blob Position | Status |
|---|---|---|---|
| `0x00` | Init | - | CONFIRMED |
| `0x01 <value>` | LED animation speed (0-100) | Byte 1 | CONFIRMED |
| `0x02 <value>` | Ball/motor speed (0-100) | Byte 2 | CONFIRMED |
| `0x05 <value>` | LED brightness (0-100) | Byte 5 | CONFIRMED |
| `0x06 0x01` | LED on | Byte 6 (indirectly) | CONFIRMED |
| `0x06 0x00` | LED off | Byte 6 (indirectly) | CONFIRMED |
| `0x07 <color data>` | LED color (gradient format) | Byte 7+ | CONFIRMED |

### Config Notification Blob (from CHAR_COMMAND after init)

```
Byte 0:  0x00  = blob type (config dump)
Byte 1:  LED animation speed (0-100, default 72)
Byte 2:  Ball/motor speed (0-100, default 50)
Byte 3:  0x01  = unknown (always 1)
Byte 4:  0x01  = unknown (always 1)
Byte 5:  LED brightness (0-100)
Byte 6:  Playing status (1=playing, 0=paused)
Byte 7:  Color count (from color command)
Byte 8:  Color count (duplicate?)
Byte 9:  Position 1 (e.g., 0x00 = start)
Byte 10: Position 2 (e.g., 0xFF = end)
Byte 11+: RGB color data (R1 R2 G1 G2 B1 B2 per color pair)
```

Example: `00 48 32 01 01 64 01 02 02 00 FF 00 00 00 00 00 00 ...`
= LED speed 72, ball speed 50, brightness 100, playing, 2-color gradient

### LED Color Format (IMPORTANT)

Solid color with count=1 (`0x07 0x01 0x01 R G B`) does **NOT** work on Mini Pro.

Must use gradient format with count=2 and same color on both ends:
```
0x07 0x02 0x00 0xFF R R G G B B
```
- Byte 0: `0x07` (LED color command)
- Byte 1: `0x02` (count = 2 color stops)
- Byte 2: `0x00` (position 1 = start)
- Byte 3: `0xFF` (position 2 = end)
- Bytes 4-5: R1, R2
- Bytes 6-7: G1, G2
- Bytes 8-9: B1, B2

For solid red: `07 02 00 FF FF FF 00 00 00 00`
For gradient red->blue: `07 02 00 FF FF 00 00 00 00 FF`

### Status Codes (read from CHAR_STATUS)

| Value | Meaning |
|---|---|
| "1" | Calibrating |
| "2" | Playing |
| "3" | Paused |
| "4" | Sleeping |
| "5" | Busy |

### Settings (read from CHAR_SETTINGS)

Returns CSV string like: `"100,0,1,0000000000000"`
- Field 0: LED brightness (mirrors CMD 0x05 value)
- Field 1: `0` - unknown
- Field 2: `1` - unknown (possibly LED on/off state)
- Field 3: `0000000000000` - 13 zeros, unknown

Note: Writing to CHAR_SETTINGS appears to be accepted but the value does NOT persist (reads back as original).

### Sensor Data (CHAR_SENSOR notifications)

Sends 9-byte packets every ~1 second:
```
Byte 0: 0x08 (packet type)
Bytes 1-4: 32-bit value (position/angle?)
Bytes 5-8: 32-bit value (position/angle?)
```
Example: `08 EB 01 00 00 E1 01 00 00` = type 8, values 491 and 481

---

## Dangerous Operations

- **DO NOT** write to CHAR_POSITION (`9d277d03`): Writing `0x00` crashes/disconnects the device
- **DO NOT** write unrecognized commands to CHAR_PLAYBACK: Only 0x00, 0x04, 0x06, 0x07, 0x08 are safe
- The device may become temporarily unavailable (stops advertising) after a crash. Wait 10-30 seconds.

---

## Tools & Scripts

### `sandsara_controller.py`
Full CLI controller. Usage:
```
python3 sandsara_controller.py scan|play|pause|next|sleep|speed <N>|led on|off|color <hex>|gradient <h1> <h2>|status|interactive|daemon
```

### `sandsara_test_server.py`
Persistent BLE connection server. Watches `/tmp/sandsara_cmd` for commands, logs to `/tmp/sandsara_log`.
```
# Start server:
python3 sandsara_test_server.py

# Send commands (from another terminal):
echo "play" > /tmp/sandsara_cmd
echo "led ff0000" > /tmp/sandsara_cmd
echo "raw cmd 0564" > /tmp/sandsara_cmd    # raw hex to command char
echo "raw pb 07" > /tmp/sandsara_cmd       # raw hex to playback char
echo "raw c8 XX" > /tmp/sandsara_cmd       # raw hex to any char (c8, c9, dt, settings)
echo "read settings" > /tmp/sandsara_cmd   # read a characteristic
echo "readall" > /tmp/sandsara_cmd         # read all characteristics
echo "quit" > /tmp/sandsara_cmd
```

---

## Key Files

| File | Description |
|---|---|
| `sandsara_controller.py` | Main CLI controller script |
| `sandsara_test_server.py` | Persistent connection test server |
| `split_arm/lib/armeabi-v7a/libapp.so` | Decompiled Flutter app binary (strings extracted) |
| `~/Desktop/bugreport_extracted/FS/data/misc/bluetooth/logs/BT_HCI_*.curf` | HCI snoop capture |
| `~/Desktop/firmwareSandsara/` | Original firmware source (different UUIDs, older hardware) |
| `~/Desktop/SandsaraApp-Android/` | Official app source (original firmware UUIDs only) |

---

## Key Discoveries & Gotchas

1. **Write Request required** - `response=True` in bleak. Device ignores Write Command (response=False).
2. **Persistent connection** - Device stops working when BLE disconnects.
3. **Solid color broken** - Must use gradient format (count=2, same color both ends) for solid colors.
4. **Not the old firmware** - Mini Pro uses completely different UUIDs than the open-source original firmware.
5. **Flutter binary** - Real protocol logic is in compiled Dart (libapp.so), not in Java layer of APK.
6. **ESP32 chip** - Advertises as Espressif in HCI logs, not as "Sandsara". Find by service UUID.
7. **Notifications init** - Must enable notifications on all chars before sending commands.
8. **Crash-prone** - Writing wrong commands to CHAR_PLAYBACK or CHAR_POSITION crashes the device.
9. **CMD 0x02 is ball speed** - Separate from brightness (CMD 0x05) and LED speed (CMD 0x01).
10. **Settings read-only** - CHAR_SETTINGS CSV reflects brightness but writes don't persist.

---

## Complete Command Reference

### CHAR_COMMAND (`e914c2c0`)
| CMD | Payload | Range | Function |
|-----|---------|-------|----------|
| 0x00 | none | - | Init handshake |
| 0x01 | 1 byte | 0-100 | LED animation speed |
| 0x02 | 1 byte | 0-100 | Ball/motor speed |
| 0x05 | 1 byte | 0-100 | LED brightness |
| 0x06 | 1 byte | 0 or 1 | LED off/on |
| 0x07 | 9 bytes | see format | LED color (gradient) |

### CHAR_PLAYBACK (`10b59496`)
| CMD | Payload | Function |
|-----|---------|----------|
| 0x00 | none | Init handshake |
| 0x04 | none | Sleep |
| 0x06 | none | Next track |
| 0x07 | none | Play |
| 0x08 | none | Pause |

### CHAR_DATETIME (`0ecc71c5`)
| CMD | Payload | Function |
|-----|---------|----------|
| 0x00 | none | Init handshake |
| 0x04 | ISO timestamp ASCII | Set datetime |
