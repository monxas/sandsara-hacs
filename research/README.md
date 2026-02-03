# Research Files

Files for future reverse engineering of undiscovered protocol features.

## What's NOT yet implemented

### File Transfer / Pattern Upload

The Sandsara has a second BLE service for uploading sand patterns:

**Service UUID:** `fd31abc4-22e7-11eb-adc1-0242ac120002`

| Characteristic | UUID | Purpose |
|----------------|------|---------|
| File send flag | `fcbff68e-...` | Start/stop transfer |
| File unknown | `27566b01-...` | Unknown |
| File send data | `fcbffa44-...` | Actual file data |
| File status | `250e79ac-...` | Transfer status |

### Playlist Management

The playback characteristic returns playlist data like `"1-2-3-4-5-6-7-8-9-10"` but we haven't decoded how to:
- List available patterns
- Add/remove patterns from playlist
- Reorder playlist

## Files in this directory

### `hci_captures/`
Bluetooth HCI snoop logs captured from Android while using the official Sandsara app.
- Open with Wireshark: `wireshark BT_HCI_*.curf`
- Or use tshark: `tshark -r BT_HCI_*.curf -Y "btatt"`

### `Bluetooth.cpp` / `Bluetooth.h`
Original Sandsara firmware BLE code (open source, but for older hardware).
- Different UUIDs than Mini Pro, but similar logic
- Contains file receive callbacks that may help understand the protocol

### `libapp_file_transfer_strings.txt`
Extracted strings from the Flutter app binary related to file transfer.
- Method names like `sendPlaylist`, `_parseDeviceInfo`
- May contain hints about the file transfer protocol

## How to capture new HCI logs

1. On Android: Settings → Developer Options → Enable Bluetooth HCI snoop log
2. Toggle Bluetooth off/on to start fresh capture
3. Use the Sandsara app to upload a pattern
4. Run: `adb bugreport bugreport.zip`
5. Extract and find: `FS/data/misc/bluetooth/logs/BT_HCI_*.curf`
