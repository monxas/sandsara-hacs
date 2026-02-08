# HCI Capture Analysis V2 — File Transfer Investigation

**Capture:** `BT_HCI_2026_0208_004826.cfa.curf` (9.5MB, BTSnoop v1)
**Date:** 2026-02-08
**App:** `com.ht117.sandsaras` (Flutter-based)
**Device MAC:** `94:B9:7E:F1:10:76` (Sandsara Mini Pro)

---

## ⚠️ KEY FINDING: NO FILE TRANSFER IN THIS CAPTURE

**This capture does NOT contain an actual file transfer.** After exhaustive analysis:

- **ZERO writes** to FILE_FLAG (`0x0028`) in the entire capture
- **ZERO writes** to FILE_DATA (`0x002e`) in the entire capture
- Only 32 total write operations in the entire 170k+ frame capture
- The capture contains: connection, device init, playback commands, and file list queries

The capture covers two BLE connection sessions:
1. **Session 1** (frames ~53k–86k): Connect → init → play/sleep/prev → file list query (empty response) → shuffle toggle
2. **Session 2** (frames ~169k+): Connect → init → LED color change → playback → file list query (returns "302") → pattern list refresh

---

## File-Transfer-Related Activity Found

### FILE_UNKNOWN (`0x002b`) — File List Query Protocol

Two interactions observed, confirming `FILE_UNKNOWN` is a **file count/list** characteristic:

#### Session 1 (T+4934s) — Empty Response
| Time | Op | Handle | Value | Meaning |
|------|-----|--------|-------|---------|
| 4934.255 | Write Req | 0x002c (CCCD) | `01:00` | Enable notifications |
| 4934.320 | Notification | 0x002b | `ff` | Ready signal |
| 4934.329 | Write Req | 0x002b | `01` | Query command |
| 4934.418 | Notification | 0x002b | `fe` | End (no files? or error) |
| 4934.429 | Write Req | 0x002c (CCCD) | `00:00` | Disable notifications |

#### Session 2 (T+11569s) — Returns File Count "302"
| Time | Op | Handle | Value | Meaning |
|------|-----|--------|-------|---------|
| 11568.928 | Write Req | 0x002c (CCCD) | `01:00` | Enable notifications |
| 11569.079 | Notification | 0x002b | `ff` | Ready signal |
| 11569.099 | Write Req | 0x002b | `01` | Query command |
| 11569.175 | Notification | 0x002b | `01 33 30 32` | `0x01` + ASCII "302" = 302 files |
| 11569.176 | Notification | 0x002b | `fe` | End of response |
| 11569.189 | Write Req | 0x002c (CCCD) | `01:00` | (re-enable/disable) |
| 11569.323 | Write Resp | 0x002c | — | Confirmed |

**Conclusion:** FILE_UNKNOWN is a file count query, NOT used for file transfers.

---

## What We Know vs. What We Need

### Protocol Source: Firmware (`Bluetooth.cpp`)
Our FILE_TRANSFER_PROTOCOL.md is based on the original firmware source, which says:
1. Write **filename** (ASCII) to FILE_FLAG → device responds "ok" on FILE_STATUS
2. Write data chunks to FILE_DATA → device responds "1" on FILE_DATA notification
3. Write any byte to FILE_FLAG → device responds "done" on FILE_STATUS

### Our Current Code (`coordinator.py` line 616+)
Our implementation does something DIFFERENT from the firmware protocol:
1. Enable notifications on FILE_FLAG
2. Wait for `0x00` notification on FILE_FLAG ← **NOT in firmware protocol**
3. Write chunk count (single byte) to FILE_FLAG ← **Firmware expects FILENAME, not count**
4. Wait for `0x01` + filename on FILE_FLAG ← **Firmware uses FILE_STATUS for responses**
5. Write chunks to FILE_DATA, wait for `0x02` on FILE_FLAG per chunk ← **Firmware uses FILE_DATA notifications**
6. Write `0x01` to FILE_FLAG ← **Firmware says write any byte**

### CRITICAL MISMATCHES
| Aspect | Firmware Protocol | Our Code |
|--------|------------------|----------|
| **Step 1 write** | Filename (ASCII) to FILE_FLAG | Chunk count (1 byte) to FILE_FLAG |
| **Step 1 response** | "ok"/"error" on FILE_STATUS | 0x00 on FILE_FLAG |
| **Chunk ack** | "1" on FILE_DATA notification | 0x02 on FILE_FLAG notification |
| **Completion** | "done" on FILE_STATUS | N/A |
| **Notifications** | FILE_STATUS + FILE_DATA | FILE_FLAG only |

---

## Recommended Fixes

### Option A: Follow Firmware Protocol Exactly
```python
async def async_upload_pattern(self, file_path, filename):
    # 1. Enable notifications on FILE_STATUS and FILE_DATA
    await client.start_notify(CHAR_FILE_STATUS, status_handler)
    await client.start_notify(CHAR_FILE_DATA, data_handler)  # for chunk acks
    
    # 2. Write filename to FILE_FLAG (ASCII string, not chunk count)
    await client.write_gatt_char(CHAR_FILE_FLAG, filename.encode('ascii'), response=True)
    
    # 3. Wait for "ok" on FILE_STATUS
    # response should be ASCII "ok" or "error= -2"
    
    # 4. Send chunks to FILE_DATA (512 bytes per firmware, but MTU may limit to 244)
    for chunk in chunks:
        await client.write_gatt_char(CHAR_FILE_DATA, chunk, response=True)
        # Wait for "1" (0x31) notification on FILE_DATA
    
    # 5. Write completion byte to FILE_FLAG
    await client.write_gatt_char(CHAR_FILE_FLAG, b'\x00', response=True)
    
    # 6. Wait for "done" on FILE_STATUS
```

### Option B: Get a REAL File Transfer Capture
The most reliable path is to capture an actual file transfer from the app. This capture only shows browsing/playback. To get a transfer capture:
1. Start HCI logging on Android (Developer Options → Enable Bluetooth HCI snoop log)
2. Open Sandsara app
3. Upload a pattern (preferably a small one)
4. Stop HCI logging
5. Pull the btsnoop file

---

## Other Discoveries from This Capture

### Playlist Refresh After File List
After querying file count (302), the app writes `0x0b` + ASCII "302" to PLAYBACK:
```
Frame 169887: Write 0x0b 33 30 32 to 0x0013 (PLAYBACK)
```
This is likely **"add track 302 to playlist"** command (0x0b = add track).

Device responds with updated playlist:
```
"1-2-3-4-5-6-7-9-10-18-33-302"
```

### New Playback Command: 0x08
```
Frame 169827: Write 0x08 to 0x0013 (PLAYBACK)
```
Previously undocumented. Occurs after LED color change. Possibly "resume" or "refresh".

### LED Color Write: 0x06 + 0x01
```
Frame 169781: Write 0x06 0x01 to 0x0010 (COMMAND)
```
Occurs in session 2. Possibly LED mode/animation toggle.

---

## Summary

**The capture doesn't contain a file transfer.** Our code's protocol is based on assumptions that don't match the firmware source. The most impactful fix is to follow the firmware protocol (write filename to FILE_FLAG, listen on FILE_STATUS for "ok"/"done", listen on FILE_DATA for chunk acks). But ideally we need a real transfer capture to validate.
