#!/usr/bin/env python3
"""
Generate Sandsara pattern for kanji 栄 (prosperity) from KanjiVG SVG.

- Parses the official SVG strokes
- Samples curves densely
- Builds a continuous path with retracing (no jumps)
- Resamples to a smooth ~6000 points
- Transforms to Sandsara coordinates (centered, scaled, Y up)
- Writes binary CSV format: int16 LE, ',', int16 LE, '\n'
"""

import math
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

SVG_PATH = Path("/tmp/kanji-ei.svg")
OUTPUT_PATH = Path("/root/clawd/sandsara-hacs/research/patterns/kanji-ei-codex.bin")

# Output density + scaling
TARGET_POINTS = 6000
SCALE = 0.78  # use 78% of max radius

# Sampling parameters (SVG units)
CURVE_DENSITY = 6.0   # points per SVG unit (approx length)
LINE_DENSITY = 4.0
MIN_CURVE_POINTS = 50
MIN_LINE_POINTS = 20
TRANSITION_DENSITY = 5.0
MIN_TRANSITION_POINTS = 15


def tokenize_path(d):
    return re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?[0-9]*\.?[0-9]+", d)


def parse_svg_path(d):
    """Parse SVG path data into command tuples."""
    tokens = tokenize_path(d)
    commands = []
    i = 0
    current_cmd = None

    while i < len(tokens):
        token = tokens[i]
        if token.isalpha():
            current_cmd = token
            i += 1
            continue

        if current_cmd in ("M", "m"):
            x, y = float(tokens[i]), float(tokens[i + 1])
            commands.append((current_cmd, x, y))
            i += 2
            # Subsequent pairs are implicit lineto
            current_cmd = "L" if current_cmd == "M" else "l"
        elif current_cmd in ("L", "l"):
            x, y = float(tokens[i]), float(tokens[i + 1])
            commands.append((current_cmd, x, y))
            i += 2
        elif current_cmd in ("C", "c"):
            x1, y1 = float(tokens[i]), float(tokens[i + 1])
            x2, y2 = float(tokens[i + 2]), float(tokens[i + 3])
            x, y = float(tokens[i + 4]), float(tokens[i + 5])
            commands.append((current_cmd, x1, y1, x2, y2, x, y))
            i += 6
        elif current_cmd in ("Q", "q"):
            x1, y1 = float(tokens[i]), float(tokens[i + 1])
            x, y = float(tokens[i + 2]), float(tokens[i + 3])
            commands.append((current_cmd, x1, y1, x, y))
            i += 4
        elif current_cmd in ("H", "h"):
            x = float(tokens[i])
            commands.append((current_cmd, x))
            i += 1
        elif current_cmd in ("V", "v"):
            y = float(tokens[i])
            commands.append((current_cmd, y))
            i += 1
        else:
            # Unsupported command - skip safely
            i += 1

    return commands


def dist(p0, p1):
    return math.hypot(p1[0] - p0[0], p1[1] - p0[1])


def cubic_bezier(p0, p1, p2, p3, t):
    mt = 1 - t
    return (
        mt ** 3 * p0[0] + 3 * mt ** 2 * t * p1[0] + 3 * mt * t ** 2 * p2[0] + t ** 3 * p3[0],
        mt ** 3 * p0[1] + 3 * mt ** 2 * t * p1[1] + 3 * mt * t ** 2 * p2[1] + t ** 3 * p3[1],
    )


def quadratic_bezier(p0, p1, p2, t):
    mt = 1 - t
    return (
        mt ** 2 * p0[0] + 2 * mt * t * p1[0] + t ** 2 * p2[0],
        mt ** 2 * p0[1] + 2 * mt * t * p1[1] + t ** 2 * p2[1],
    )


def estimate_curve_length(points):
    if len(points) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(points)):
        total += dist(points[i - 1], points[i])
    return total


def sample_cubic(p0, p1, p2, p3):
    # Estimate length with 10 segments
    probe = [cubic_bezier(p0, p1, p2, p3, i / 10.0) for i in range(11)]
    length = estimate_curve_length(probe)
    num_points = max(int(length * CURVE_DENSITY), MIN_CURVE_POINTS)
    return [cubic_bezier(p0, p1, p2, p3, i / (num_points - 1)) for i in range(num_points)]


def sample_quadratic(p0, p1, p2):
    probe = [quadratic_bezier(p0, p1, p2, i / 10.0) for i in range(11)]
    length = estimate_curve_length(probe)
    num_points = max(int(length * CURVE_DENSITY), MIN_CURVE_POINTS)
    return [quadratic_bezier(p0, p1, p2, i / (num_points - 1)) for i in range(num_points)]


def sample_line(p0, p1, density=LINE_DENSITY, min_points=MIN_LINE_POINTS):
    length = dist(p0, p1)
    if length < 1e-9:
        return [p0]
    num_points = max(int(length * density), min_points)
    return [
        (
            p0[0] + (p1[0] - p0[0]) * (i / (num_points - 1)),
            p0[1] + (p1[1] - p0[1]) * (i / (num_points - 1)),
        )
        for i in range(num_points)
    ]


def svg_path_to_points(d):
    """Convert an SVG path to a list of points (SVG coords)."""
    commands = parse_svg_path(d)
    points = []

    cx, cy = 0.0, 0.0

    for cmd in commands:
        op = cmd[0]
        if op == "M":
            cx, cy = cmd[1], cmd[2]
            points.append((cx, cy))
        elif op == "m":
            cx += cmd[1]
            cy += cmd[2]
            points.append((cx, cy))
        elif op == "L":
            x, y = cmd[1], cmd[2]
            seg = sample_line((cx, cy), (x, y))
            points.extend(seg[1:])
            cx, cy = x, y
        elif op == "l":
            x, y = cx + cmd[1], cy + cmd[2]
            seg = sample_line((cx, cy), (x, y))
            points.extend(seg[1:])
            cx, cy = x, y
        elif op == "H":
            x = cmd[1]
            seg = sample_line((cx, cy), (x, cy))
            points.extend(seg[1:])
            cx = x
        elif op == "h":
            x = cx + cmd[1]
            seg = sample_line((cx, cy), (x, cy))
            points.extend(seg[1:])
            cx = x
        elif op == "V":
            y = cmd[1]
            seg = sample_line((cx, cy), (cx, y))
            points.extend(seg[1:])
            cy = y
        elif op == "v":
            y = cy + cmd[1]
            seg = sample_line((cx, cy), (cx, y))
            points.extend(seg[1:])
            cy = y
        elif op == "C":
            x1, y1, x2, y2, x, y = cmd[1:]
            seg = sample_cubic((cx, cy), (x1, y1), (x2, y2), (x, y))
            points.extend(seg[1:])
            cx, cy = x, y
        elif op == "c":
            x1, y1, x2, y2, x, y = cmd[1:]
            seg = sample_cubic(
                (cx, cy),
                (cx + x1, cy + y1),
                (cx + x2, cy + y2),
                (cx + x, cy + y),
            )
            points.extend(seg[1:])
            cx, cy = cx + x, cy + y
        elif op == "Q":
            x1, y1, x, y = cmd[1:]
            seg = sample_quadratic((cx, cy), (x1, y1), (x, y))
            points.extend(seg[1:])
            cx, cy = x, y
        elif op == "q":
            x1, y1, x, y = cmd[1:]
            seg = sample_quadratic((cx, cy), (cx + x1, cy + y1), (cx + x, cy + y))
            points.extend(seg[1:])
            cx, cy = cx + x, cy + y

    return points


def find_closest_point_index(points, target):
    """Find index of closest point in a list to target."""
    min_dist = float("inf")
    min_idx = 0
    tx, ty = target
    for i, (x, y) in enumerate(points):
        d = (x - tx) ** 2 + (y - ty) ** 2
        if d < min_dist:
            min_dist = d
            min_idx = i
    return min_idx


def choose_orientation(stroke_points, drawn_points):
    """Choose stroke direction (forward or reversed) that minimizes distance to drawn path."""
    if not drawn_points or len(stroke_points) < 2:
        return stroke_points

    start = stroke_points[0]
    end = stroke_points[-1]

    start_idx = find_closest_point_index(drawn_points, start)
    end_idx = find_closest_point_index(drawn_points, end)

    ds = dist(drawn_points[start_idx], start)
    de = dist(drawn_points[end_idx], end)

    if de < ds:
        return list(reversed(stroke_points))
    return stroke_points


def build_continuous_path(stroke_points_list):
    """Build continuous path with retracing between strokes."""
    final_points = []

    for stroke in stroke_points_list:
        if not stroke:
            continue

        if not final_points:
            final_points.extend(stroke)
            continue

        # Choose best orientation (minimize distance to existing path)
        stroke = choose_orientation(stroke, final_points)
        target = stroke[0]

        # Retrace along existing path to closest point to target
        target_idx = find_closest_point_index(final_points, target)
        retrace = final_points[target_idx:][::-1]
        if retrace:
            final_points.extend(retrace[1:])  # skip duplicate current point

        # Transition to target (short visible line)
        last = final_points[-1]
        if dist(last, target) > 1e-6:
            transition = sample_line(last, target, density=TRANSITION_DENSITY, min_points=MIN_TRANSITION_POINTS)
            final_points.extend(transition[1:])

        # Draw the stroke
        if dist(final_points[-1], stroke[0]) < 1e-6:
            final_points.extend(stroke[1:])
        else:
            final_points.extend(stroke)

    return final_points


def resample_path(points, target_count):
    """Resample polyline to a fixed number of points (uniform distance)."""
    if len(points) < 2 or target_count <= 2:
        return points

    # cumulative distances
    cum = [0.0]
    for i in range(1, len(points)):
        cum.append(cum[-1] + dist(points[i - 1], points[i]))

    total_length = cum[-1]
    if total_length == 0:
        return points

    step = total_length / (target_count - 1)
    new_points = [points[0]]
    j = 1

    for k in range(1, target_count - 1):
        d = step * k
        while j < len(cum) - 1 and cum[j] < d:
            j += 1
        # interpolate between j-1 and j
        d0, d1 = cum[j - 1], cum[j]
        if d1 == d0:
            t = 0.0
        else:
            t = (d - d0) / (d1 - d0)
        x0, y0 = points[j - 1]
        x1, y1 = points[j]
        new_points.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))

    new_points.append(points[-1])
    return new_points


def compute_bbox(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), max(xs), min(ys), max(ys)


def transform_to_sandsara(points, bbox, scale=SCALE):
    minx, maxx, miny, maxy = bbox
    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0
    width = maxx - minx
    height = maxy - miny
    max_dim = max(width, height)

    if max_dim == 0:
        return [(0, 0) for _ in points]

    scale_factor = (32767 * scale) / (max_dim / 2.0)

    transformed = []
    for x, y in points:
        sx = (x - cx) * scale_factor
        sy = -(y - cy) * scale_factor  # flip Y
        # clamp to int16 range
        ix = max(-32767, min(32767, int(round(sx))))
        iy = max(-32767, min(32767, int(round(sy))))
        transformed.append((ix, iy))

    return transformed


def write_sandsara(points, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "wb") as f:
        for x, y in points:
            f.write(struct.pack("<h", x))
            f.write(b",")
            f.write(struct.pack("<h", y))
            f.write(b"\n")


def extract_svg_strokes(svg_path):
    tree = ET.parse(svg_path)
    root = tree.getroot()

    # SVG namespace handling
    ns = {"svg": "http://www.w3.org/2000/svg"}
    paths = root.findall(".//svg:path", ns)

    strokes = []
    for p in paths:
        d = p.attrib.get("d")
        if d:
            strokes.append(d)
    return strokes


def main():
    if not SVG_PATH.exists():
        raise FileNotFoundError(f"SVG not found: {SVG_PATH}")

    # Extract strokes from SVG
    strokes = extract_svg_strokes(SVG_PATH)
    if not strokes:
        raise RuntimeError("No stroke paths found in SVG")

    # Convert each stroke to points (SVG coordinates)
    stroke_points_list = [svg_path_to_points(d) for d in strokes]

    # Compute bbox from stroke points only (exclude transitions)
    all_stroke_points = [p for stroke in stroke_points_list for p in stroke]
    bbox = compute_bbox(all_stroke_points)

    # Build continuous path with retracing
    raw_path = build_continuous_path(stroke_points_list)

    # Resample to target count for smoothness
    smooth_path = resample_path(raw_path, TARGET_POINTS)

    # Transform to Sandsara coordinate system
    sandsara_points = transform_to_sandsara(smooth_path, bbox)

    # Write output
    write_sandsara(sandsara_points, OUTPUT_PATH)

    # Basic stats
    xs = [p[0] for p in sandsara_points]
    ys = [p[1] for p in sandsara_points]
    print(f"Created: {OUTPUT_PATH}")
    print(f"Total points: {len(sandsara_points)}")
    print(f"X range: {min(xs)} .. {max(xs)}")
    print(f"Y range: {min(ys)} .. {max(ys)}")
    print(f"File size: {OUTPUT_PATH.stat().st_size} bytes")

    # Print first 3 points (hex)
    with open(OUTPUT_PATH, "rb") as f:
        print("First 3 points (hex):")
        for i in range(3):
            chunk = f.read(6)
            if len(chunk) == 6:
                print(f"  {i}: {chunk.hex()}")


if __name__ == "__main__":
    main()
