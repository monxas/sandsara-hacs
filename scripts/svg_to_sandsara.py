#!/usr/bin/env python3
"""
Convert SVG paths to Sandsara pattern format.
Handles the constraint that the ball cannot "jump" - must retrace paths.
"""

import struct
import re
from pathlib import Path

def write_point(x, y):
    """Write point in Sandsara binary CSV format."""
    x_int = max(-32768, min(32767, int(x)))
    y_int = max(-32768, min(32767, int(y)))
    return struct.pack('<h', x_int) + b',' + struct.pack('<h', y_int) + b'\n'

def parse_svg_path(d):
    """Parse SVG path 'd' attribute into list of commands."""
    # Tokenize: split into commands and numbers
    tokens = re.findall(r'[MmCcLlHhVvSsQqTtAaZz]|[-+]?[0-9]*\.?[0-9]+', d)
    
    commands = []
    i = 0
    current_cmd = None
    
    while i < len(tokens):
        token = tokens[i]
        if token.isalpha():
            current_cmd = token
            i += 1
        else:
            # It's a number, use current command
            if current_cmd in ('M', 'm'):
                x, y = float(tokens[i]), float(tokens[i+1])
                commands.append((current_cmd, x, y))
                i += 2
                # Subsequent coords after M are implicit L
                current_cmd = 'L' if current_cmd == 'M' else 'l'
            elif current_cmd in ('L', 'l'):
                x, y = float(tokens[i]), float(tokens[i+1])
                commands.append((current_cmd, x, y))
                i += 2
            elif current_cmd in ('C', 'c'):
                # Cubic bezier: x1 y1 x2 y2 x y
                x1, y1 = float(tokens[i]), float(tokens[i+1])
                x2, y2 = float(tokens[i+2]), float(tokens[i+3])
                x, y = float(tokens[i+4]), float(tokens[i+5])
                commands.append((current_cmd, x1, y1, x2, y2, x, y))
                i += 6
            elif current_cmd in ('S', 's'):
                # Smooth cubic: x2 y2 x y
                x2, y2 = float(tokens[i]), float(tokens[i+1])
                x, y = float(tokens[i+2]), float(tokens[i+3])
                commands.append((current_cmd, x2, y2, x, y))
                i += 4
            elif current_cmd in ('Q', 'q'):
                # Quadratic: x1 y1 x y
                x1, y1 = float(tokens[i]), float(tokens[i+1])
                x, y = float(tokens[i+2]), float(tokens[i+3])
                commands.append((current_cmd, x1, y1, x, y))
                i += 4
            elif current_cmd in ('H', 'h'):
                x = float(tokens[i])
                commands.append((current_cmd, x))
                i += 1
            elif current_cmd in ('V', 'v'):
                y = float(tokens[i])
                commands.append((current_cmd, y))
                i += 1
            else:
                i += 1  # Skip unknown
    
    return commands

def cubic_bezier(p0, p1, p2, p3, t):
    """Evaluate cubic bezier at parameter t."""
    mt = 1 - t
    return (mt**3 * p0 + 3*mt**2*t * p1 + 3*mt*t**2 * p2 + t**3 * p3)

def interpolate_bezier_cubic(x0, y0, x1, y1, x2, y2, x3, y3, num_points=30):
    """Generate points along a cubic bezier curve."""
    points = []
    for i in range(num_points + 1):
        t = i / num_points
        x = cubic_bezier(x0, x1, x2, x3, t)
        y = cubic_bezier(y0, y1, y2, y3, t)
        points.append((x, y))
    return points

def interpolate_line(x0, y0, x1, y1, num_points=20):
    """Generate points along a line."""
    points = []
    for i in range(num_points + 1):
        t = i / num_points
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        points.append((x, y))
    return points

def svg_path_to_points(d, points_per_curve=30):
    """Convert SVG path to list of (x, y) points."""
    commands = parse_svg_path(d)
    points = []
    
    cx, cy = 0, 0  # Current position
    
    for cmd in commands:
        if cmd[0] == 'M':
            cx, cy = cmd[1], cmd[2]
            points.append((cx, cy))
        elif cmd[0] == 'm':
            cx += cmd[1]
            cy += cmd[2]
            points.append((cx, cy))
        elif cmd[0] == 'L':
            x, y = cmd[1], cmd[2]
            pts = interpolate_line(cx, cy, x, y, 20)[1:]
            points.extend(pts)
            cx, cy = x, y
        elif cmd[0] == 'l':
            x, y = cx + cmd[1], cy + cmd[2]
            pts = interpolate_line(cx, cy, x, y, 20)[1:]
            points.extend(pts)
            cx, cy = x, y
        elif cmd[0] == 'C':
            x1, y1, x2, y2, x, y = cmd[1:]
            pts = interpolate_bezier_cubic(cx, cy, x1, y1, x2, y2, x, y, points_per_curve)[1:]
            points.extend(pts)
            cx, cy = x, y
        elif cmd[0] == 'c':
            x1, y1, x2, y2, x, y = cmd[1:]
            # Convert relative to absolute
            pts = interpolate_bezier_cubic(cx, cy, cx+x1, cy+y1, cx+x2, cy+y2, cx+x, cy+y, points_per_curve)[1:]
            points.extend(pts)
            cx, cy = cx + x, cy + y
        elif cmd[0] == 'H':
            x = cmd[1]
            pts = interpolate_line(cx, cy, x, cy, 20)[1:]
            points.extend(pts)
            cx = x
        elif cmd[0] == 'h':
            x = cx + cmd[1]
            pts = interpolate_line(cx, cy, x, cy, 20)[1:]
            points.extend(pts)
            cx = x
        elif cmd[0] == 'V':
            y = cmd[1]
            pts = interpolate_line(cx, cy, cx, y, 20)[1:]
            points.extend(pts)
            cy = y
        elif cmd[0] == 'v':
            y = cy + cmd[1]
            pts = interpolate_line(cx, cy, cx, y, 20)[1:]
            points.extend(pts)
            cy = y
    
    return points

def transform_svg_to_sandsara(points, svg_size=109, scale=0.7):
    """
    Transform SVG coordinates to Sandsara coordinates.
    SVG: (0,0) top-left, Y+ down, range 0-109
    Sandsara: (0,0) center, Y+ up, range -32767 to 32767
    """
    result = []
    center = svg_size / 2
    max_coord = 32767 * scale
    
    for x, y in points:
        # Center and flip Y
        sx = (x - center) / center * max_coord
        sy = -(y - center) / center * max_coord  # Flip Y
        result.append((sx, sy))
    
    return result

def find_closest_point_index(points, target_x, target_y):
    """Find index of closest point to target."""
    min_dist = float('inf')
    min_idx = 0
    for i, (x, y) in enumerate(points):
        dist = (x - target_x)**2 + (y - target_y)**2
        if dist < min_dist:
            min_dist = dist
            min_idx = i
    return min_idx

def main():
    # The 9 strokes of 栄 from KanjiVG
    strokes = [
        "M25.75,18c3.61,3.85,7.48,10.58,8,12.5",  # s1 - left top mark
        "M48.25,13c1.88,3.5,4.25,9.12,5,14.25",   # s2 - center top mark
        "M79,14c0.21,1.15-0.25,2.18-0.83,2.93c-1.58,2.05-5.98,7.66-7.8,9.69",  # s3 - right top mark
        "M21.62,38.25c-0.11,3.8-2.7,13.9-3.62,16.22",  # s4 - left hook
        "M22.49,41.63c14.76-2,43.77-5.34,61.3-6.08c10.08-0.42,3.33,6.36-0.15,9.3",  # s5 - horizontal + right hook
        "M24.5,60.25c2.54,0.85,5.54,0.46,8.14,0.2c9.71-0.97,27.27-3.66,40.86-4.32c2.43-0.12,5.26-0.01,8.01,0.37",  # s6 - middle horizontal
        "M52.25,44c1,1,1.75,2.75,1.75,4.5c0,3.14,0,28.88,0,41.75c0,2.48,0,4.48,0,5.75",  # s7 - vertical
        "M51,59.5c0,0.62-0.42,1.53-0.96,2.32C43.29,71.9,29.12,84.84,17.62,90.25",  # s8 - left diagonal
        "M54.75,58.75C59.89,63.89,72.92,75.97,83,83.1c2.84,2.01,5.87,3.9,9.37,5.03",  # s9 - right diagonal
    ]
    
    # Parse all strokes
    all_stroke_points = []
    for s in strokes:
        points = svg_path_to_points(s, points_per_curve=40)
        points = transform_svg_to_sandsara(points)
        all_stroke_points.append(points)
    
    # Build final path with retracing between strokes
    final_points = []
    drawn_points = []  # All points we've drawn so far
    
    for i, stroke_points in enumerate(all_stroke_points):
        if i == 0:
            # First stroke - just draw it
            final_points.extend(stroke_points)
            drawn_points.extend(stroke_points)
        else:
            # Need to retrace from current position to start of new stroke
            current_pos = final_points[-1]
            target_pos = stroke_points[0]
            
            # Find closest point in drawn_points to target
            closest_idx = find_closest_point_index(drawn_points, target_pos[0], target_pos[1])
            
            # Find closest point in drawn_points to current position
            current_idx = find_closest_point_index(drawn_points, current_pos[0], current_pos[1])
            
            # Retrace path: from current to closest to target
            # Simple approach: go backwards through recent points, then forward to target area
            if current_idx <= closest_idx:
                retrace = drawn_points[current_idx:closest_idx+1]
            else:
                retrace = drawn_points[closest_idx:current_idx+1][::-1]
            
            # Add transition from end of retrace to start of new stroke
            if retrace:
                final_points.extend(retrace[1:])  # Skip first (duplicate of current)
            
            # Smooth transition to new stroke start
            last = final_points[-1] if final_points else (0, 0)
            transition = interpolate_line(last[0], last[1], stroke_points[0][0], stroke_points[0][1], 15)
            final_points.extend(transition[1:])
            
            # Draw the stroke
            final_points.extend(stroke_points)
            drawn_points.extend(stroke_points)
    
    # Write output
    output_path = Path(__file__).parent.parent / "research" / "patterns" / "kanji-ei-svg.bin"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    data = bytearray()
    for x, y in final_points:
        data.extend(write_point(x, y))
    
    with open(output_path, "wb") as f:
        f.write(data)
    
    print(f"Created: {output_path}")
    print(f"Total points: {len(final_points)}")
    print(f"File size: {len(data)} bytes")
    
    # Verify format
    print(f"\nFirst 3 points (hex):")
    for i in range(min(3, len(final_points))):
        offset = i * 6
        print(f"  Point {i}: {data[offset:offset+6].hex()}")

if __name__ == "__main__":
    main()
