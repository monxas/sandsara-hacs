# Sandsara File Transfer — Deep HCI Capture Analysis

## Handle-to-UUID Mapping (Verified from Service Discovery)

| Handle | CCCD | UUID | Role | Notes |
|--------|------|------|------|-------|
| 0x0028 | 0x0029 | `fcbff68e-2af1-11eb-adc1-0242ac120002` | **CHAR_FILE_FLAG** | Control char for file transfer |
| 0x002b | 0x002c | `27566b01-59c3-4a6f-a40e-c35606b0a29b` | **CHAR_FILE_UNKNOWN** | File listing char |
| 0x002e | 0x002f | `fcbffa44-2af1-11eb-adc1-0242ac120002` | **CHAR_FILE_DATA** | Bulk data writes |
| 0x0031 | 0x0032 | `250e79ac-f0d7-43cc-ad6a-63544b5c6663` | **CHAR_FILE_STATUS** | Returns errors (unused in transfer) |

> **CRITICAL**: Previous analysis (HCI_ANALYSIS.md) had the handle mapping WRONG — it said FILE_FLAG=0x002e. The real FILE_FLAG is at **0x0028**. However, our code uses UUIDs (not handles), so the UUIDs are correct and resolve to the right handles dynamically.

## Complete File Transfer Protocol (from capture)

### Session 2 Transfer (frames 174666–176615, t=12286–12308s)

#### Step 1: Enable notifications on FILE_FLAG
```
Frame 174666 [t+0.000s]: WRITE_REQ → 0x0029 (FILE_FLAG CCCD) value=0x0100
Frame 174668 [t+0.085s]: NOTIFICATION ← 0x0028 (FILE_FLAG): 00
Frame 174669 [t+0.085s]: WRITE_RESP ← 0x0029
```
**Key**: The `0x00` notification arrives BEFORE the write response! Potential race condition.

#### Step 2: Write 0x6F to FILE_FLAG (request transfer)
```
Frame 174670 [t+0.100s]: WRITE_REQ → 0x0028 (FILE_FLAG) value=6f
Frame 174673 [t+0.231s]: NOTIFICATION ← 0x0028 (FILE_FLAG): 01333033  (= 0x01 + "303")
Frame 174674 [t+0.231s]: WRITE_RESP ← 0x0028
```
**Device assigns filename "303" and signals ready (0x01 prefix).**

#### Step 3: Bulk data transfer (158 chunks to FILE_DATA)
```
Frame 174676 [t+0.246s]: WRITE_REQ → 0x002e (FILE_DATA): [244 bytes]
Frame 174697 [t+0.523s]: NOTIFICATION ← 0x0028 (FILE_FLAG): 02   ← CHUNK ACK
Frame 174698 [t+0.523s]: WRITE_RESP ← 0x002e

Frame 174701 [t+0.534s]: WRITE_REQ → 0x002e (FILE_DATA): [244 bytes]
Frame 174712 [t+0.621s]: NOTIFICATION ← 0x0028 (FILE_FLAG): 02   ← CHUNK ACK
Frame 174713 [t+0.621s]: WRITE_RESP ← 0x002e

... (158 total chunks, each followed by 0x02 ACK on FILE_FLAG)

Frame 176604 [t+21.252s]: WRITE_REQ → 0x002e (FILE_DATA): [62 bytes] ← LAST CHUNK (shorter)
Frame 176606 [t+21.340s]: NOTIFICATION ← 0x0028 (FILE_FLAG): 02   ← FINAL ACK
Frame 176607 [t+21.340s]: WRITE_RESP ← 0x002e
```

#### Step 4: Signal transfer complete
```
Frame 176608 [t+21.348s]: WRITE_REQ → 0x0028 (FILE_FLAG) value=01
Frame 176612 [t+21.439s]: WRITE_RESP ← 0x0028
```

#### Step 5: Disable notifications
```
Frame 176613 [t+21.451s]: WRITE_REQ → 0x0029 (FILE_FLAG CCCD) value=0x0000
Frame 176615 [t+21.534s]: WRITE_RESP ← 0x0029
```

### Session 3 Transfer (frames 265295–265583, t=41300–41304s)
Same protocol, 23 chunks, assigned filename "311".

## File Listing Protocol (CHAR_FILE_UNKNOWN)

Separate from file transfer, uses 0x002b/0x002c:

```
1. WRITE → 0x002c (CCCD): enable notifications
2. NOTIFICATION ← 0x002b: ff   (= "ready")
3. WRITE → 0x002b: 01   (= "list files")
4. NOTIFICATION ← 0x002b: 01 + ASCII names (e.g., "302-303-304...")
5. NOTIFICATION ← 0x002b: fe   (= "end of list")
6. WRITE → 0x002c (CCCD): disable notifications
```

## Timing Analysis

| Operation | Time (ms) |
|-----------|----------|
| CCCD write → 0x00 notification | 85ms |
| 0x00 notification → CCCD write response | <1ms (simultaneous) |
| Write 0x6F → 0x01+filename notification | 131ms |
| Write chunk → 0x02 ACK notification | ~90-100ms |
| Between chunks | ~10ms |
| Total 158-chunk transfer | ~21 seconds |
| Write 0x01 (complete) → write response | 91ms |

## Comparison with Our Code

### What matches ✅
1. UUID mapping is correct — UUIDs in const.py match capture exactly
2. Protocol sequence: enable notifs → wait 0x00 → write 0x6F → wait 0x01+name → chunks → write 0x01
3. Chunk size: 244 bytes (FILE_CHUNK_SIZE matches)
4. After each chunk, wait for 0x02 ACK on FILE_FLAG
5. Completion signal: write 0x01 to FILE_FLAG
6. Disable notifications after transfer

### Potential Issues ⚠️

#### 1. Race Condition with 0x00 Notification
The 0x00 "ready" notification arrives BEFORE the CCCD write response in the capture. In our code:
```python
await self._client.start_notify(CHAR_FILE_FLAG, _file_flag_handler)  # waits for CCCD write resp
_flag_event.clear()  # ← may clear already-received 0x00!
await asyncio.wait_for(_flag_event.wait(), timeout=5.0)  # ← may timeout!
```
The code handles this gracefully (continues with warning), so this alone doesn't explain failure.

#### 2. No Playback-Related Issues Visible
During transfer, the device sends playback notifications on 0x0013 concurrently. This is normal.

#### 3. File Data Format
Session 3 pattern starts with `00 00 2c 00 00 0a ...` — coordinate pairs in little-endian format.
Session 2 pattern starts with `b8 57 2c 7b 5d 0a ...` — different starting coordinates but same format.

## Key Protocol Values

| Value | Direction | Handle | Meaning |
|-------|-----------|--------|---------|
| `0x0100` | → CCCD | 0x0029 | Enable notifications |
| `0x0000` | → CCCD | 0x0029 | Disable notifications |
| `0x00` | ← notif | 0x0028 | Device ready for transfer |
| `0x6F` | → write | 0x0028 | Request new file transfer |
| `0x01` + name | ← notif | 0x0028 | Device assigned filename |
| bulk data | → write | 0x002e | Pattern data chunk (244 bytes, last may be shorter) |
| `0x02` | ← notif | 0x0028 | Chunk received ACK |
| `0x01` | → write | 0x0028 | Transfer complete signal |
| `0xFF` | ← notif | 0x002b | File list ready |
| `0x01` | → write | 0x002b | Request file list |
| `0x01` + names | ← notif | 0x002b | File names (dash-separated) |
| `0xFE` | ← notif | 0x002b | End of file list |

## Conclusion

**The code protocol matches the capture exactly.** The UUIDs resolve correctly, the sequence is right, and the acknowledgment flow is implemented.

If the device doesn't respond after writing 0x6F, the issue is likely:
1. **Connection state** — stale connection, need reconnect before transfer
2. **Device state** — device may need to be in a specific mode (stopped? idle?)
3. **BLE stack issue** — bleak/HA BLE proxy interaction problem
4. **Notification registration** — bleak might not have the callback registered in time

The protocol itself is correctly implemented in our code.
