# File Transfer Protocol — Real HCI Capture Analysis

**Date:** 2026-02-08
**Capture:** `BT_HCI_2026_0208_004826.cfa.curf` (15.7MB)
**Device:** Sandsara Mini Pro `94:B9:7E:F1:10:76`

## Critical Discovery: Handle-to-UUID Mapping Was CORRECT

The actual ATT handle mapping from service discovery in this capture:

| Handle | CCCD | UUID | Name | Role |
|--------|------|------|------|------|
| 0x0028 | 0x0029 | `fcbff68e-2af1-11eb` | FILE_FLAG | **Control/handshake** |
| 0x002b | 0x002c | `27566b01-59c3-4a6f` | FILE_UNKNOWN | File listing |
| 0x002e | 0x002f | `fcbffa44-2af1-11eb` | FILE_DATA | **Chunk data** |
| 0x0031 | 0x0032 | `250e79ac-f0d7-43cc` | FILE_STATUS | (errors on read) |

## Two Complete File Transfers Found

### Transfer 1 (file "303") — 38,370 bytes, 158 chunks
### Transfer 2 (file "311") — ~5,474 bytes, 23 chunks

## Exact Packet-by-Packet Sequence (Transfer 1)

### Phase 1: Service Discovery (t=10832.9s)
```
Frame 169623  READ_BY_TYPE_RSP  0x0027,0x0028  → FILE_FLAG (fcbff68e...)
Frame 169626  READ_BY_TYPE_RSP  0x002a,0x002b  → FILE_UNKNOWN (27566b01...)
Frame 169629  READ_BY_TYPE_RSP  0x002d,0x002e  → FILE_DATA (fcbffa44...)
Frame 169632  READ_BY_TYPE_RSP  0x0030,0x0031  → FILE_STATUS (250e79ac...)
Frame 169635  ERROR_RSP         0x0031          → FILE_STATUS read fails
```

### Phase 2: Enable Notifications (t=10832.9s)
```
Frame 169638  WRITE_REQ  0x0029  (no value shown)  → Enable FILE_FLAG notifications
Frame 169641  WRITE_REQ  0x002c  (no value shown)  → Enable FILE_UNKNOWN notifications
Frame 169644  WRITE_REQ  0x002f  (no value shown)  → Enable FILE_DATA notifications
Frame 169647  WRITE_REQ  0x0032  (no value shown)  → Enable FILE_STATUS notifications
```

### Phase 3: File Listing via FILE_UNKNOWN (t=11569s, ~736s later)
```
Frame 169865  WRITE_REQ   0x002c               → Enable notifications on FILE_UNKNOWN
Frame 169867  NOTIFY      0x002b  = 0xFF       → "Ready for command"
Frame 169869  WRITE_REQ   0x002b  = 0x01       → "List files" command
Frame 169871  NOTIFY      0x002b  = 01 333032  → 0x01 + ASCII "302"
Frame 169872  NOTIFY      0x002b  = 0xFE       → "End of list"
```

### Phase 4: Pattern Play Progress (t=11585-12274s)
```
Handle 0x0013 receives progress notifications during pattern drawing:
  01 342c35  → "4,5" (command 1, playlist position?)
  02 30-39   → "0" through "99" (drawing progress %)
  ...
  02 3836    → "86" (86% progress)
```

### Phase 5: FILE TRANSFER INITIATION (t=12286.8s) ⭐

```
Frame 174666  WRITE_REQ   0x0029               → Enable FILE_FLAG notifications
Frame 174668  NOTIFY      0x0028  = 0x00       → "Ready for file transfer"
Frame 174670  WRITE_REQ   0x0028  = 0x6F       → ⭐ COMMAND: START UPLOAD (0x6F = 111 = 'o')
Frame 174672  NOTIFY      0x0013  = 03312c2d31 → Progress: "1,-1" (new track added)
Frame 174673  NOTIFY      0x0028  = 01 333033  → 0x01 + ASCII "303" = assigned filename!
Frame 174674  WRITE_RSP   0x0028               → Write acknowledged
```

**Key insight:** The app writes `0x6F` to FILE_FLAG, NOT the chunk count!

### Phase 6: DATA TRANSFER (t=12287.08 - 12308.09s, ~21 seconds) ⭐

```
Frame 174676  WRITE_REQ   0x002e  244 bytes    → Chunk 1 to FILE_DATA
Frame 174697  NOTIFY      0x0028  = 0x02       → Ack on FILE_FLAG
Frame 174698  WRITE_RSP   0x002e               → Write response

Frame 174701  WRITE_REQ   0x002e  244 bytes    → Chunk 2 to FILE_DATA
Frame 174712  NOTIFY      0x0028  = 0x02       → Ack on FILE_FLAG
Frame 174713  WRITE_RSP   0x002e               → Write response

... (repeats 156 more times) ...

Frame 176604  WRITE_REQ   0x002e  62 bytes     → Chunk 158 (last, partial)
Frame 176606  NOTIFY      0x0028  = 0x02       → Final ack
```

**Chunk details:**
- Chunks 1-157: exactly 244 bytes each
- Chunk 158 (last): 62 bytes
- Total: 157 × 244 + 62 = **38,370 bytes**
- Each write uses **Write Request** (opcode 0x12, response=True)
- Each write receives a **Write Response** (opcode 0x13)
- After each Write Response, a **Notification** of `0x02` arrives on FILE_FLAG

**Timing between chunks:** ~90-200ms per chunk (write + response + ack)

### Phase 7: TRANSFER COMPLETE (t=12308.19s)

```
Frame 176608  WRITE_REQ   0x0028  = 0x01       → "Transfer complete" to FILE_FLAG
Frame 176612  WRITE_RSP   0x0028               → Acknowledged
```

### Transfer 2 (file "311") — Same Sequence

```
Frame 265297  NOTIFY      0x0028  = 0x00       → Ready
Frame 265299  WRITE_REQ   0x0028  = 0x6F       → Start upload command
Frame 265327  NOTIFY      0x0028  = 01 333131  → 0x01 + "311" = filename
Frame 265328  WRITE_RSP   0x0028               → Acknowledged

(23 data chunks to 0x002e, 22 × 244 + last partial)
(0x02 ack after each chunk on FILE_FLAG)

Frame 265577  WRITE_REQ   0x0028  = 0x01       → Transfer complete
Frame 265580  WRITE_RSP   0x0028               → Acknowledged
```

## Protocol Summary

```
Phone → Device:  Enable FILE_FLAG notifications (CCCD)
Device → Phone:  NOTIFY FILE_FLAG = 0x00            "Ready"
Phone → Device:  WRITE FILE_FLAG = 0x6F              "Start upload"
Device → Phone:  NOTIFY FILE_FLAG = 0x01 + ASCII_ID  "File ID assigned: XXX"

repeat for each chunk:
  Phone → Device:  WRITE FILE_DATA = <244 bytes>     Data chunk (response=True)
  Device → Phone:  NOTIFY FILE_FLAG = 0x02            "Chunk received"

Phone → Device:  WRITE FILE_FLAG = 0x01              "Transfer complete"
```

## Comparison: App vs Our Code

| Step | Real App | Our Code | Bug? |
|------|----------|----------|------|
| Enable notifications | FILE_FLAG CCCD | FILE_FLAG CCCD | ✅ OK |
| Wait for ready | 0x00 on FILE_FLAG | 0x00 on FILE_FLAG | ✅ OK |
| **Initiate upload** | **Write `0x6F` to FILE_FLAG** | **Write `total_chunks` to FILE_FLAG** | ❌ **BUG!** |
| Receive filename | 0x01 + ASCII on FILE_FLAG | 0x01 + ASCII on FILE_FLAG | ✅ OK |
| Send data chunks | Write to FILE_DATA (`fcbffa44`) | Write to FILE_DATA (`fcbffa44`) | ✅ OK |
| Chunk response mode | **Write Request** (response=True) | Write Request (response=True) | ✅ OK |
| Chunk acks | 0x02 on FILE_FLAG | 0x02 on FILE_FLAG | ✅ OK |
| End transfer | Write 0x01 to FILE_FLAG | Write 0x01 to FILE_FLAG | ✅ OK |

## The Single Bug

**Step 3 is wrong.** The app writes `0x6F` (the "start upload" command), but our code writes `bytes([total_chunks])` (the number of chunks).

- For a 38KB file with 158 chunks, our code writes `0x9E` (158)
- The device expects `0x6F` (111, ASCII 'o') as the "open/upload" command
- The device probably doesn't recognize `0x9E` as a valid command, and doesn't send the 0x01+filename response → our code times out with "no ack after sending chunk count"

## Code Fix

In `coordinator.py`, line ~678, change:

```python
# BEFORE (wrong):
await self._client.write_gatt_char(
    CHAR_FILE_FLAG, bytes([total_chunks]), response=True
)

# AFTER (correct):
await self._client.write_gatt_char(
    CHAR_FILE_FLAG, bytes([0x6F]), response=True
)
```

Also update the comment at line ~622:
```python
# BEFORE:
# 3. Write chunk count (single byte) to File Flag

# AFTER:  
# 3. Write 0x6F ("start upload" command) to File Flag
```

## Additional Notes

1. **`0x6F` is constant** — both transfers (158 and 23 chunks) use the same `0x6F` value
2. **No chunk count is sent** — the device doesn't need to know how many chunks to expect
3. **End-of-transfer is 0x01** — same as we already have
4. **FILE_STATUS (0x0031)** errors on read — it's apparently not used for file transfers
5. **FILE_UNKNOWN (0x002b)** is used for file listing, not file transfer
6. **The `0x6F` value** may stand for ASCII 'o' = "open" or could be a numeric command code
