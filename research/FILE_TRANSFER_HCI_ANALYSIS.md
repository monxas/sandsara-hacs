# Sandsara File Transfer Protocol — HCI Analysis

**Date:** 2026-02-08
**Source:** BLE HCI capture from Redmi 6A running official Sandsara app
**Capture file:** `BT_HCI_2026_0208_004826.cfa.curf`

## Characteristics Involved

| Handle | CCCD Handle | UUID suffix | Name | Role |
|--------|-------------|-------------|------|------|
| 0x0028 | 0x0029 | fcbff68e | File Flag | Transfer control & acknowledgments |
| 0x002b | 0x002c | 27566b01 | File Unknown | File listing/count query |
| 0x002e | 0x002f | fcbffa44 | File Data | Actual file payload |
| 0x0031 | 0x0032 | 250e79ac | File Status | Status queries (not used in successful transfer) |

## Protocol Sequence

### Phase 0: Service Discovery & CCCD Setup

At connection time (~4485s and ~10832s), the app discovers all file transfer characteristics via Read by Type (0x09), then enables notifications on all four CCCDs (0x0029, 0x002c, 0x002f, 0x0032) by writing to them (opcode 0x05).

**Note:** File Status 0x0031 returned error (opcode 0x01) during discovery — likely not readable.

### Phase 1: Query File Count via File Unknown (0x002b)

**First query** (~4934s — no files on device yet):
```
→ Write CCCD 0x002c (enable notifications)
← Notification 0x002b: ff          ← "ready" signal
→ Write 0x002b: 01                 ← "query" command
← Notification 0x002b: fe          ← "empty/done" (no files)
→ Write CCCD 0x002c (disable)
```

**Second query** (~11568s — after connecting to device with files):
```
→ Write CCCD 0x002c (enable notifications)
← Notification 0x002b: ff          ← "ready" signal
→ Write 0x002b: 01                 ← "query" command
← Notification 0x002b: 01333032    ← 0x01 + ASCII "302" (file ID)
← Notification 0x002b: fe          ← "end of list"
→ Write CCCD 0x002c (disable)
```

**Interpretation:**
- `ff` = ready/listening
- `01` + ASCII filename = file entry in list
- `fe` = end of list marker
- Write `01` to 0x002b = "list files" command

### Phase 2: File Transfer via File Flag (0x0028) + File Data (0x002e)

**Complete transfer of file "303"** (~12286s):

#### Step 1: Enable notifications and check status
```
→ Write CCCD 0x0029 (enable notifications on File Flag)
← Notification 0x0028: 00          ← "idle/ready to receive"
```

#### Step 2: Initiate transfer with filename
```
→ Write 0x0028: 6f                 ← 0x6F = 111 decimal (likely total chunk count or file size indicator)
← Notification 0x0028: 01333033    ← 0x01 + ASCII "303" = acknowledgment with filename
```

**Key insight:** The byte `6f` (111) appears to be the number of data chunks. The device responds with `01` + the filename it will save as.

#### Step 3: Send data chunks with flow control
Each chunk follows this pattern:
```
→ Write 0x002e: <244 bytes of track data>
← Notification 0x0028: 02          ← "chunk received, send next"
```

This repeats for every chunk. The `02` on File Flag is the acknowledgment.

**Chunk details:**
- Each Write Request to 0x002e contains exactly **244 bytes** of payload (MTU-limited)
- The data appears to be theta/rho coordinate pairs for the sand pattern
- Total chunks sent: **111** (matching the 0x6F value sent in step 2)
- Transfer time: ~12287.069 to ~12308.178 = **~21 seconds** for all 111 chunks

#### Step 4: Complete transfer
```
→ Write 0x0028: 01                 ← "transfer complete" signal
← Write Response (0x13) for 0x0028
→ Write CCCD 0x0029 (disable notifications)
```

### Phase 3: Post-Transfer File List Verification

After the transfer completes (~12342s), the app queries the file list again:
```
→ Write CCCD 0x002c (enable)
← Notification 0x002b: ff
→ Write 0x002b: 01
← Notification 0x002b: 013330322d333033   ← 0x01 + ASCII "302-303"
← Notification 0x002b: fe
→ Write CCCD 0x002c (disable)
```

The device now reports two files: "302-303" (as a single string with dash separator).

### Phase 4: Playback

After upload, the playback characteristic (0x0013) shows the device cycling through tracks. At ~12770s:
```
→ Write 0x0013: 0b333033           ← Read command (0x0b) for track "303"
← Read Response 0x0013: 312d322d332d342d352d362d372d392d31302d31382d33332d3330322d333033
                         (ASCII: "1-2-3-4-5-6-7-9-10-18-33-302-303")
```
This confirms the file "303" is now in the playlist.

## Protocol Summary

```
┌─────────┐                          ┌──────────┐
│   App   │                          │ Sandsara │
└────┬────┘                          └────┬─────┘
     │                                    │
     │─── Enable CCCD 0x0029 ────────────►│
     │◄── Notification 0x0028: 0x00 ──────│  (ready)
     │                                    │
     │─── Write 0x0028: <chunk_count> ───►│  (initiate: N chunks)
     │◄── Notification 0x0028: 0x01+name──│  (ack with filename)
     │                                    │
     │─── Write 0x002e: <chunk 1> ───────►│  (244 bytes)
     │◄── Notification 0x0028: 0x02 ──────│  (chunk ack)
     │                                    │
     │─── Write 0x002e: <chunk 2> ───────►│  (244 bytes)
     │◄── Notification 0x0028: 0x02 ──────│  (chunk ack)
     │                                    │
     │    ... repeat for N chunks ...     │
     │                                    │
     │─── Write 0x0028: 0x01 ────────────►│  (transfer complete)
     │─── Disable CCCD 0x0029 ───────────►│
     │                                    │
```

## Key Protocol Values

| Value | Characteristic | Direction | Meaning |
|-------|---------------|-----------|---------|
| `00` | File Flag (notif) | ← | Device idle/ready |
| `01` | File Flag (write) | → | Transfer complete signal |
| `02` | File Flag (notif) | ← | Chunk acknowledged, send next |
| `6f` | File Flag (write) | → | Chunk count (111 in this case) |
| `01`+ASCII | File Flag (notif) | ← | File acknowledged with name |
| `01` | File Unknown (write) | → | List files command |
| `ff` | File Unknown (notif) | ← | Ready/listening |
| `fe` | File Unknown (notif) | ← | End of list |
| `01`+ASCII | File Unknown (notif) | ← | File entry (name) |

## Differences from Previous Understanding

1. **The first byte to File Flag is the chunk count**, not a command byte. The value `6f` = 111 matches exactly the number of data chunks sent.
2. **Flow control is per-chunk**: Each 244-byte write to File Data gets an explicit `02` acknowledgment on File Flag before the next chunk is sent.
3. **File names are ASCII strings** like "302", "303" — these are track IDs.
4. **File list uses dash-separated string** when multiple files exist: "302-303".
5. **The transfer complete signal is `01` written to File Flag** (same characteristic used for initiation).
6. **File Status (0x0031) was never used** in the successful transfer — it may only be for error reporting or firmware-specific queries.

## Data Format

The file data appears to be binary coordinate pairs. Each chunk is 244 bytes. With 111 chunks × 244 bytes = **27,084 bytes** total for track "303".

The coordinate format in each 4-byte group appears to be:
- 2 bytes: theta (angle) as little-endian uint16
- 2 bytes: rho (radius) as little-endian uint16  
- Separator byte: `0a` (newline) between coordinate pairs

Each chunk contains approximately 48-49 coordinate pairs.

## Implementation Notes for HACS

1. **Calculate chunk count** before starting: `ceil(file_size / 244)`
2. **Write chunk count** as single byte to File Flag (0x0028)
3. **Wait for** notification `01` + filename on File Flag
4. **Send chunks** of 244 bytes to File Data (0x002e), waiting for `02` notification after each
5. **Signal completion** by writing `01` to File Flag
6. **Verify** by querying file list on File Unknown (0x002b)
