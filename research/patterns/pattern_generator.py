#!/usr/bin/env python3
"""
Sandsara Pattern Generator

Create custom patterns for the Sandsara sand table.
Patterns are saved as .bin files that can be uploaded to the table.

Usage:
    python pattern_generator.py

Format:
    Each point is 6 bytes:
    - Bytes 0-1: X coordinate (signed 16-bit, little-endian)
    - Byte 2: Comma separator (0x2C)
    - Bytes 3-4: Y coordinate (signed 16-bit, little-endian)
    - Byte 5: Newline (0x0A)
"""

import struct
import math
from pathlib import Path


def write_pattern(filepath, points):
    """Write a list of (x, y) coordinates to a Sandsara .bin pattern file."""
    with open(filepath, 'wb') as f:
        for x, y in points:
            x = max(-32767, min(32767, int(x)))
            y = max(-32767, min(32767, int(y)))
            f.write(struct.pack('<h', x))  # X little-endian
            f.write(b',')                   # Comma
            f.write(struct.pack('<h', y))  # Y little-endian
            f.write(b'\n')                  # Newline
    print(f"Created {filepath} with {len(points)} points ({len(points) * 6} bytes)")


def read_pattern(filepath):
    """Read a Sandsara .bin pattern file and return list of (x, y) tuples."""
    points = []
    with open(filepath, 'rb') as f:
        data = f.read()
    for i in range(0, len(data), 6):
        chunk = data[i:i+6]
        if len(chunk) == 6:
            x = struct.unpack('<h', chunk[0:2])[0]
            y = struct.unpack('<h', chunk[3:5])[0]
            points.append((x, y))
    return points


# =============================================================================
# Pattern Generators
# =============================================================================

def circle(radius=20000, num_points=500):
    """Create a simple circle."""
    points = []
    for i in range(num_points):
        angle = (i / num_points) * 2 * math.pi
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        points.append((x, y))
    return points


def spiral(max_radius=25000, num_rotations=10, points_per_rotation=100):
    """Create an outward spiral from center to edge."""
    points = []
    total_points = num_rotations * points_per_rotation
    for i in range(total_points):
        progress = i / total_points
        angle = progress * num_rotations * 2 * math.pi
        radius = progress * max_radius
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        points.append((x, y))
    return points


def heart(scale=1200, num_points=500):
    """Create a heart shape using parametric equations."""
    points = []
    for i in range(num_points):
        t = (i / num_points) * 2 * math.pi
        x = 16 * (math.sin(t) ** 3)
        y = 13 * math.cos(t) - 5 * math.cos(2*t) - 2 * math.cos(3*t) - math.cos(4*t)
        points.append((x * scale, y * scale))
    return points


def star(outer_radius=22000, inner_radius=10000, num_points_val=5, samples_per_segment=50):
    """Create a star with specified number of points."""
    points = []
    total_vertices = num_points_val * 2
    for i in range(total_vertices + 1):
        vertex_idx = i % total_vertices
        angle = (vertex_idx / total_vertices) * 2 * math.pi - math.pi / 2
        radius = outer_radius if vertex_idx % 2 == 0 else inner_radius
        target_x = radius * math.cos(angle)
        target_y = radius * math.sin(angle)

        if i == 0:
            points.append((target_x, target_y))
        else:
            # Interpolate from previous point
            prev_x, prev_y = points[-1]
            for j in range(1, samples_per_segment + 1):
                t = j / samples_per_segment
                x = prev_x + (target_x - prev_x) * t
                y = prev_y + (target_y - prev_y) * t
                points.append((x, y))
    return points


def flower(radius=20000, petals=6, num_points=1000):
    """Create a flower/rose curve pattern."""
    points = []
    k = petals
    for i in range(num_points):
        angle = (i / num_points) * 2 * math.pi * petals
        r = radius * math.cos(k * angle / petals)
        x = r * math.cos(angle)
        y = r * math.sin(angle)
        points.append((x, y))
    return points


def lissajous(a=3, b=4, delta=math.pi/2, radius=20000, num_points=1000):
    """Create a Lissajous curve pattern."""
    points = []
    for i in range(num_points):
        t = (i / num_points) * 2 * math.pi
        x = radius * math.sin(a * t + delta)
        y = radius * math.sin(b * t)
        points.append((x, y))
    return points


def polygon(sides=6, radius=20000, samples_per_side=100):
    """Create a regular polygon."""
    points = []
    for i in range(sides):
        angle1 = (i / sides) * 2 * math.pi - math.pi / 2
        angle2 = ((i + 1) / sides) * 2 * math.pi - math.pi / 2
        x1, y1 = radius * math.cos(angle1), radius * math.sin(angle1)
        x2, y2 = radius * math.cos(angle2), radius * math.sin(angle2)
        for j in range(samples_per_side):
            t = j / samples_per_side
            points.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t))
    return points


def wave_circle(base_radius=18000, wave_amplitude=4000, waves=12, num_points=1000):
    """Create a circle with wavy edges."""
    points = []
    for i in range(num_points):
        angle = (i / num_points) * 2 * math.pi
        radius = base_radius + wave_amplitude * math.sin(waves * angle)
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        points.append((x, y))
    return points


# =============================================================================
# Main - Generate example patterns
# =============================================================================

if __name__ == '__main__':
    output_dir = Path(__file__).parent / 'samples'
    output_dir.mkdir(exist_ok=True)

    print("Generating example patterns...\n")

    # Generate various patterns
    patterns = {
        'example-circle.bin': circle(),
        'example-spiral.bin': spiral(),
        'example-heart.bin': heart(),
        'example-star.bin': star(),
        'example-flower.bin': flower(),
        'example-lissajous.bin': lissajous(),
        'example-hexagon.bin': polygon(sides=6),
        'example-wave-circle.bin': wave_circle(),
    }

    for name, pts in patterns.items():
        write_pattern(output_dir / name, pts)

    print(f"\nGenerated {len(patterns)} patterns in {output_dir}/")
