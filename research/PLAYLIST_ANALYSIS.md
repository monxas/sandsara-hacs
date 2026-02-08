# Playlist Analysis — Why Uploaded Tracks Fail on Select

**Date:** 2026-02-08
**Status:** Fixed in v2.6.0

## Root Cause

After uploading a pattern file, the official app sends a **playlist add command** (`0x0B` + ASCII track ID) to the PLAYBACK characteristic. Without this, the track exists on the device's flash storage but is NOT in the active playlist. When you try to select a track that isn't in the playlist, the device briefly acknowledges it then reverts to a playlist track.

## Evidence from HCI Capture

All writes to PLAYBACK (handle 0x0013) in the capture:

```
Frame 169887: 0b 333032    → 0x0B + "302" = ADD track 302 to playlist
Frame 195863: 0b 333033    → 0x0B + "303" = ADD track 303 to playlist (after upload)
Frame 266412: 0b 333131    → 0x0B + "311" = ADD track 311 to playlist (after upload)
```

The pattern is clear: after every file upload, the app writes `0x0B` + ASCII track_id to PLAYBACK. This is why tracks 302, 303, 311 appear in the device playlist `[1,2,3,4,5,6,7,9,10,18,33,302,303,311]` and our uploads (315-318) do not.

## Protocol

```
PLAYBACK characteristic: 10b59496-bf86-44a8-ba7a-67d8e26a93eb

Command 0x0B = Add track to device playlist
  Format: 0x0B + ASCII_TRACK_ID
  Example: bytes([0x0B]) + b"303"  →  adds track 303
```

## Fix Applied (v2.6.0)

1. **const.py**: Added `PB_ADD_TO_PLAYLIST = 0x0B`
2. **coordinator.py**: Added `async_add_track_to_device_playlist()` method
3. **Upload flow**: After file transfer completes, automatically sends 0x0B to add track to device playlist
4. **Select flow**: If selecting a track not in playlist (ID >= 100), automatically adds it first

## Other Playback Commands Observed

| Byte | ASCII | Command | Example |
|------|-------|---------|---------|
| 0x00 | | PB_INIT | `00` |
| 0x01 | | PB_SELECT | `01` + "12" (track file ID) |
| 0x04 | | PB_SLEEP | `04` |
| 0x05 | | PB_PREV | `05` |
| 0x06 | | PB_NEXT | `06` |
| 0x07 | | PB_PLAY | `07` |
| 0x08 | | PB_PAUSE | `08` |
| 0x09 | | Unknown | `09 00` (seen after playlist add) |
| 0x0B | | PB_ADD_TO_PLAYLIST | `0b` + "303" |
| 0x0D | | PB_SHUFFLE | `0d 01`/`0d 00` |
