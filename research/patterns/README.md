# Sandsara Pattern File Format (.bin)

## Overview

Sandsara sand tables use binary pattern files (`.bin`) that contain sequences of X,Y coordinates. The ball follows these coordinates to draw patterns in the sand.

## File Format Specification

Each point is exactly **6 bytes**:

```
Offset  Size  Description
------  ----  -----------
0-1     2     X coordinate (signed 16-bit integer, little-endian)
2       1     Comma separator (always 0x2C = ',')
3-4     2     Y coordinate (signed 16-bit integer, little-endian)
5       1     Newline separator (always 0x0A = '\n')
```

### Visual representation:
```
[X_low][X_high][,][Y_low][Y_high][\n]
```

### Coordinate System

- **Origin**: Center of the circular table (0, 0)
- **X range**: -32767 to +32767 (left to right)
- **Y range**: -32767 to +32767 (bottom to top)
- **Scale**: Values are typically scaled to fit within the table's physical radius

The table is circular, so patterns should generally stay within a circular boundary to avoid the ball hitting the edges.

## Reading Pattern Files (Python)

```python
import struct

def read_pattern(filepath):
    """Read a Sandsara .bin pattern file and return list of (x, y) coordinates."""
    points = []
    with open(filepath, 'rb') as f:
        data = f.read()

    for i in range(0, len(data), 6):
        chunk = data[i:i+6]
        if len(chunk) == 6:
            # Little-endian signed 16-bit integers
            x = struct.unpack('<h', chunk[0:2])[0]
            y = struct.unpack('<h', chunk[3:5])[0]
            points.append((x, y))

    return points
```

## Writing Pattern Files (Python)

```python
import struct
import math

def write_pattern(filepath, points):
    """Write a list of (x, y) coordinates to a Sandsara .bin pattern file."""
    with open(filepath, 'wb') as f:
        for x, y in points:
            # Clamp to int16 range
            x = max(-32767, min(32767, int(x)))
            y = max(-32767, min(32767, int(y)))
            # Write: X (little-endian), comma, Y (little-endian), newline
            f.write(struct.pack('<h', x))  # X coordinate
            f.write(b',')                   # Comma separator
            f.write(struct.pack('<h', y))  # Y coordinate
            f.write(b'\n')                  # Newline separator

# Example: Create a circle pattern
def create_circle(radius=20000, num_points=500):
    points = []
    for i in range(num_points):
        angle = (i / num_points) * 2 * math.pi
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        points.append((x, y))
    return points

# Example: Create a heart pattern
def create_heart(scale=1000, num_points=500):
    points = []
    for i in range(num_points):
        t = (i / num_points) * 2 * math.pi
        # Parametric heart equations
        x = 16 * (math.sin(t) ** 3)
        y = 13 * math.cos(t) - 5 * math.cos(2*t) - 2 * math.cos(3*t) - math.cos(4*t)
        points.append((x * scale, y * scale))
    return points

# Example: Create a spiral pattern
def create_spiral(max_radius=25000, num_rotations=10, points_per_rotation=100):
    points = []
    total_points = num_rotations * points_per_rotation
    for i in range(total_points):
        progress = i / total_points  # 0 to 1
        angle = progress * num_rotations * 2 * math.pi
        radius = progress * max_radius  # Grows from 0 to max_radius
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        points.append((x, y))
    return points

# Write examples
write_pattern('my_circle.bin', create_circle())
write_pattern('my_heart.bin', create_heart())
write_pattern('my_spiral.bin', create_spiral())
```

## Converting from Theta-Rho (.thr) Format

The Sisyphus table uses `.thr` files with theta (angle in radians) and rho (radius 0-1). To convert:

```python
import math

def thr_to_bin(thr_filepath, bin_filepath, max_radius=25000):
    """Convert a .thr file to Sandsara .bin format."""
    points = []

    with open(thr_filepath, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2:
                theta = float(parts[0])  # Angle in radians
                rho = float(parts[1])    # Normalized radius (0-1)

                # Convert polar to Cartesian
                x = rho * max_radius * math.cos(theta)
                y = rho * max_radius * math.sin(theta)
                points.append((x, y))

    write_pattern(bin_filepath, points)
```

## Tips for Creating Patterns

1. **Stay within bounds**: Keep coordinates within ±25000 to ensure the pattern fits on the table
2. **Smooth transitions**: Add intermediate points for smooth curves
3. **Start and end**: Consider where the ball starts and ends for seamless looping
4. **Point density**: More points = smoother curves but larger files. ~100-500 points per full rotation is typical
5. **Test patterns**: Use the web visualizer (`webui/`) to preview before uploading

## File Naming Convention

Sandsara uses the naming pattern: `Sandsara-trackNumber-XXXX.bin` where XXXX is a 4-digit number (e.g., `Sandsara-trackNumber-0001.bin`).

## Source

Format discovered by reverse-engineering the [Sandsara firmware](https://github.com/Sandsara/firmwareSandsara), specifically the `SdFiles.cpp` file which contains the binary parsing code.
