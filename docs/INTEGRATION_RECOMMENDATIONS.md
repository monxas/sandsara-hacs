# Sandsara Integration - File Transfer Implementation Recommendations

## Current Status

The basic integration works:
- ✅ Connection and handshake
- ✅ Playback control (play/pause/next/sleep)
- ✅ LED control (on/off/color/brightness)
- ✅ Speed control (ball/LED animation)

Missing:
- ❌ Pattern upload via BLE
- ❌ Playlist management
- ❌ Pattern selection from device

---

## Recommended Implementation Approach

### Phase 1: Service Discovery & Validation

Before implementing file transfer, validate the protocol:

1. **Run the test script** (`tools/file_transfer_test.py discover`) to:
   - Confirm File Transfer service exists
   - Identify all characteristics and their properties
   - Determine which firmware UUIDs are available

2. **Document findings** - The Mini Pro may have:
   - Different characteristics than original firmware
   - Additional validation requirements
   - Different chunk size limits

### Phase 2: Add File Transfer Constants

Add to `const.py`:

```python
# File Transfer Service
SERVICE_FILE_TRANSFER = "fd31abc4-22e7-11eb-adc1-0242ac120002"

# File Transfer Characteristics
CHAR_FILE_FLAG = "fcbff68e-2af1-11eb-adc1-0242ac120002"
CHAR_FILE_DATA = "fcbffa44-2af1-11eb-adc1-0242ac120002"
CHAR_FILE_STATUS = "250e79ac-f0d7-43cc-ad6a-63544b5c6663"

# Transfer parameters
FILE_CHUNK_SIZE = 512
```

### Phase 3: Coordinator Extensions

Add these methods to `SandsaraCoordinator`:

```python
async def async_upload_pattern(
    self, 
    filename: str, 
    data: bytes,
    progress_callback: Callable[[int, int], None] | None = None
) -> bool:
    """Upload a pattern file to the device.
    
    Args:
        filename: Destination filename (e.g., "my-pattern.bin")
        data: Raw pattern data (6 bytes per point, polar coordinates)
        progress_callback: Optional callback(bytes_sent, total_bytes)
    
    Returns:
        True if successful
    """
    await self._ensure_connected()
    if not self._client:
        return False

    # Start transfer
    await self._client.write_gatt_char(
        CHAR_FILE_FLAG, 
        filename.encode('ascii'), 
        response=True
    )
    
    # Send chunks
    total = len(data)
    for i in range(0, total, FILE_CHUNK_SIZE):
        chunk = data[i:i + FILE_CHUNK_SIZE]
        await self._client.write_gatt_char(CHAR_FILE_DATA, chunk, response=True)
        await asyncio.sleep(0.05)  # Rate limiting
        
        if progress_callback:
            progress_callback(min(i + FILE_CHUNK_SIZE, total), total)
    
    # End transfer
    await self._client.write_gatt_char(CHAR_FILE_FLAG, bytes([0x00]), response=True)
    
    return True
```

### Phase 4: Home Assistant Services

Register custom services in `__init__.py`:

```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # ... existing setup ...
    
    async def handle_upload_pattern(call: ServiceCall) -> None:
        """Handle pattern upload service."""
        filename = call.data["filename"]
        file_path = call.data.get("file_path")
        pattern_data = call.data.get("pattern_data")
        
        if file_path:
            data = Path(file_path).read_bytes()
        elif pattern_data:
            data = bytes.fromhex(pattern_data)
        else:
            raise ValueError("Either file_path or pattern_data required")
        
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_upload_pattern(filename, data)
    
    hass.services.async_register(
        DOMAIN,
        "upload_pattern",
        handle_upload_pattern,
        schema=vol.Schema({
            vol.Required("filename"): cv.string,
            vol.Optional("file_path"): cv.string,
            vol.Optional("pattern_data"): cv.string,
        })
    )
```

### Phase 5: Pattern Generation Helpers

Add utilities for creating patterns programmatically:

```python
# In a new file: pattern_utils.py

import struct
import math

def create_circle_pattern(num_points: int = 360, radius: int = 128) -> bytes:
    """Create a circle pattern."""
    points = []
    for i in range(num_points):
        theta = int((i / num_points) * 65535)
        rho = 0x2C00 | (radius & 0xFF)
        counter = i
        points.append(struct.pack('>HHH', theta, rho, counter))
    return b''.join(points)

def create_spiral_pattern(
    num_points: int = 1000,
    start_radius: int = 20,
    end_radius: int = 200,
    rotations: float = 5.0
) -> bytes:
    """Create a spiral pattern."""
    points = []
    for i in range(num_points):
        t = i / num_points
        theta = int((t * rotations % 1.0) * 65535)
        radius = int(start_radius + (end_radius - start_radius) * t)
        rho = 0x2C00 | (radius & 0xFF)
        counter = i
        points.append(struct.pack('>HHH', theta, rho, counter))
    return b''.join(points)

def polar_to_pattern(
    points: list[tuple[float, float]],  # List of (angle_radians, radius_0_255)
) -> bytes:
    """Convert polar coordinates to pattern format."""
    data = []
    for i, (angle, radius) in enumerate(points):
        theta = int((angle / (2 * math.pi)) * 65535) % 65536
        rho = 0x2C00 | (int(radius) & 0xFF)
        counter = i
        data.append(struct.pack('>HHH', theta, rho, counter))
    return b''.join(data)
```

---

## UI Integration Options

### Option A: File Upload in Configuration

Add to `config_flow.py` to allow uploading patterns during setup or as options.

### Option B: Custom Lovelace Card

Create a custom card that:
- Shows current pattern/playlist
- Allows browsing uploaded patterns
- Provides pattern upload via drag-and-drop

### Option C: Services Only

Expose services and let users automate pattern uploads:
- `sandsara.upload_pattern` - Upload raw pattern
- `sandsara.upload_from_file` - Upload from file path
- `sandsara.create_pattern` - Generate pattern from parameters

---

## Testing Checklist

Before releasing file transfer:

1. [ ] Test with small pattern file (< 1KB)
2. [ ] Test with medium pattern file (10-50KB)
3. [ ] Test with large pattern file (> 100KB)
4. [ ] Test transfer interruption and recovery
5. [ ] Test concurrent transfers (should be blocked)
6. [ ] Verify pattern plays correctly after upload
7. [ ] Test playlist creation and modification
8. [ ] Document any Mini Pro specific quirks

---

## Known Risks

1. **Untested Protocol** - The file transfer protocol is reverse-engineered and not yet validated on Mini Pro

2. **Device Stability** - Writing incorrect data could crash the device or corrupt its SD card

3. **BLE Bandwidth** - Large files may take significant time; need progress feedback

4. **Pattern Format** - The exact format requirements (especially the counter field) are not fully understood

---

## Next Steps

1. **Run discovery** - Use `file_transfer_test.py discover` to validate characteristics
2. **Test small transfer** - Try sending a minimal pattern (few points)
3. **Validate playback** - Ensure uploaded patterns appear and play correctly
4. **Iterate** - Refine based on actual device behavior
