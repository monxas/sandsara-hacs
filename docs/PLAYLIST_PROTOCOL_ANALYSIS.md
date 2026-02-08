# Sandsara Mini Pro — Playlist & Pattern Protocol Analysis

**Date:** 2026-02-08
**Sources:** Firmware source (`Bluetooth.cpp`/`.h`), Flutter app strings (`libapp_file_transfer_strings.txt`), HACS integration code, existing protocol docs, HCI sniff data.

---

## 1. Complete BLE Characteristic Map

### IMPORTANT: Two Firmware Generations

The Sandsara Mini Pro runs **new firmware** with different UUIDs than the original open-source firmware. The original firmware source (`Bluetooth.cpp`) documents the **old protocol**. The Mini Pro has a **simplified/consolidated** GATT profile.

#### Mini Pro (Actual Device) — Service: `fd31a2be-22e7-11eb-adc1-0242ac120002`

| Characteristic | UUID | R/W/N | Data Format | Purpose |
|---|---|---|---|---|
| CHAR_COMMAND | `e914c2c0-cde3-4939-adb2-ca61a3cc9b4e` | R/W/N | Binary: `[cmd_byte, params...]` | LED speed, ball speed, brightness, LED toggle, LED color |
| CHAR_PLAYBACK | `10b59496-bf86-44a8-ba7a-67d8e26a93eb` | R/W/N | Binary: `[cmd_byte]` | Play/pause/next/sleep + playlist state notifications |
| CHAR_DATETIME | `0ecc71c5-20a8-462f-92d0-0618c5051cf0` | R/W/N | `[cmd_byte, ASCII...]` | Datetime sync, device info blob, settings |
| CHAR_MODEL | `caf74386-dd8b-4f54-9dd9-71c75f6d679a` | R | ASCII string | Model name ("mini") |
| CHAR_VERSION | `7b204278-30c3-11eb-adc1-0242ac120002` | R | ASCII string | Firmware version ("6.3.1") |
| CHAR_STATUS | `9e23e02e-8921-4bf9-84f5-f58fa81c726e` | R | ASCII digit | Status: 1=calibrating, 2=playing, 3=paused, 4=sleeping, 5=busy |
| CHAR_SETTINGS | `20e01699-0346-45c7-91ae-3ebd8a16a2e6` | R/W | CSV ASCII | Settings string (read-only in practice) |
| CHAR_POSITION | `9d277d03-0855-4d8c-8687-316ebca89a61` | R/W/N | Binary | ⚠️ DANGEROUS — writing 0x00 crashes device |
| CHAR_SENSOR | `eb940790-03f8-406d-bfc4-2f232cf65f84` | R/W/N | Binary 9 bytes | Sensor/position data, floods every ~1s |

#### Mini Pro — File Transfer Service: `fd31abc4-22e7-11eb-adc1-0242ac120002`

| Characteristic | UUID | R/W/N | Purpose |
|---|---|---|---|
| File Flag | `fcbff68e-2af1-11eb-adc1-0242ac120002` | W/N | Start/end file receive transfer |
| File Unknown | `27566b01-59c3-4a6f-a40e-c35606b0a29b` | W/N | Unknown — possibly device info or file metadata |
| File Data | `fcbffa44-2af1-11eb-adc1-0242ac120002` | W/N | File chunk data (512-byte chunks) |
| File Status | `250e79ac-f0d7-43cc-ad6a-63544b5c6663` | R/W/N | Transfer status |

**Note:** The File Transfer service reuses some UUIDs from the original firmware (`fcbff68e` = FILE_UUID_RECEIVEFLAG, `fcbffa44` = FILE_UUID_RECEIVE). However, only 4 of the original 7 file characteristics are present on the Mini Pro.

#### Original Firmware File Characteristics (NOT confirmed on Mini Pro)

| Characteristic | UUID | Purpose | Status on Mini Pro |
|---|---|---|---|
| ReceiveFlag | `fcbff68e-...` | Start/end file receive | ✅ Present |
| Receive | `fcbffa44-...` | Chunk data for receive | ✅ Present |
| Exists | `fcbffb52-...` | Check if file exists | ❌ NOT found |
| Delete | `fcbffc24-...` | Delete file | ❌ NOT found |
| SendFlag | `fcbffdaa-...` | Start reading file from device | ❌ NOT found |
| Send | `fcbffe72-...` | Read chunk data from device | ❌ NOT found |
| ErrorMsg | `fcbffce2-...` | Error messages for file ops | ❌ NOT found |

#### Original Firmware Playlist Characteristics (NOT on Mini Pro as separate chars)

Service UUID: `fd31a778-22e7-11eb-adc1-0242ac120002`

| Characteristic | UUID | R/W | Purpose |
|---|---|---|---|
| PlaylistName | `9b12a048-2c6e-11eb-adc1-0242ac120002` | R/W | Set/get current playlist name |
| PathAmount | `9b12a26e-2c6e-11eb-adc1-0242ac120002` | R | Number of tracks in current playlist |
| PathName | `9b12a534-2c6e-11eb-adc1-0242ac120002` | R/W | Set/get current track filename |
| PathPosition | `9b12a62e-2c6e-11eb-adc1-0242ac120002` | R/W | Set/get current track index (1-based) |
| AddPath | `9b12a7be-2c6e-11eb-adc1-0242ac120002` | W | Append track to current playlist |
| Mode | `9b12a886-2c6e-11eb-adc1-0242ac120002` | W | Playlist order mode |
| Progress | `9b12a944-2c6e-11eb-adc1-0242ac120002` | R/N | Track progress (0-100%) |
| ErrorMsg | `9b12aa02-2c6e-11eb-adc1-0242ac120002` | R/N | Playlist error messages |

**These are NOT exposed as separate characteristics on the Mini Pro.** The Mini Pro consolidated playlist control into CHAR_PLAYBACK notifications.

---

## 2. Playlist Management Protocol

### What We Know (from firmware source — original protocol)

The original firmware's playlist system works like this:

1. **Playlists are text files** on the SD card with `.playlist` extension
2. A playlist file contains one pattern filename per line:
   ```
   Sandsara-trackNumber-0001.bin
   Sandsara-trackNumber-0002.bin
   my-custom-pattern.bin
   ```
3. **Selecting a playlist:** Write playlist name (WITHOUT `.playlist` extension) to `PLAYLIST_UUID_NAME` (`9b12a048`)
   - Device appends `.playlist` and looks for that file on SD card
   - Responds "ok" or "error= -1" (not found) via `PLAYLIST_UUID_ERRORMSG`
   - Sets `orderModeGlobal = 1` (sequential) and rewinds
4. **Default playlist:** `DEFAULTPLAYLIST` constant (value unknown, probably `/default.playlist`)
   - Deleted when switching to a non-default playlist

### How It Works on Mini Pro (from HCI sniffing)

The Mini Pro reports playlist state via **CHAR_PLAYBACK notifications**:

- **Init notification:** `0x03 "1,-1"` → status 3 (paused), track info "1,-1"
- **Full state notification:** `0x00 0xFF ... "1,-1" ...` → full playlist state blob

The `"1,-1"` format appears to be `"<track_position>,<total_tracks_or_status>"`. The `-1` may indicate "unknown" or "no playlist loaded."

### Gap Analysis

❓ **How does the app on Mini Pro select a playlist?** The old firmware used dedicated characteristics (`9b12a048`). The Mini Pro doesn't expose these. Possibilities:
1. Playlist selection is encoded as a sub-command of CHAR_PLAYBACK (e.g., `0x01`, `0x02`, `0x03`, `0x05` — the "dangerous" bytes we haven't tested)
2. The app creates/modifies playlist files via file transfer, then triggers a restart/refresh
3. Playlist commands go through CHAR_DATETIME or an undiscovered protocol

### Flutter App Evidence

From `libapp_file_transfer_strings.txt`:
- `PlaylistConfig` — class for playlist configuration
- `PlaylistConfig._internal@899189875` — internal constructor
- `_readPlaylist@899189875` — reads playlist data
- `_parsePlaylistInfo@8991898752` — parses playlist info
- `PlaylistOPCode` — enum/class for playlist operation codes
- `Playlist sent successfully` / `Failed to send playlist`
- `sendPlaylist2` — method to send playlist
- `reorderPlaylist` — reorder playlist items
- `delPlaylistItem` — delete playlist item
- `Playlist must have at least one item`
- `Empty playlist, nothing to send`
- `New playlist:` — creating new playlist
- `Playlist to send:` — about to transmit
- `Playlist parsed:` / `Failed to parse playlist`
- `Error writing playlist data:`
- `Error handling playlist notification:`
- `Playlist Configuration Updated:`
- `Device config and playlist config initialized`
- `Failed to get playlist characteristic`

This confirms:
- The app has a full playlist management system
- It uses "op codes" (`PlaylistOPCode`) — suggesting a command-based protocol
- It sends complete playlists to the device
- It can reorder and delete individual items
- There's a dedicated "playlist characteristic" the app looks for

---

## 3. Pattern Selection Protocol

### Original Firmware (Confirmed from Source)

Two methods to play a specific pattern:

#### Method A: By Filename (temporary play)
Write filename to `PLAYLIST_UUID_PATHNAME` (`9b12a534`):
- Device plays that file immediately
- When done, **returns to the previous playlist position**
- Used for "preview/test" of a single pattern
- Errors: "-2" (invalid filename), "-3" (file doesn't exist)

#### Method B: By Position (permanent switch)
Write track index (1-based integer as ASCII) to `PLAYLIST_UUID_PATHPOSITION` (`9b12a62e`):
- Device jumps to that position in the current playlist
- Continues sequential playback from there
- Resets progress to 0%

### Mini Pro (Partially Confirmed)

- **Next track:** Write `0x06` to CHAR_PLAYBACK ✅ CONFIRMED
- **Jump to position:** Unknown — likely a sub-command of CHAR_PLAYBACK
- **Play by name:** Unknown

From Flutter strings:
- `jumpToPattern` — method name for jumping to a specific pattern
- `pattern selected:` — debug log when pattern is selected
- `selectMusicTrack` — track selection method
- `Play All The Patterns` — UI string suggesting "play all" mode

---

## 4. File Listing Protocol

### Original Firmware

**There is NO file listing capability in the original firmware.** The firmware has no BLE characteristic or command to enumerate files on the SD card.

The original app's approach:
1. App maintains its own database of patterns (`SELECT COUNT(*) FROM patterns`, `SELECT * FROM patterns`)
2. App uses `FILE_UUID_EXISTS` (`fcbffb52`) to check if specific files exist by name
3. Pattern naming convention: `Sandsara-trackNumber-XXXX.bin` (sequential numbering)
4. The app can brute-force check existence by iterating through known filenames

### Mini Pro

The Mini Pro has only 4 file transfer characteristics (vs 7 in original), and notably **lacks** the file-exists check (`fcbffb52`) and file-delete (`fcbffc24`) characteristics.

From Flutter strings:
- `Existing Files (first 10):` — suggests the app does enumerate files somehow
- `Device info payload too short for files array (len=` — the device sends a file list in a payload!
- `File Index: 2` — files are indexed

**Key discovery:** The device appears to send a list of files as part of its initialization payload (possibly in the CHAR_DATETIME `0x00` init blob or through `27566b01`). The app parses this to know what files exist on the device.

---

## 5. File Transfer Protocol (to device)

### Confirmed Protocol (from firmware + Mini Pro testing)

**Sending a file to the device:**

1. Write filename (ASCII) to File Flag (`fcbff68e`)
2. Wait for status notification: `"ok"` = ready, `"error= -2"` = SD card error
3. Write file data in 512-byte chunks to File Data (`fcbffa44`)
4. After each chunk, wait for notification `"1"` on File Data
5. After all chunks sent, write any byte to File Flag to signal completion
6. Wait for status notification: `"done"` = success

**Device behavior during transfer:**
- Pauses playback (`pauseModeGlobal = true`)
- Buffers data up to 9KB before SD card write
- If BLE disconnects mid-transfer, partial file is deleted

### Playlist File Transfer

From Flutter strings:
- `Playlist to send:` / `Playlist sent successfully` / `Failed to send playlist`
- `sendPlaylist2` method
- Playlist files use `.playlist` extension

The app likely:
1. Constructs a `.playlist` file (text, one filename per line)
2. Sends it via the same file transfer protocol
3. Then tells the device to switch to that playlist

---

## 6. What We Know vs What Needs Sniffing

### ✅ CONFIRMED (tested or directly from firmware source)

| Feature | Method | Source |
|---|---|---|
| Play/Pause/Next/Sleep | CHAR_PLAYBACK 0x07/0x08/0x06/0x04 | HCI sniff |
| LED brightness/speed/color | CHAR_COMMAND sub-commands | HCI sniff |
| File transfer (send to device) | File Flag + File Data chunked protocol | Firmware source + partial HCI |
| Playlist format | Text file, `.playlist` extension, one filename per line | Firmware source |
| Pattern file format | 6 bytes/point binary, polar coords | Pattern analysis |
| Status reading | CHAR_STATUS returns "1"-"5" | HCI sniff |
| Init handshake | 0x00 to DT/PB/CMD, then 0x04+timestamp to DT | HCI sniff |

### ❓ NEEDS SNIFFING / TESTING

| Feature | What's Unknown | Priority |
|---|---|---|
| **Playlist selection** | How does Mini Pro switch playlists? Sub-command of CHAR_PLAYBACK? | 🔴 Critical |
| **Track jump by position** | Which command/char jumps to track N in current playlist? | 🔴 Critical |
| **File listing** | How does the app get the list of files from the device? Init blob parsing? | 🔴 Critical |
| **Purpose of `27566b01`** | May be device info, file metadata, or playlist commands | 🟡 High |
| **Purpose of `250e79ac`** | File Status char — exact notification semantics | 🟡 High |
| **CHAR_PLAYBACK sub-commands** | What do 0x01, 0x02, 0x03, 0x05 do? (0x01-0x03, 0x05 crashed before) | 🟡 High |
| **PlaylistOPCode** | What are the op codes? How are they sent? | 🟡 High |
| **File exists/delete on Mini Pro** | Are these features available through different UUIDs? | 🟠 Medium |
| **CHAR_POSITION (`9d277d03`)** | Purpose — crashed when writing 0x00 | 🟠 Medium |
| **Playlist reorder** | How does `reorderPlaylist` work over BLE? | 🟠 Medium |
| **Track progress** | How/where is track progress reported on Mini Pro? | 🟢 Low |

### 🔮 EDUCATED SPECULATION

1. **Playlist selection likely works by:**
   - Sending a `.playlist` file via file transfer
   - Then writing a command to CHAR_PLAYBACK or CHAR_DATETIME to activate it
   - OR: The `27566b01` characteristic is used for playlist commands

2. **File listing likely works via:**
   - The init blob from CHAR_DATETIME includes file metadata
   - The `"Device info payload too short for files array"` string confirms the device sends file info
   - Possibly triggered by writing a specific command to `27566b01` or CHAR_DATETIME

3. **PlaylistOPCode suggests:**
   - There's a structured command protocol for playlist operations
   - Likely sent as binary data to one of the characteristics
   - Operations: create, set active, add track, remove track, reorder

---

## 7. Sniffing Plan

### Setup
1. Enable HCI snoop logging on Android (Developer Options → Enable Bluetooth HCI snoop log)
2. Clear old logs
3. Open Sandsara app, connect to device
4. Perform each operation below, noting timestamps
5. Export HCI log (bugreport) and analyze with Wireshark

### Operations to Capture

#### Session 1: Init & File List Discovery
1. **Cold connect** — app connects to fresh device
2. **Wait** for full init to complete
3. **Navigate to "My Patterns"** — observe what the app reads to enumerate patterns
4. **Navigate to playlist view** — observe what reads/writes occur
5. **Goal:** Capture the init blob parsing and file listing protocol

#### Session 2: Pattern Selection
1. Connect and wait for init
2. **Tap a specific pattern** to play it — capture what's written
3. **Skip to next** — compare with our known 0x06 command
4. **Go back to a previous pattern** — capture position jump
5. **Goal:** Identify pattern selection commands

#### Session 3: Playlist Management
1. Connect and init
2. **Create a new playlist** in the app
3. **Add patterns** to the playlist
4. **Reorder patterns** within the playlist
5. **Remove a pattern** from the playlist
6. **Activate the playlist** (make it the current one)
7. **Goal:** Capture PlaylistOPCode commands and playlist file transfer

#### Session 4: File Transfer
1. Connect and init
2. **Send a new pattern** from the community/app to the device
3. **Monitor all characteristics** during transfer
4. **Goal:** Confirm file transfer protocol, identify role of `27566b01` and `250e79ac`

#### Session 5: Dangerous Command Exploration (CAREFUL)
1. Connect and init
2. Capture what the app writes to CHAR_PLAYBACK during various operations
3. Look for uses of `0x01`, `0x02`, `0x03`, `0x05` that we previously deemed dangerous
4. **Goal:** Safely identify remaining CHAR_PLAYBACK sub-commands via observed app behavior

### Wireshark Filters

```
# All ATT writes to Sandsara
bluetooth.dst == 94:b9:7e:f1:10:76 && btatt.opcode == 0x12

# Notifications from Sandsara
bluetooth.src == 94:b9:7e:f1:10:76 && btatt.opcode == 0x1b

# File transfer service only
btatt.handle in {<file_flag_handle>, <file_data_handle>, <file_unknown_handle>, <file_status_handle>}

# Playback characteristic only
btatt.handle == <playback_handle>
```

---

## 8. HACS Integration Gaps

### Currently Implemented
- ✅ BLE connection with init handshake
- ✅ Play / Pause / Next / Sleep
- ✅ LED brightness, speed, color, on/off
- ✅ Ball speed control
- ✅ Status polling
- ✅ Notification parsing (config blob)

### Missing for Pattern Management
- ❌ **No file transfer** — cannot send patterns to device
- ❌ **No playlist management** — cannot create/switch playlists
- ❌ **No track selection** — cannot jump to specific pattern by name or position
- ❌ **No file listing** — cannot enumerate patterns on device
- ❌ **No track progress** — don't parse progress notifications
- ❌ **No current track info** — don't parse track name/position from notifications

### Implementation Priority
1. **Parse playlist state from CHAR_PLAYBACK notifications** — understand `"1,-1"` format
2. **Sniff and implement track selection** — jump to pattern by position
3. **Implement file transfer** — send .bin patterns to device
4. **Implement playlist creation** — send .playlist files
5. **Implement playlist switching** — activate a specific playlist

---

## 9. Key Flutter App String Clusters

### Playlist-Related
```
PlaylistConfig, PlaylistConfig._internal, _readPlaylist, _parsePlaylistInfo
PlaylistOPCode, sendPlaylist2, reorderPlaylist, delPlaylistItem
"Playlist sent successfully", "Failed to send playlist"
"Playlist to send:", "New playlist:", "Playlist parsed:"
"Error writing playlist data:", "Error handling playlist notification:"
"Playlist Configuration Updated:", "Device config and playlist config initialized"
"Failed to get playlist characteristic", "Empty playlist, nothing to send"
"Playlist must have at least one item"
```

### Pattern/Track-Related
```
jumpToPattern, selectMusicTrack, pattern selected:
sendFile, sendBin, sendFirstChunk, sendNextChunk, send firstChunk, send nextChunk
patternSend, sendPlaylist2
"File sent successfully", "File received successfully", "File sent"
"Failed to send file", "Error sending file", "Send file canceled"
"Sending file begin", "Sending first chunk", "Sending chunk:"
"------------------File sent"
"File Index: 2", "File Size:", "File:"
addPattern, removePattern, renamePattern, importPattern, importPatterns
```

### Device Info / File Discovery
```
"Device info payload too short for files array (len="
"Existing Files (first 10):"
"Count patterns:", "Failed to list patterns:"
"Patterns Before Calibration:", "Tracks for Calibration:"
"tracksForCalib", "updateTracksForCalib"
```

The "Device info payload too short for files array" is the smoking gun that the device sends a file list during initialization, likely in the CHAR_DATETIME `0x00` init blob or through one of the unidentified characteristics.
