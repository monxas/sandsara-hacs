# Sandsara Pattern Files

Pattern files from the Sandsara SD card for reverse engineering.

## Format Analysis Results

### File Structure

- **Format**: Binary, no header
- **Coordinate System**: Polar (θ, ρ)
- **Point Size**: 6 bytes per point
- **Encoding**: Big-endian unsigned 16-bit integers

### 6-Byte Point Structure

```
Offset  Size  Description
------  ----  -----------
0-1     2     Theta (θ) - angle, 0-65535 maps to 0-360°
2-3     2     Rho (ρ) - radius, always 0x2Cxx (11264-11519)
4-5     2     Counter/timing value (purpose unclear)
```

### Key Observations

1. **Theta** (bytes 0-1):
   - Full range 0-65535 = 0° to 360°
   - Pattern shape comes from theta sequence, not smooth progression

2. **Rho** (bytes 2-3):
   - Always in range 0x2C00 to 0x2CFF (11264-11519)
   - High byte 0x2C appears to be format marker
   - Low byte (0x00-0xFF) is actual radius value (0-255 levels)
   - Radius variation is minimal; patterns stay near table edge

3. **Counter** (bytes 4-5):
   - Not monotonically increasing
   - Possibly timing/speed hint or control data

### Sample Files

| File | Points | Description |
|------|--------|-------------|
| testing-circle.bin | 896 | Circle pattern (constant rho, varying theta) |
| testing-spiral.bin | 6,217 | Spiral-like pattern |
| testing-x.bin | 752 | X/cross pattern (theta oscillates) |
| Sandsara-trackNumber-XXXX.bin | varies | Production patterns from SD card |

### Visualization

Run `python3 analyze_pattern.py` or `python3 visualize_path.py` to generate plots in `plots/`.

## Converting Coordinates

```python
import struct, math

def read_point(data, offset):
    theta_raw, rho_raw, counter = struct.unpack('>HHH', data[offset:offset+6])
    theta_rad = (theta_raw / 65535.0) * 2 * math.pi
    rho = rho_raw & 0xFF  # Extract low byte (0-255)
    return theta_rad, rho, counter

def polar_to_cartesian(theta, rho):
    x = rho * math.cos(theta)
    y = rho * math.sin(theta)
    return x, y
```

## Open Questions

1. What does the counter/timing field (bytes 4-5) control?
2. Is 0x2C a format version marker or has another meaning?
3. How does the device interpolate between points?
4. Can custom patterns be uploaded via BLE file transfer service?
