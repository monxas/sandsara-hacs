#!/usr/bin/env python3
"""
Convert SVG paths to Sandsara pattern format.

Sandsara pattern rules (from analyzing 100 original patterns):
- Binary CSV: signed int16 LE (X) + 0x2C + signed int16 LE (Y) + 0x0A = 6 bytes/point
- Coordinates are CARTESIAN (X, Y), NOT polar
- All points must be within circle: sqrt(x²+y²) <= 32767
- Step distance between consecutive points should be ~250 (range 217-285 typical)
- No duplicate points (step=0) or huge jumps (step>1000)
- Most patterns use full radius (max_r ≈ 32767)
"""

import struct
import re
import math
from pathlib import Path


def write_point(x, y):
    """Write point in Sandsara binary CSV format."""
    x_int = max(-32768, min(32767, int(round(x))))
    y_int = max(-32768, min(32767, int(round(y))))
    return struct.pack('<h', x_int) + b',' + struct.pack('<h', y_int) + b'\n'


def parse_svg_path(d):
    """Parse SVG path 'd' attribute into list of commands."""
    tokens = re.findall(r'[MmCcLlHhVvSsQqTtAaZz]|[-+]?[0-9]*\.?[0-9]+', d)
    commands = []
    i = 0
    current_cmd = None
    while i < len(tokens):
        token = tokens[i]
        if token.isalpha():
            current_cmd = token
            i += 1
            if current_cmd in ('Z', 'z'):
                commands.append((current_cmd,))
        else:
            if current_cmd in ('M', 'm'):
                x, y = float(tokens[i]), float(tokens[i+1])
                commands.append((current_cmd, x, y))
                i += 2
                current_cmd = 'L' if current_cmd == 'M' else 'l'
            elif current_cmd in ('L', 'l'):
                x, y = float(tokens[i]), float(tokens[i+1])
                commands.append((current_cmd, x, y))
                i += 2
            elif current_cmd in ('C', 'c'):
                x1, y1 = float(tokens[i]), float(tokens[i+1])
                x2, y2 = float(tokens[i+2]), float(tokens[i+3])
                x, y = float(tokens[i+4]), float(tokens[i+5])
                commands.append((current_cmd, x1, y1, x2, y2, x, y))
                i += 6
            elif current_cmd in ('S', 's'):
                x2, y2 = float(tokens[i]), float(tokens[i+1])
                x, y = float(tokens[i+2]), float(tokens[i+3])
                commands.append((current_cmd, x2, y2, x, y))
                i += 4
            elif current_cmd in ('Q', 'q'):
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
            elif current_cmd in ('A', 'a'):
                # Arc: rx ry x-rotation large-arc sweep x y
                rx = float(tokens[i])
                ry = float(tokens[i+1])
                rot = float(tokens[i+2])
                large = float(tokens[i+3])
                sweep = float(tokens[i+4])
                x = float(tokens[i+5])
                y = float(tokens[i+6])
                commands.append((current_cmd, rx, ry, rot, large, sweep, x, y))
                i += 7
            else:
                i += 1
    return commands


def cubic_bezier(p0, p1, p2, p3, t):
    """Evaluate cubic bezier at parameter t."""
    mt = 1 - t
    return mt**3 * p0 + 3*mt**2*t * p1 + 3*mt*t**2 * p2 + t**3 * p3


def svg_path_to_points(d, points_per_curve=30):
    """Convert SVG path to list of (x, y) points."""
    commands = parse_svg_path(d)
    points = []
    cx, cy = 0, 0
    start_x, start_y = 0, 0  # For Z command

    for cmd in commands:
        if cmd[0] == 'M':
            cx, cy = cmd[1], cmd[2]
            start_x, start_y = cx, cy
            points.append((cx, cy))
        elif cmd[0] == 'm':
            cx += cmd[1]; cy += cmd[2]
            start_x, start_y = cx, cy
            points.append((cx, cy))
        elif cmd[0] == 'L':
            cx, cy = cmd[1], cmd[2]
            points.append((cx, cy))
        elif cmd[0] == 'l':
            cx += cmd[1]; cy += cmd[2]
            points.append((cx, cy))
        elif cmd[0] == 'C':
            x1, y1, x2, y2, x, y = cmd[1:]
            for i in range(1, points_per_curve + 1):
                t = i / points_per_curve
                px = cubic_bezier(cx, x1, x2, x, t)
                py = cubic_bezier(cy, y1, y2, y, t)
                points.append((px, py))
            cx, cy = x, y
        elif cmd[0] == 'c':
            x1, y1, x2, y2, x, y = cmd[1:]
            ax1, ay1 = cx+x1, cy+y1
            ax2, ay2 = cx+x2, cy+y2
            ax, ay = cx+x, cy+y
            for i in range(1, points_per_curve + 1):
                t = i / points_per_curve
                px = cubic_bezier(cx, ax1, ax2, ax, t)
                py = cubic_bezier(cy, ay1, ay2, ay, t)
                points.append((px, py))
            cx, cy = ax, ay
        elif cmd[0] == 'S':
            x2, y2, x, y = cmd[1:]
            # Reflect previous control point
            x1, y1 = cx, cy  # simplified
            for i in range(1, points_per_curve + 1):
                t = i / points_per_curve
                px = cubic_bezier(cx, x1, x2, x, t)
                py = cubic_bezier(cy, y1, y2, y, t)
                points.append((px, py))
            cx, cy = x, y
        elif cmd[0] == 's':
            x2, y2, x, y = cmd[1:]
            ax2, ay2 = cx+x2, cy+y2
            ax, ay = cx+x, cy+y
            for i in range(1, points_per_curve + 1):
                t = i / points_per_curve
                px = cubic_bezier(cx, cx, ax2, ax, t)
                py = cubic_bezier(cy, cy, ay2, ay, t)
                points.append((px, py))
            cx, cy = ax, ay
        elif cmd[0] == 'H':
            cx = cmd[1]
            points.append((cx, cy))
        elif cmd[0] == 'h':
            cx += cmd[1]
            points.append((cx, cy))
        elif cmd[0] == 'V':
            cy = cmd[1]
            points.append((cx, cy))
        elif cmd[0] == 'v':
            cy += cmd[1]
            points.append((cx, cy))
        elif cmd[0] in ('Z', 'z'):
            if abs(cx - start_x) > 0.01 or abs(cy - start_y) > 0.01:
                points.append((start_x, start_y))
            cx, cy = start_x, start_y
    return points


def interpolate_line(x0, y0, x1, y1, num_points=20):
    """Generate points along a line."""
    points = []
    for i in range(num_points + 1):
        t = i / num_points
        points.append((x0 + (x1-x0)*t, y0 + (y1-y0)*t))
    return points


def path_length(points):
    """Total euclidean length of polyline."""
    total = 0
    for i in range(1, len(points)):
        dx = points[i][0] - points[i-1][0]
        dy = points[i][1] - points[i-1][1]
        total += math.sqrt(dx*dx + dy*dy)
    return total


def resample_equidistant(points, step=250.0):
    """
    Resample a polyline so consecutive points are ~step apart.
    This is critical for Sandsara patterns — originals have uniform ~250 step distance.
    """
    if len(points) < 2:
        return points

    result = [points[0]]
    residual = 0.0  # distance accumulated since last emitted point

    for i in range(1, len(points)):
        dx = points[i][0] - points[i-1][0]
        dy = points[i][1] - points[i-1][1]
        seg_len = math.sqrt(dx*dx + dy*dy)

        if seg_len < 1e-6:
            continue  # skip zero-length segments

        # Direction unit vector
        ux, uy = dx / seg_len, dy / seg_len

        consumed = 0.0
        remaining = seg_len

        while True:
            need = step - residual
            if need <= remaining:
                consumed += need
                px = points[i-1][0] + ux * consumed
                py = points[i-1][1] + uy * consumed
                result.append((px, py))
                residual = 0.0
                remaining -= need
            else:
                residual += remaining
                break

    return result


def clamp_to_circle(points, radius=32767):
    """Clamp all points to be within the circle of given radius."""
    result = []
    for x, y in points:
        r = math.sqrt(x*x + y*y)
        if r > radius:
            scale = radius / r
            x *= scale
            y *= scale
        result.append((x, y))
    return result


def remove_close_points(points, min_dist=200.0):
    """Remove points that are too close together (below min_dist)."""
    if len(points) < 2:
        return points
    result = [points[0]]
    for i in range(1, len(points)):
        dx = points[i][0] - result[-1][0]
        dy = points[i][1] - result[-1][1]
        if math.sqrt(dx*dx + dy*dy) >= min_dist:
            result.append(points[i])
    return result


def transform_svg_to_sandsara(points, svg_size=109, scale=0.7):
    """Transform SVG coordinates to Sandsara coordinates."""
    result = []
    center = svg_size / 2
    max_coord = 32767 * scale
    for x, y in points:
        sx = (x - center) / center * max_coord
        sy = -(y - center) / center * max_coord
        result.append((sx, sy))
    return result


if __name__ == "__main__":
    print("This is a library module. Use svg_oviedo_to_sandsara.py or similar.")
