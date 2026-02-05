# File Transfer Protocol - Test Results

**Date:** 2026-02-06  
**Status:** ⏳ Blocked - No BLE hardware access

---

## Test Environment

| Item | Status |
|------|--------|
| Test script ready | ✅ `tools/file_transfer_test.py` |
| Dependencies (bleak) | ✅ Installed |
| BLE hardware access | ❌ LXC container has no Bluetooth |
| HA BLE Proxies | ❌ All ESP32 proxies unavailable |
| Sandsara device | 📍 MAC: `94:B9:7E:F1:10:76` |
| HA Integration | ✅ Loaded but device unavailable |

---

## Findings

### 1. BLE Access
- The test environment (LXC container `101`) has no direct Bluetooth hardware
- Home Assistant's ESP32 BLE proxies are all offline since 2026-02-04
- No paired nodes with BLE capability available

### 2. Sandsara in Home Assistant
The Sandsara is registered in HA with:
- Config entry ID: `01KGGC7QK0VNBMNDCBD10GBAA7`
- Domain: `sandsara`
- MAC Address: `94:B9:7E:F1:10:76`
- State: `loaded` (but entities show `unavailable`)

### 3. Test Scripts Ready
Two scripts prepared:
- `tools/file_transfer_test.py` - Full test suite (scan, discover, send)
- `tools/simple_ble_test.py` - Minimal connectivity test

---

## How to Test Manually

### Option A: From a machine with Bluetooth
```bash
# Install dependencies
pip install bleak

# Run simple test (auto-scan)
cd /root/clawd/sandsara-hacs
python3 tools/simple_ble_test.py

# Or specify MAC directly
python3 tools/simple_ble_test.py 94:B9:7E:F1:10:76

# Full test with file transfer
python3 tools/file_transfer_test.py discover   # Service discovery
python3 tools/file_transfer_test.py test       # Send test pattern
```

### Option B: Fix HA BLE Proxies
1. Check power on ESP32 BLE proxy devices
2. Verify they're online in ESPHome dashboard
3. Once proxies are back, Sandsara should reconnect
4. File transfer would need to be tested via custom HA service

### Option C: Run from Proxmox Host
If Proxmox host has a USB Bluetooth adapter:
```bash
ssh root@192.168.0.50
pip install bleak
python3 /path/to/simple_ble_test.py
```

---

## Protocol to Verify (when BLE available)

1. **Service Discovery**
   - Verify `fd31abc4-22e7-11eb-adc1-0242ac120002` service exists
   - Confirm `FILE_FLAG` and `FILE_DATA` characteristics present
   - Check characteristic properties (write, notify)

2. **Transfer Protocol**
   - Write filename to FILE_FLAG → expect "ok" notification
   - Write 512-byte chunks to FILE_DATA → expect "1" per chunk
   - Write 0x00 to FILE_FLAG → expect "done" notification

3. **Pattern Validation**
   - Verify test pattern appears in device playlist
   - Confirm pattern plays correctly

---

## Next Steps

- [ ] Restore ESP32 BLE proxy connectivity
- [ ] OR get direct BLE access from another machine
- [ ] Run `simple_ble_test.py` to verify connectivity
- [ ] Run `file_transfer_test.py discover` for service discovery
- [ ] Test file transfer with simple circle pattern
- [ ] Document actual device responses vs expected

---

## Related Files

- `tools/file_transfer_test.py` - Main test script
- `tools/simple_ble_test.py` - Simple connectivity test
- `docs/FILE_TRANSFER_PROTOCOL.md` - Protocol documentation
- `research/Bluetooth.cpp` - Original firmware source
