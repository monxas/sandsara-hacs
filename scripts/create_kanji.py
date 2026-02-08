#!/usr/bin/env python3
"""
Create a Sandsara pattern for the kanji 栄 (prosperity/glory)
Binary CSV format: X (int16 LE) + ',' + Y (int16 LE) + '\n'
"""

import struct
from pathlib import Path

def write_point(x, y):
    """Write a point in binary CSV format. x,y are normalized -1 to 1."""
    x_int = max(-32768, min(32767, int(x * 32767)))
    y_int = max(-32768, min(32767, int(y * 32767)))
    return struct.pack('<h', x_int) + b',' + struct.pack('<h', y_int) + b'\n'

def interpolate_line(x1, y1, x2, y2, num_points=20):
    """Generate points along a line."""
    points = []
    for i in range(num_points + 1):
        t = i / num_points
        x = x1 + (x2 - x1) * t
        y = y1 + (y2 - y1) * t
        points.append((x, y))
    return points

def interpolate_curve(points_list, num_per_segment=15):
    """Generate points along multiple segments."""
    result = []
    for i in range(len(points_list) - 1):
        x1, y1 = points_list[i]
        x2, y2 = points_list[i + 1]
        segment = interpolate_line(x1, y1, x2, y2, num_per_segment)
        if i > 0:
            segment = segment[1:]  # Skip first point (duplicate)
        result.extend(segment)
    return result

def create_kanji_ei():
    """
    Create the kanji 栄 (prosperity)
    Coordinate system: center is (0,0), range -1 to 1
    Y+ is up, X+ is right
    """
    all_points = []
    
    # The kanji 栄 consists of these strokes (simplified):
    # Top part: three small marks (like flames/leaves)
    # Middle: horizontal line with downward hooks
    # Bottom: 木 (tree) radical
    
    # Scale factor for the whole character
    s = 0.85
    
    # === TOP THREE MARKS ===
    # Left mark (small diagonal)
    stroke1 = [
        (-0.25 * s, 0.75 * s),
        (-0.20 * s, 0.65 * s),
        (-0.18 * s, 0.55 * s),
    ]
    all_points.extend(interpolate_curve(stroke1, 12))
    
    # Move to center mark
    all_points.extend(interpolate_line(stroke1[-1][0], stroke1[-1][1], 0, 0.8 * s, 8))
    
    # Center mark (vertical dash)
    stroke2 = [
        (0, 0.8 * s),
        (0, 0.65 * s),
    ]
    all_points.extend(interpolate_curve(stroke2, 12))
    
    # Move to right mark
    all_points.extend(interpolate_line(stroke2[-1][0], stroke2[-1][1], 0.20 * s, 0.75 * s, 8))
    
    # Right mark (small diagonal)
    stroke3 = [
        (0.20 * s, 0.75 * s),
        (0.25 * s, 0.65 * s),
        (0.22 * s, 0.55 * s),
    ]
    all_points.extend(interpolate_curve(stroke3, 12))
    
    # === HORIZONTAL WITH HOOKS (冖 like shape) ===
    # Move to start
    all_points.extend(interpolate_line(stroke3[-1][0], stroke3[-1][1], -0.45 * s, 0.45 * s, 10))
    
    # Left hook down
    stroke4 = [
        (-0.45 * s, 0.45 * s),
        (-0.42 * s, 0.35 * s),
        (-0.35 * s, 0.25 * s),
    ]
    all_points.extend(interpolate_curve(stroke4, 15))
    
    # Move to horizontal bar start
    all_points.extend(interpolate_line(stroke4[-1][0], stroke4[-1][1], -0.50 * s, 0.40 * s, 8))
    
    # Main horizontal bar
    stroke5 = interpolate_line(-0.50 * s, 0.40 * s, 0.50 * s, 0.40 * s, 30)
    all_points.extend(stroke5)
    
    # Right hook down
    stroke6 = [
        (0.50 * s, 0.40 * s),
        (0.45 * s, 0.30 * s),
        (0.38 * s, 0.22 * s),
    ]
    all_points.extend(interpolate_curve(stroke6, 15))
    
    # === MIDDLE HORIZONTAL ===
    all_points.extend(interpolate_line(stroke6[-1][0], stroke6[-1][1], -0.35 * s, 0.15 * s, 10))
    stroke7 = interpolate_line(-0.35 * s, 0.15 * s, 0.35 * s, 0.15 * s, 25)
    all_points.extend(stroke7)
    
    # === BOTTOM 木 (TREE) RADICAL ===
    # Vertical center line
    all_points.extend(interpolate_line(0.35 * s, 0.15 * s, 0, 0.10 * s, 10))
    stroke8 = interpolate_line(0, 0.10 * s, 0, -0.70 * s, 40)
    all_points.extend(stroke8)
    
    # Left diagonal branch
    all_points.extend(interpolate_line(0, -0.10 * s, 0, -0.10 * s, 5))  # small pause at branch point
    stroke9 = [
        (0, -0.10 * s),
        (-0.20 * s, -0.30 * s),
        (-0.40 * s, -0.55 * s),
    ]
    all_points.extend(interpolate_curve(stroke9, 25))
    
    # Move back to center for right branch
    all_points.extend(interpolate_line(-0.40 * s, -0.55 * s, 0, -0.10 * s, 15))
    
    # Right diagonal branch
    stroke10 = [
        (0, -0.10 * s),
        (0.20 * s, -0.30 * s),
        (0.40 * s, -0.55 * s),
    ]
    all_points.extend(interpolate_curve(stroke10, 25))
    
    # Small horizontal at bottom of tree (the root line)
    all_points.extend(interpolate_line(0.40 * s, -0.55 * s, -0.25 * s, -0.45 * s, 12))
    stroke11 = interpolate_line(-0.25 * s, -0.45 * s, 0.25 * s, -0.45 * s, 20)
    all_points.extend(stroke11)
    
    return all_points

def main():
    points = create_kanji_ei()
    
    # Write to binary file
    output_path = Path(__file__).parent.parent / "research" / "patterns" / "kanji-ei-prosperity.bin"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    data = bytearray()
    for x, y in points:
        data.extend(write_point(x, y))
    
    with open(output_path, "wb") as f:
        f.write(data)
    
    print(f"Created {output_path}")
    print(f"Total points: {len(points)}")
    print(f"File size: {len(data)} bytes")

if __name__ == "__main__":
    main()
