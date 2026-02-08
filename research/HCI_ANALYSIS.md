# Sandsara Mini Pro — HCI Capture Analysis

**Capture file:** `BT_HCI_2026_0208_004826.cfa.curf`
**Date:** 2026-02-08
**Total ATT operations:** 308
**Firmware:** 6.3.2, Model: "mini"

---

## 1. Handle-to-UUID Mapping

### Main Service: `fd31a2be-22e7-11eb-adc1-0242ac120002`

| Handle | CCCD | UUID | Characteristic |
|--------|------|------|---------------|
| 0x0010 | 0x0011 | `e914c2c0-cde3-4939-adb2-ca61a3cc9b4e` | CHAR_COMMAND |
| 0x0013 | 0x0014 | `10b59496-bf86-44a8-ba7a-67d8e26a93eb` | CHAR_PLAYBACK |
| 0x0016 | 0x0017 | `0ecc71c5-20a8-462f-92d0-0618c5051cf0` | CHAR_DATETIME |
| 0x0019 | — | `caf74386-dd8b-4f54-9dd9-71c75f6d679a` | CHAR_MODEL (read-only) |
| 0x001b | — | `7b204278-30c3-11eb-adc1-0242ac120002` | CHAR_VERSION (read-only) |
| 0x001d | — | `9e23e02e-8921-4bf9-84f5-f58fa81c726e` | CHAR_STATUS (read-only) |
| 0x001f | — | `20e01699-0346-45c7-91ae-3ebd8a16a2e6` | CHAR_SETTINGS |
| 0x0021 | 0x0022 | `9d277d03-0855-4d8c-8687-316ebca89a61` | CHAR_POSITION |
| 0x0024 | 0x0025 | `eb940790-03f8-406d-bfc4-2f232cf65f84` | CHAR_SENSOR |

### File Transfer Service: `fd31abc4-22e7-11eb-adc1-0242ac120002`

| Handle | CCCD | UUID | Characteristic |
|--------|------|------|---------------|
| 0x0028 | 0x0029 | `fcbff68e-2af1-11eb-adc1-0242ac120002` | File Flag |
| 0x002b | 0x002c | `27566b01-59c3-4a6f-a40e-c35606b0a29b` | File Unknown |
| 0x002e | 0x002f | `fcbffa44-2af1-11eb-adc1-0242ac120002` | File Data |
| 0x0031 | 0x0032 | `250e79ac-f0d7-43cc-ad6a-63544b5c6663` | File Status |

### Standard Services

| Handle | UUID | Characteristic |
|--------|------|---------------|
| 0x0003 | 0x2a00 | Device Name (GAP) |
| 0x0005 | 0x2a01 | Appearance (GAP) |
| 0x0008 | 0x2a05 | Service Changed (GATT) |
| 0x000b | 0x2b3a | ? (GATT service) |
| 0x000d | 0x2b29 | ? (GATT service) |

---

## 2. Complete Timeline of BLE Operations

### Phase 1: GATT Discovery (T+4484.8s — T+4485.7s)
Standard service/characteristic discovery. Phone discovers all services, characteristics, and enables CCCDs.

### Phase 2: Read Device Info (T+4485.8s — T+4486.0s)
| T+offset | Op | Handle | Decoded |
|----------|-----|--------|---------|
| 4485.831 | Read Response | 0x001b (VERSION) | `"6.3.2"` |
| 4486.015 | Read Response | 0x0019 (MODEL) | `"mini"` |

### Phase 3: Init Handshake (T+4486.0s — T+4487.1s)

| T+offset | Op | Handle | Value | Decoded |
|----------|-----|--------|-------|---------|
| 4486.028 | Enable notif | 0x0017 (DT CCCD) | `01:00` | |
| 4486.113 | **Notify** | 0x0016 (DATETIME) | `ff` | ACK |
| 4486.124 | **Write** | 0x0016 (DATETIME) | `00` | Init request |
| 4486.210 | **Notify** | 0x0016 (DATETIME) | `0b 3130302c30` | `\x0b"100,0"` — brightness=100 |
| 4486.212 | **Notify** | 0x0016 (DATETIME) | 163 bytes | `\x00"Sand Sandsara Mini"...` — device info + file array |
| 4486.213 | **Notify** | 0x0016 (DATETIME) | `fe` | Init complete |
| 4486.298 | Enable notif | 0x0014 (PB CCCD) | `01:00` | |
| 4486.358 | **Notify** | 0x0013 (PLAYBACK) | `ff` | ACK |
| 4486.368 | Read Request | 0x0013 (PLAYBACK) | | |
| 4486.503 | **Read Resp** | 0x0013 (PLAYBACK) | | `"1-2-3-4-5-6-7-9-10-18-33"` — **PLAYLIST!** |
| 4486.512 | **Write** | 0x0013 (PLAYBACK) | `00` | Init request |
| 4486.601 | **Notify** | 0x0013 (PLAYBACK) | 43 bytes | `\x00` state blob — `"01,-1"` (paused, no track) |
| 4486.614 | Read Request | 0x001f (SETTINGS) | | |
| 4486.698 | **Read Resp** | 0x001f (SETTINGS) | | `"100,0,1,0000000000000"` |
| 4486.791 | Enable notif | 0x0011 (CMD CCCD) | `01:00` | |
| 4486.893 | **Notify** | 0x0010 (COMMAND) | `ff` | ACK |
| 4486.911 | **Write** | 0x0010 (COMMAND) | `00` | Init request |
| 4486.991 | **Notify** | 0x0010 (COMMAND) | 75 bytes | Config blob — see below |
| 4486.999 | **Write** | 0x0016 (DATETIME) | `04 32303236...` | `\x04"2026-02-08T02:03:13.348098"` — set time |
| 4487.088 | **Notify** | 0x0016 (DATETIME) | `fe` | Time set ACK |

### Phase 4: Play Command (T+4609.2s)

| T+offset | Op | Handle | Value | Decoded |
|----------|-----|--------|-------|---------|
| 4609.204 | **Write** | 0x0013 (PLAYBACK) | `07` | **PLAY** |
| 4609.305 | **Notify** | 0x0013 (PLAYBACK) | `03 302c30323a3035` | `\x03"0,02:05"` — playing, time 02:05 |
| 4617.349 | **Notify** | 0x0013 (PLAYBACK) | `02 3439` | `\x02"49"` — progress 49% |

### Phase 5: Sleep Command (T+4628.6s)

| T+offset | Op | Handle | Value | Decoded |
|----------|-----|--------|-------|---------|
| 4628.556 | **Write** | 0x0013 (PLAYBACK) | `04` | **SLEEP** |
| 4628.755 | **Notify** | 0x0013 (PLAYBACK) | `01 38322c2d323339393234343930` | `\x01"82,-239924490"` — track 82, hash |
| 4628.756 | **Notify** | 0x0013 (PLAYBACK) | `02 30` | `\x02"0"` — progress 0% |

Progress notifications follow: 0,1,2,...14 (every ~3s each)

### Phase 6: Sleep Again (T+4696.6s)

| T+offset | Op | Handle | Value | Decoded |
|----------|-----|--------|-------|---------|
| 4696.612 | **Write** | 0x0013 (PLAYBACK) | `04` | **SLEEP** |
| 4696.714 | **Notify** | 0x0013 (PLAYBACK) | `01 38332c313834303535353936` | `\x01"83,184055596"` — track 83, hash |
| 4696.714 | **Notify** | 0x0013 (PLAYBACK) | `02 30` | `\x02"0"` — progress 0% |

Progress notifications continue: 0-100 (playing the full sleep pattern)

### Phase 7: Previous Track (T+4716.4s) — **NEW DISCOVERY!**

| T+offset | Op | Handle | Value | Decoded |
|----------|-----|--------|-------|---------|
| 4716.413 | **Write** | 0x0013 (PLAYBACK) | `05` | **PREVIOUS TRACK** |
| 4716.506 | **Notify** | 0x0013 (PLAYBACK) | `01 38322c2d323339393234343930` | `\x01"82,-239924490"` — back to track 82 |
| 4716.507 | **Notify** | 0x0013 (PLAYBACK) | `02 30` | `\x02"0"` — progress 0% |

Progress continues 0-100, then track completes...

### Phase 8: Track Completion Sequence (T+4998.6s)

| T+offset | Op | Handle | Value | Decoded |
|----------|-----|--------|-------|---------|
| 4997.793 | **Notify** | 0x0013 (PLAYBACK) | `02 313030` | `\x02"100"` — progress 100% |
| 4998.623 | **Notify** | 0x0013 (PLAYBACK) | `03 312c31` | `\x03"1,1"` — track ended, auto-advancing |

### Phase 9: File Unknown Handshake (T+4934.3s)

| T+offset | Op | Handle | Value | Decoded |
|----------|-----|--------|-------|---------|
| 4934.255 | Enable notif | 0x002c (File Unk CCCD) | `01:00` | |
| 4934.320 | **Notify** | 0x002b (File Unknown) | `ff` | ACK |
| 4934.329 | **Write** | 0x002b (File Unknown) | `01` | Init/ping |
| 4934.418 | **Notify** | 0x002b (File Unknown) | `fe` | Done |
| 4934.429 | Disable notif | 0x002c (File Unk CCCD) | `00:00` | |

### Phase 10: Select Track by Index (T+5037.5s) — **NEW DISCOVERY!**

| T+offset | Op | Handle | Value | Decoded |
|----------|-----|--------|-------|---------|
| 5037.479 | **Write** | 0x0013 (PLAYBACK) | `01 33` | **SELECT TRACK** — `\x01"3"` = jump to track 3 |
| 5037.573 | **Notify** | 0x0013 (PLAYBACK) | `01 332c34` | `\x01"3,4"` — track 3, file size/hash 4 |
| 5037.573 | **Notify** | 0x0013 (PLAYBACK) | `02 30` | `\x02"0"` — progress 0% |

Track 3 plays, progress 0→100, then:

| 5058.730 | **Notify** | 0x0013 (PLAYBACK) | `03 312c30` | `\x03"1,0"` — track ended |
| 5058.730 | **Notify** | 0x0013 (PLAYBACK) | `03 302c30` | `\x03"0,0"` — auto-play next, time 0 |

### Phase 11: Shuffle Toggle (T+5171.4s) — **NEW DISCOVERY!**

| T+offset | Op | Handle | Value | Decoded |
|----------|-----|--------|-------|---------|
| 5171.446 | **Write** | 0x0013 (PLAYBACK) | `0d 01` | **SHUFFLE ON** |
| 5174.588 | **Write** | 0x0013 (PLAYBACK) | `0d 00` | **SHUFFLE OFF** |

Note: With shuffle ON, progress notifications skip numbers (e.g., 0,1,2,3,5,6,7,9,10,11,13...) — skipping every 4th value. This appears to be a side effect of shuffle mode on progress reporting, not actual progress behavior.

---

## 3. Protocol Discoveries

### 3.1 NEW: Previous Track Command (0x05)

Previously marked as "DANGEROUS — crashes device". In this capture, **0x05 = Previous Track**, analogous to 0x06 = Next Track. Safe to use.

### 3.2 NEW: Select Track by Index (0x01 + ASCII index)

```
Write to CHAR_PLAYBACK: 0x01 + ASCII_string(track_index)
Example: 0x01 0x33 = select track "3"
```

The track index is the **position in the current playlist** (from the playlist string `"1-2-3-4-5-6-7-9-10-18-33"`). Writing `0x01 "3"` selects the 3rd entry (which is pattern file #3).

**Response notification:** `0x01 "3,4"` — confirms track 3, second value is likely a file identifier or size.

### 3.3 NEW: Shuffle Mode (0x0d + 0x00/0x01)

```
Write to CHAR_PLAYBACK: 0x0d 0x01  → Shuffle ON
Write to CHAR_PLAYBACK: 0x0d 0x00  → Shuffle OFF
```

### 3.4 NEW: Playlist Read Format

**Reading CHAR_PLAYBACK** returns the current playlist as a dash-separated list of track indices:

```
"1-2-3-4-5-6-7-9-10-18-33"
```

These are file indices (matching positions in the file existence array from the CHAR_DATETIME init blob). The playlist contains 11 tracks referencing file indices 1,2,3,4,5,6,7,9,10,18,33.

### 3.5 CHAR_DATETIME Init Blob Structure

```
Offset  Size  Content
[0]     1     Command byte: 0x00
[1-31]  31    Device name, null-padded: "Sand Sandsara Mini"
[32]    1     0x00 (unknown)
[33]    1     0x01 (unknown flag)
[34-41] 8     Calibration string: "25252525"
[42-49] 8     Zeros (padding)
[50]    1     0x0a (10) — unknown
[51]    1     0x78 (120) — possibly max file capacity
[52-53] 2     Zeros
[54-59] 6     "2002,0" — unknown (firmware build? SD info?)
[60-61] 2     Zeros
[62-162] 101  File existence array: each byte 0x01 = file exists, 0x00 = empty
```

**File existence array:** 101 bytes, indexed 0-100. Each byte indicates whether a pattern file exists at that index on the SD card. In this capture, all 101 slots contain 0x01 (all files present).

### 3.6 Playback Notification Sub-commands

| Byte 0 | Format | Meaning |
|--------|--------|---------|
| `0x00` | Binary blob (43 bytes) | Full playback state (after init) |
| `0x01` | `0x01` + ASCII `"trackIdx,value"` | Track change — new track index and file hash/size |
| `0x02` | `0x02` + ASCII `"N"` | Progress percentage (0-100) |
| `0x03` | `0x03` + ASCII `"status,time"` | Status change — playing/ended + timestamp |
| `0xFF` | Single byte | Connection ACK |
| `0xFE` | Single byte | Init/operation complete |

#### Status change (0x03) values:
- `"0,02:05"` — playing, at time position 2:05
- `"0,0"` — playing, at time 0 (start of new track)
- `"1,0"` — track completed (transitioning)
- `"1,1"` — track completed, auto-advancing

#### Track change (0x01) values:
- `"3,4"` — track index 3, value 4 (after select)
- `"82,-239924490"` — track index 82, value -239924490 (after sleep — large signed int, likely file checksum)
- `"83,184055596"` — track index 83, value 184055596

### 3.7 Full Playback State Blob (0x00)

```
Offset  Value    Meaning
[0]     0x00     Blob type
[1]     0x01     Unknown (possibly play mode)
[2]     0x51(81) Unknown
[3-4]   0x0000   Unknown
[5]     0x00     Unknown
[6]     0x51(81) Unknown  
[7-9]   0x000000 Unknown
[10-14] "01,-1"  Track info: position 1, status -1 (no active track)
[15-42] 0x00...  Padding
[43]    0x01     Unknown flag
```

### 3.8 Command Config Blob Analysis

```
Byte  Value  Meaning
[0]   0x00   Blob type (config dump)
[1]   0x10   LED animation speed = 16
[2]   0x1e   Ball/motor speed = 30
[3]   0x00   Unknown
[4]   0x00   Unknown
[5]   0x22   LED brightness = 34
[6]   0x00   Playing status (0=paused)
[7]   0x5f   Unknown (95)
[8-10] 000000 Unknown
[11]  0x02   Color count = 2
[12]  0x00   Position 1 = 0x00 (start)
[13]  0xFF   Position 2 = 0xFF (end)
[14-75] Color data (multiple gradient entries, 14 bytes each)
```

Color gradient entries repeat in the config blob with pattern: `R R G G B B 00 00 00 00 00 00 00 00`

Observed colors: `F0 F0`, `FF FF`, `BE BE` — suggesting paired R values for gradient stops.

---

## 4. Updated Command Reference

### CHAR_PLAYBACK (`10b59496`) — Complete

| CMD | Payload | Function | Status |
|-----|---------|----------|--------|
| `0x00` | none | Init handshake | CONFIRMED |
| `0x01` | ASCII track index | **Select track by playlist position** | **NEW** ✅ |
| `0x04` | none | Sleep (play sleep pattern) | CONFIRMED |
| `0x05` | none | **Previous track** | **NEW** ✅ |
| `0x06` | none | Next track | CONFIRMED |
| `0x07` | none | Play | CONFIRMED |
| `0x08` | none | Pause | CONFIRMED |
| `0x0d` | `0x00` or `0x01` | **Shuffle off/on** | **NEW** ✅ |

Reading CHAR_PLAYBACK returns: `"idx1-idx2-idx3-..."` — current playlist as dash-separated file indices.

### Unknown/Untested Commands

| CMD | Status |
|-----|--------|
| `0x02` | Untested — possibly stop? |
| `0x03` | Untested — possibly related to status queries |
| `0x09-0x0c` | Untested |
| `0x0e+` | Untested |

---

## 5. File Unknown Characteristic (`27566b01`)

Based on this capture, the File Unknown characteristic follows a simple handshake:
1. Enable notifications → receive `0xFF` (ACK)
2. Write `0x01` → receive `0xFE` (done)
3. Disable notifications

This appears to be a **file service initialization/ready check**, not a data transfer channel. The app enables it mid-playback (while progress notifications are flowing), suggesting it may be verifying file service availability before a potential transfer operation.

---

## 6. Recommendations for HACS Integration

### Immediate (from this capture):

1. **Add Previous Track** — write `0x05` to CHAR_PLAYBACK
2. **Add Select Track** — write `0x01` + ASCII index to CHAR_PLAYBACK
3. **Add Shuffle Toggle** — write `0x0d 0x01`/`0x0d 0x00` to CHAR_PLAYBACK
4. **Read Playlist** — read CHAR_PLAYBACK to get `"1-2-3-..."` playlist indices
5. **Parse File Array** — from CHAR_DATETIME init blob bytes [62:], build file existence map
6. **Parse Progress** — notification `0x02` + ASCII number = track progress %
7. **Parse Track Changes** — notification `0x01` + ASCII `"idx,hash"` = current track
8. **Parse Status** — notification `0x03` + ASCII `"status,time"` = play state

### Needs More Sniffing:

1. **Playlist creation/modification** — how to write a new playlist (likely file transfer of .playlist file, then some command)
2. **Track naming** — how to map file indices to human-readable names
3. **Sleep pattern selection** — 0x04 plays specific patterns (82, 83) — how are these configured?
4. **Commands 0x02, 0x03, 0x09-0x0c** — untested, may reveal more functionality
5. **File transfer protocol** — only the File Unknown handshake was seen, no actual transfers

### Key Insight: Playlist is Index-Based

The playlist system uses **numeric file indices** (0-100+), not filenames. The device stores files by index, and the playlist is simply a list of which indices to play in order. The CHAR_DATETIME init blob provides a bitmap of which indices have files. This is much simpler than the filename-based system in the original firmware.

---

## 7. Raw Data Reference

### All Writes to CHAR_PLAYBACK (0x0013)

| Frame | T+offset | Hex Value | Decoded |
|-------|----------|-----------|---------|
| 53541 | 4486.512 | `00` | Init |
| 59351 | 4609.204 | `07` | Play |
| 60259 | 4628.556 | `04` | Sleep |
| 63551 | 4696.612 | `04` | Sleep |
| 64539 | 4716.413 | `05` | Previous track |
| 79906 | 5037.479 | `01 33` | Select track "3" |
| 85931 | 5171.446 | `0d 01` | Shuffle ON |
| 85935 | 5174.588 | `0d 00` | Shuffle OFF |

### All Writes to Other Characteristics

| Frame | T+offset | Handle | Char | Hex Value | Decoded |
|-------|----------|--------|------|-----------|---------|
| 53497 | 4486.124 | 0x0016 | DATETIME | `00` | Init |
| 53558 | 4486.911 | 0x0010 | COMMAND | `00` | Init |
| 53562 | 4486.999 | 0x0016 | DATETIME | `04 3230...` | Set time |
| 74908 | 4934.329 | 0x002b | File Unknown | `01` | File svc init |
