# Sandsara File Transfer — Deep Protocol Analysis (Agent C)

Capture: `/tmp/sandsara-real/FS/data/misc/bluetooth/logs/BT_HCI_2026_0208_004826.cfa.curf`
Device: `94:B9:7E:F1:10:76`

## Key Findings (TL;DR)
- **MTU negotiation:** Client requests **512**, server responds **255** (ATT MTU=255). Max data payload observed **250 bytes**.
- **Actual handles in this transfer** (based on HCI):
  - **File Flag char value handle = 0x0028**
  - **File Flag CCCD handle = 0x0029**
  - **File Data char value handle = 0x002e**
- **Write type for file data:** **Write Request (0x12)** with **Write Response (0x13)**, *not* Write Command.
- **CCCD enable/disable used explicitly** (0x0001 then 0x0000).
- **FILE_STATUS (0x0034/0x0035)**: **no traffic** in entire capture.
- **FILE_UNKNOWN (0x002b)**: used in *other* sessions, **not used** in the transfer at 12287s.
- **COMMAND (0x001f)**: no writes before/around transfer.

## MTU Exchange
From frame 53440/53445 (and similarly in later sessions):
- **Exchange MTU Request:** Client Rx MTU = **512**
- **Exchange MTU Response:** Server Rx MTU = **255**

This allows **250-byte** ATT value payloads (observed). Our current `FILE_CHUNK_SIZE=244` is smaller than the app’s actual chunk size in this capture.

## 60s Window Before First File Data Write
**First file data write:** frame **174676**, time **12287.084628** (Write Request to 0x002e, 250 bytes)

**Window:** 12227.0s → 12287.1s (all ATT traffic)

**Observed sequence (in order):**
1. **Periodic notifications on 0x0013** (opcode 0x1b) every ~6–7s
   - Values: `023737`, `023738`, `023739`, `023830`, `023831`, `023832`, `023833`, `023834`, `023835`, `023836`
   - Not part of file transfer; likely DATETIME/clock tick or status.
2. **CCCD enable for File Flag**
   - **Frame 174666 @ 12286.838s:** Write Request to **0x0029** (CCCD) value **0x0001 (Notify)**
   - **Frame 174669 @ 12286.923s:** Write Response
3. **Ready signal**
   - **Frame 174668 @ 12286.923s:** Notification on **0x0028** with **0x00**
4. **Start transfer**
   - **Frame 174670 @ 12286.939s:** Write Request to **0x0028** value **0x6F**
5. **Filename ack**
   - **Frame 174673 @ 12287.069s:** Notification on **0x0028** value **0x01 33 30 33** (ASCII “303”)
6. **First data chunk**
   - **Frame 174676 @ 12287.084s:** Write Request to **0x002e**, **250 bytes**

After this, the pattern repeats: each **Write Request to 0x002e** is followed by **Write Response** and **0x02** notification on 0x0028.

## File Transfer Sequence (Exact Observed Protocol)
**Handles in this connection:**
- File Flag = **0x0028**
- File Flag CCCD = **0x0029**
- File Data = **0x002e**

**Sequence:**
1. **Enable notifications** on File Flag CCCD (Write Request 0x0001 → handle 0x0029)
2. **Wait for 0x00** notification on File Flag (handle 0x0028)
3. **Write 0x6F** to File Flag (Write Request → 0x0028)
4. **Wait for 0x01 + ASCII filename** notification on File Flag
5. **Send file chunks** to File Data (handle 0x002e)
   - **Write Request (0x12) with response (0x13)**
   - **Chunk size = 250 bytes**
   - **After each chunk:** File Flag notifies **0x02** (ack)
6. **Write 0x01** to File Flag (transfer complete)
   - Frame 176608 @ 12308.186s
7. **Disable notifications** on File Flag CCCD (write 0x0000)
   - Frame 176613 @ 12308.289s

## Why Our Upload Fails (Likely Causes)
1. **Race condition on “ready” notification (0x00):**
   - The app’s **0x00** ready notify arrives **immediately after CCCD enable**.
   - Our code calls `start_notify(...)` **then clears `_flag_event`**. If the notify arrives before the clear, the event is wiped and we **timeout waiting**.
2. **Chunk size mismatch:**
   - App uses **250-byte chunks**, we use **244**. Not necessarily fatal, but different from real behavior.
3. **MTU not explicitly requested in our flow:**
   - App requests **512 → 255 MTU** before transfer. If we don’t, host may default to **23**, making large writes fail or be truncated.

## Proposed Fix (Python changes)
Below is a concrete patch idea for `async_upload_pattern` (focus: remove race, request MTU, use observed chunk size):

```python
# --- before start_notify
_flag_event.clear()
_flag_data = bytearray()

# Optional: request MTU (BlueZ backend supports it)
try:
    await self._client._backend.exchange_mtu(255)  # or 512
except Exception:
    pass

# Enable notifications
await self._client.start_notify(CHAR_FILE_FLAG, _file_flag_handler)

# Wait for 0x00 (ready) — but don't wipe event after start_notify
try:
    await asyncio.wait_for(_flag_event.wait(), timeout=5.0)
except asyncio.TimeoutError:
    _LOGGER.warning("Sandsara: no ready signal on File Flag (continuing)")

# ... after receive/timeout, continue
```

**Chunk size adjustment:**
```python
# Compute from MTU (255): max_value = 255 - 3 = 252; app uses 250
FILE_CHUNK_SIZE = 250
```

**Also consider:**
- Using `write_gatt_descriptor` explicitly for CCCD (0x0001/0x0000) to ensure write-with-response.
- If ready signal is missed, perform a **read** on File Flag or proceed directly to writing 0x6F (app seems tolerant).

## Notes / Other Observations
- FILE_UNKNOWN (0x002b) **used in other sessions** with `0xFF → write 0x01 → 0x01+filename → 0xFE` (matches list-files behavior), but **not in the transfer window**.
- COMMAND (0x001f) **unused** in the transfer window.
- FILE_STATUS not used at all in this capture.

---

## Appendix: Key Frames
- **MTU Exchange:** 53440 (req 512), 53445 (rsp 255)
- **CCCD enable:** 174666 (write 0x0001 → 0x0029)
- **Ready notify:** 174668 (0x00 → 0x0028)
- **Start transfer:** 174670 (write 0x6F → 0x0028)
- **Filename ack:** 174673 (0x01 33 30 33 → 0x0028)
- **First data chunk:** 174676 (write 250 bytes → 0x002e)
- **Transfer complete:** 176608 (write 0x01 → 0x0028)
- **CCCD disable:** 176613 (write 0x0000 → 0x0029)
```
