# Sandsara Mini Pro - File Transfer Protocol

**Status:** Reverse-engineered (needs testing)
**Last updated:** 2026-02-06

---

## Overview

The Sandsara Mini Pro uses a chunked file transfer protocol over BLE GATT. This protocol is based on the original Sandsara firmware (found in `research/Bluetooth.cpp`) but with some modifications for the Mini Pro.

The protocol allows:
- Sending pattern files (`.bin`) to the device
- Sending playlist files (`.playlist`) to the device
- Checking if files exist
- Deleting files
- Reading files from the device (optional)

---

## BLE Service & Characteristics

### Service: File Transfer
**UUID:** `fd31abc4-22e7-11eb-adc1-0242ac120002`

| Characteristic | UUID | Properties | Purpose |
|----------------|------|------------|---------|
| File Flag | `fcbff68e-2af1-11eb-adc1-0242ac120002` | write, notify | Start/end file transfer |
| File Data | `fcbffa44-2af1-11eb-adc1-0242ac120002` | write, notify | Send file chunks |
| File Unknown | `27566b01-59c3-4a6f-a40e-c35606b0a29b` | write, notify | Unknown (maybe file info?) |
| File Status | `250e79ac-f0d7-43cc-ad6a-63544b5c6663` | write, notify, read | Transfer status |

### Firmware Original UUIDs (for reference)
The original firmware defines these additional characteristics (may not all exist on Mini Pro):
- `fcbffb52-...` - Check if file exists
- `fcbffc24-...` - Delete file
- `fcbffdaa-...` - Send flag (for reading files)
- `fcbffe72-...` - Send data (for reading files)
- `fcbffce2-...` - Error messages

---

## Protocol: Sending a File to Device

Based on `FilesCallbacks_receiveFlag` and `FilesCallbacks_receive` from firmware source.

### Step 1: Start Transfer

Write the filename to the **File Flag** characteristic:
```
CHAR_FILE_FLAG.write(filename.encode('ascii'))
```

Example: `"my-pattern.bin"` → write `6d792d7061747465726e2e62696e`

**Device response (via File Status notification):**
- `"ok"` - File created, ready to receive data
- `"error= -2"` - File cannot be created (SD card issue)

**Note:** If the file already exists, the device will delete it first.

### Step 2: Send Data Chunks

Write binary data in chunks to the **File Data** characteristic:
- Maximum chunk size: **512 bytes** (limited by BLE MTU)
- The device buffers up to 9KB before writing to SD card

```python
for chunk in split_into_chunks(file_data, 512):
    await CHAR_FILE_DATA.write(chunk)
    # Wait for notification "1" as acknowledgment
    await wait_for_notification()
```

**Device response (via File Data notification):**
- `"1"` (bytes `0x31`) - Chunk received, ready for next

### Step 3: End Transfer

Write any byte to the **File Flag** characteristic to signal completion:
```
CHAR_FILE_FLAG.write(b'\x00')  # or any value
```

**Device response (via File Status notification):**
- `"done"` - File saved successfully

---

## Protocol: Check if File Exists

**Note:** This may use the `27566b01` characteristic or not be available on Mini Pro.

Original firmware protocol:
1. Write filename to Check File characteristic (`fcbffb52-...`)
2. Wait for notification on Error Message characteristic
3. Response: `"1"` = exists, `"0"` = not found

---

## Protocol: Delete File

Original firmware protocol:
1. Write filename to Delete File characteristic (`fcbffc24-...`)
2. Wait for notification on Error Message characteristic
3. Response: `"1"` = deleted, `"0"` = not found

---

## Pattern File Format

See `research/patterns/README.md` for full details.

### Structure
- No header, raw binary data
- 6 bytes per coordinate point
- Big-endian unsigned 16-bit integers

### Point Format (6 bytes)
```
Offset  Type    Description
0-1     uint16  Theta (angle): 0-65535 → 0-360°
2-3     uint16  Rho (radius): 0x2C00-0x2CFF (actual radius in low byte)
4-5     uint16  Counter/timing (purpose unclear)
```

### Filename Convention
- Patterns: `Sandsara-trackNumber-XXXX.bin` (XXXX = 4-digit number)
- Playlists: `name.playlist` (text file with pattern filenames)

---

## Playlist File Format

Plain text file listing pattern filenames, one per line:
```
Sandsara-trackNumber-0001.bin
Sandsara-trackNumber-0002.bin
my-custom-pattern.bin
```

To play a playlist, write its name (without extension) to the playlist name characteristic.

---

## Implementation Notes

### BLE Connection
1. Must use **Write Request** (`response=True`), not Write Command
2. Must enable notifications before starting transfer
3. Connection must remain active during transfer
4. Device pauses playback during file reception

### Chunk Size
- Firmware uses 512 bytes max per chunk
- BLE MTU may limit this further (typically 512 on modern devices)
- Device buffers ~9KB before writing to SD card

### Error Handling
- If BLE disconnects during transfer, the partial file is deleted
- Device tracks `receiveFlag` state to detect incomplete transfers

### Status During Transfer
When receiving a file, the device:
1. Sets `pauseModeGlobal = true` (pauses playback)
2. Keeps track of `receiveFlag` state
3. Buffers data until 9KB accumulated
4. Writes to SD card in batches
5. Resumes playback after transfer completes

---

## Unknown Aspects

1. **`27566b01` characteristic** - Purpose unclear. May be:
   - File metadata/info
   - Transfer progress
   - Alternative status channel

2. **`250e79ac` characteristic** - Labeled as "status" but exact semantics unknown

3. **Mini Pro specific changes** - The Mini Pro may have:
   - Different chunk sizes
   - Different acknowledgment format
   - Additional validation

---

## Testing Checklist

- [ ] Discover and confirm all File Transfer service characteristics
- [ ] Test sending a small pattern file
- [ ] Verify file appears in device's playlist
- [ ] Test transfer cancellation/recovery
- [ ] Measure optimal chunk size for Mini Pro
- [ ] Identify purpose of `27566b01` characteristic

---

## References

- `research/Bluetooth.cpp` - Original firmware source
- `research/libapp_file_transfer_strings.txt` - Flutter app strings
- `research/patterns/` - Pattern file analysis
- `docs/PROTOCOL_NOTES.md` - Main protocol documentation
