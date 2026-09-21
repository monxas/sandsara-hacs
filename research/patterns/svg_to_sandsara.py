#!/usr/bin/env python3
"""
SVG to Sandsara Pattern Converter

Converts SVG files to Sandsara .bin pattern format.
"""

import struct
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def write_pattern(filepath, points):
    """Write points to Sandsara .bin format."""
    with open(filepath, 'wb') as f:
        for x, y in points:
            x = max(-32767, min(32767, int(x)))
            y = max(-32767, min(32767, int(y)))
            f.write(struct.pack('<h', x))
            f.write(b',')
            f.write(struct.pack('<h', y))
            f.write(b'\n')
    print(f"Created {filepath} with {len(points)} points")


def parse_transform(transform_str):
    """Parse SVG transform string into a transformation matrix."""
    if not transform_str:
        return [[1, 0, 0], [0, 1, 0]]  # Identity

    # Start with identity matrix [a, b, c, d, e, f] -> [[a, c, e], [b, d, f]]
    matrix = [[1, 0, 0], [0, 1, 0]]

    # Find all transform operations
    ops = re.findall(r'(\w+)\s*\(([^)]+)\)', transform_str)

    for op, args in ops:
        values = [float(v.strip()) for v in args.replace(',', ' ').split()]

        if op == 'translate':
            tx = values[0]
            ty = values[1] if len(values) > 1 else 0
            m = [[1, 0, tx], [0, 1, ty]]
        elif op == 'rotate':
            angle = math.radians(values[0])
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            m = [[cos_a, -sin_a, 0], [sin_a, cos_a, 0]]
        elif op == 'scale':
            sx = values[0]
            sy = values[1] if len(values) > 1 else sx
            m = [[sx, 0, 0], [0, sy, 0]]
        else:
            continue

        # Multiply matrices
        matrix = multiply_matrices(matrix, m)

    return matrix


def multiply_matrices(m1, m2):
    """Multiply two 2x3 transformation matrices."""
    return [
        [m1[0][0]*m2[0][0] + m1[0][1]*m2[1][0],
         m1[0][0]*m2[0][1] + m1[0][1]*m2[1][1],
         m1[0][0]*m2[0][2] + m1[0][1]*m2[1][2] + m1[0][2]],
        [m1[1][0]*m2[0][0] + m1[1][1]*m2[1][0],
         m1[1][0]*m2[0][1] + m1[1][1]*m2[1][1],
         m1[1][0]*m2[0][2] + m1[1][1]*m2[1][2] + m1[1][2]]
    ]


def apply_transform(point, matrix):
    """Apply transformation matrix to a point."""
    x, y = point
    new_x = matrix[0][0] * x + matrix[0][1] * y + matrix[0][2]
    new_y = matrix[1][0] * x + matrix[1][1] * y + matrix[1][2]
    return (new_x, new_y)


def sample_circle(cx, cy, r, num_points=50):
    """Sample points along a circle."""
    points = []
    for i in range(num_points + 1):
        angle = (i / num_points) * 2 * math.pi
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        points.append((x, y))
    return points


def sample_line(x1, y1, x2, y2, num_points=10):
    """Sample points along a line."""
    points = []
    for i in range(num_points + 1):
        t = i / num_points
        x = x1 + (x2 - x1) * t
        y = y1 + (y2 - y1) * t
        points.append((x, y))
    return points


def parse_path_d(d):
    """Parse SVG path d attribute into points."""
    points = []

    # Tokenize the path
    tokens = re.findall(r'([MmLlHhVvCcSsQqTtAaZz])|(-?\d*\.?\d+)', d)
    tokens = [t[0] or t[1] for t in tokens if t[0] or t[1]]

    i = 0
    current_x, current_y = 0, 0
    start_x, start_y = 0, 0
    last_command = None

    while i < len(tokens):
        token = tokens[i]

        if token.isalpha():
            command = token
            i += 1
        else:
            command = last_command

        if command in 'Mm':
            x = float(tokens[i])
            y = float(tokens[i + 1])
            i += 2
            if command == 'm':
                current_x += x
                current_y += y
            else:
                current_x, current_y = x, y
            start_x, start_y = current_x, current_y
            points.append((current_x, current_y))
            last_command = 'L' if command == 'M' else 'l'

        elif command in 'Ll':
            x = float(tokens[i])
            y = float(tokens[i + 1])
            i += 2
            if command == 'l':
                x += current_x
                y += current_y
            # Sample line
            for pt in sample_line(current_x, current_y, x, y, 5)[1:]:
                points.append(pt)
            current_x, current_y = x, y
            last_command = command

        elif command == 'H':
            x = float(tokens[i])
            i += 1
            for pt in sample_line(current_x, current_y, x, current_y, 5)[1:]:
                points.append(pt)
            current_x = x
            last_command = command

        elif command == 'h':
            dx = float(tokens[i])
            i += 1
            x = current_x + dx
            for pt in sample_line(current_x, current_y, x, current_y, 5)[1:]:
                points.append(pt)
            current_x = x
            last_command = command

        elif command == 'V':
            y = float(tokens[i])
            i += 1
            for pt in sample_line(current_x, current_y, current_x, y, 5)[1:]:
                points.append(pt)
            current_y = y
            last_command = command

        elif command == 'v':
            dy = float(tokens[i])
            i += 1
            y = current_y + dy
            for pt in sample_line(current_x, current_y, current_x, y, 5)[1:]:
                points.append(pt)
            current_y = y
            last_command = command

        elif command in 'Cc':
            # Cubic bezier
            x1 = float(tokens[i])
            y1 = float(tokens[i + 1])
            x2 = float(tokens[i + 2])
            y2 = float(tokens[i + 3])
            x = float(tokens[i + 4])
            y = float(tokens[i + 5])
            i += 6

            if command == 'c':
                x1 += current_x
                y1 += current_y
                x2 += current_x
                y2 += current_y
                x += current_x
                y += current_y

            # Sample cubic bezier
            for j in range(1, 21):
                t = j / 20
                px = (1-t)**3 * current_x + 3*(1-t)**2*t * x1 + 3*(1-t)*t**2 * x2 + t**3 * x
                py = (1-t)**3 * current_y + 3*(1-t)**2*t * y1 + 3*(1-t)*t**2 * y2 + t**3 * y
                points.append((px, py))

            current_x, current_y = x, y
            last_command = command

        elif command in 'Zz':
            # Close path
            for pt in sample_line(current_x, current_y, start_x, start_y, 5)[1:]:
                points.append(pt)
            current_x, current_y = start_x, start_y
            last_command = command

        else:
            # Skip unknown commands
            i += 1

    return points


def extract_shapes(element, parent_transform=None):
    """Recursively extract shapes from SVG element."""
    shapes = []

    if parent_transform is None:
        parent_transform = [[1, 0, 0], [0, 1, 0]]

    # Get this element's transform
    transform_str = element.get('transform', '')
    local_transform = parse_transform(transform_str)
    current_transform = multiply_matrices(parent_transform, local_transform)

    # Extract shapes based on element type
    tag = element.tag.split('}')[-1]  # Remove namespace

    if tag == 'circle':
        cx = float(element.get('cx', 0))
        cy = float(element.get('cy', 0))
        r = float(element.get('r', 0))
        points = sample_circle(cx, cy, r, 40)
        transformed = [apply_transform(p, current_transform) for p in points]
        shapes.append(('circle', transformed))

    elif tag == 'line':
        x1 = float(element.get('x1', 0))
        y1 = float(element.get('y1', 0))
        x2 = float(element.get('x2', 0))
        y2 = float(element.get('y2', 0))
        points = sample_line(x1, y1, x2, y2, 10)
        transformed = [apply_transform(p, current_transform) for p in points]
        shapes.append(('line', transformed))

    elif tag == 'path':
        d = element.get('d', '')
        if d:
            points = parse_path_d(d)
            transformed = [apply_transform(p, current_transform) for p in points]
            shapes.append(('path', transformed))

    elif tag == 'rect':
        x = float(element.get('x', 0))
        y = float(element.get('y', 0))
        w = float(element.get('width', 0))
        h = float(element.get('height', 0))
        points = [(x, y), (x+w, y), (x+w, y+h), (x, y+h), (x, y)]
        transformed = [apply_transform(p, current_transform) for p in points]
        shapes.append(('rect', transformed))

    # Recurse into children
    for child in element:
        shapes.extend(extract_shapes(child, current_transform))

    return shapes


def connect_shapes(shapes):
    """Connect multiple shapes into one continuous path."""
    if not shapes:
        return []

    all_points = []

    for i, (shape_type, points) in enumerate(shapes):
        if not points:
            continue

        if all_points:
            # Add travel line from last point to first point of new shape
            last = all_points[-1]
            first = points[0]
            travel = sample_line(last[0], last[1], first[0], first[1], 5)
            all_points.extend(travel[1:])

        all_points.extend(points)

    return all_points


def svg_to_sandsara(svg_content, output_path, scale=800):
    """Convert SVG content to Sandsara pattern."""
    # Parse SVG
    root = ET.fromstring(svg_content)

    # Get viewBox or width/height for scaling
    viewbox = root.get('viewBox')
    if viewbox:
        parts = viewbox.split()
        svg_width = float(parts[2])
        svg_height = float(parts[3])
    else:
        svg_width = float(root.get('width', 100))
        svg_height = float(root.get('height', 100))

    # Extract all shapes
    shapes = extract_shapes(root)
    print(f"Found {len(shapes)} shapes")

    # Connect shapes into one path
    points = connect_shapes(shapes)
    print(f"Total points before scaling: {len(points)}")

    if not points:
        print("No points extracted!")
        return

    # Find bounds
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    # Center and scale
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    width = max_x - min_x
    height = max_y - min_y
    max_dim = max(width, height)

    if max_dim == 0:
        max_dim = 1

    scaled_points = []
    for x, y in points:
        # Center
        x -= center_x
        y -= center_y
        # Scale to Sandsara coordinates
        x = x / max_dim * scale * 2 * 25
        y = -y / max_dim * scale * 2 * 25  # Flip Y
        scaled_points.append((x, y))

    # Write pattern
    write_pattern(output_path, scaled_points)
    return scaled_points


# Test with the weather SVG
if __name__ == '__main__':
    svg_content = '''<svg xmlns="http://www.w3.org/2000/svg" width="56" height="48" version="1.1">
  <defs>
    <filter id="blur" x="-.20655" y="-.28472" width="1.403" height="1.6944">
      <feGaussianBlur in="SourceAlpha" stdDeviation="3"/>
      <feOffset dx="0" dy="4" result="offsetblur"/>
      <feComponentTransfer>
        <feFuncA slope="0.05" type="linear"/>
      </feComponentTransfer>
      <feMerge>
        <feMergeNode/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  <g transform="translate(16,-2)" filter="url(#blur)">
    <g class="am-weather-sun" transform="translate(0,16)">
      <line transform="translate(0,9)" y2="3" fill="none" stroke="#ffa500" stroke-linecap="round" stroke-width="2"/>
      <g transform="rotate(45)">
        <line transform="translate(0,9)" y2="3" fill="none" stroke="#ffa500" stroke-linecap="round" stroke-width="2"/>
      </g>
      <g transform="rotate(90)">
        <line transform="translate(0,9)" y2="3" fill="none" stroke="#ffa500" stroke-linecap="round" stroke-width="2"/>
      </g>
      <g transform="rotate(135)">
        <line transform="translate(0,9)" y2="3" fill="none" stroke="#ffa500" stroke-linecap="round" stroke-width="2"/>
      </g>
      <g transform="scale(-1)">
        <line transform="translate(0,9)" y2="3" fill="none" stroke="#ffa500" stroke-linecap="round" stroke-width="2"/>
      </g>
      <g transform="rotate(225)">
        <line transform="translate(0,9)" y2="3" fill="none" stroke="#ffa500" stroke-linecap="round" stroke-width="2"/>
      </g>
      <g transform="rotate(-90)">
        <line transform="translate(0,9)" y2="3" fill="none" stroke="#ffa500" stroke-linecap="round" stroke-width="2"/>
      </g>
      <g transform="rotate(-45)">
        <line transform="translate(0,9)" y2="3" fill="none" stroke="#ffa500" stroke-linecap="round" stroke-width="2"/>
      </g>
      <circle r="5" fill="#ffa500" stroke="#ffa500" stroke-width="2"/>
    </g>
    <g class="am-weather-cloud-3">
      <path transform="translate(-20,-11)" d="m47.7 35.4c0-4.6-3.7-8.2-8.2-8.2-1 0-1.9 0.2-2.8 0.5-0.3-3.4-3.1-6.2-6.6-6.2-3.7 0-6.7 3-6.7 6.7 0 0.8 0.2 1.6 0.4 2.3-0.3-0.1-0.7-0.1-1-0.1-3.7 0-6.7 3-6.7 6.7 0 3.6 2.9 6.6 6.5 6.7h17.2c4.4-0.5 7.9-4 7.9-8.4z" fill="#57a0ee" stroke="#fff" stroke-linejoin="round" stroke-width="1.2"/>
    </g>
  </g>
</svg>'''

    output_dir = Path(__file__).parent / 'samples'
    output_dir.mkdir(exist_ok=True)

    svg_to_sandsara(svg_content, output_dir / 'svg-weather-icon.bin')
