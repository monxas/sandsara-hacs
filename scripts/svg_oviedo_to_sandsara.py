#!/usr/bin/env python3
"""
Convert Real Oviedo SVG crest to Sandsara pattern.

Key requirements from analyzing 100 original patterns:
- Uniform step distance ~250 between consecutive points (range 217-285)
- Use full disk radius (max_r ≈ 32767)
- All points within circle: sqrt(x²+y²) <= 32767
- No duplicate points or huge jumps
"""

import xml.etree.ElementTree as ET
import math
from pathlib import Path
from svg_to_sandsara import (
    svg_path_to_points, write_point, interpolate_line,
    path_length, resample_equidistant, clamp_to_circle, remove_close_points
)

TARGET_STEP = 250  # Match original patterns
MAX_RADIUS = 32767
SCALE_FACTOR = 1.0  # Use full disk - clamp_to_circle handles overflow


def extract_paths(svg_file):
    """Extract all d attributes from SVG paths."""
    tree = ET.parse(svg_file)
    root = tree.getroot()
    paths = []
    for path in root.iter('{http://www.w3.org/2000/svg}path'):
        d = path.get('d')
        if d:
            paths.append(d)
    return paths


def transform_to_sandsara(strokes, scale_pct=SCALE_FACTOR):
    """
    Center, scale and flip Y for all strokes.
    Scale to use scale_pct of the full disk radius.
    """
    # Find bounding box
    all_pts = [p for s in strokes for p in s]
    min_x = min(p[0] for p in all_pts)
    max_x = max(p[0] for p in all_pts)
    min_y = min(p[1] for p in all_pts)
    max_y = max(p[1] for p in all_pts)

    cx = (min_x + max_x) / 2
    cy = (min_y + max_y) / 2
    width = max_x - min_x
    height = max_y - min_y

    # Scale so the design fits within the circle
    # For a circular constraint, we need the diagonal to fit
    # But the shield is tall/narrow, so scale by max dimension
    max_dim = max(width, height)
    scale = MAX_RADIUS * scale_pct * 2 / max_dim

    result = []
    for stroke in strokes:
        t_pts = []
        for x, y in stroke:
            sx = (x - cx) * scale
            sy = -(y - cy) * scale  # flip Y (SVG Y-down → Sandsara Y-up)
            t_pts.append((sx, sy))
        result.append(t_pts)
    return result


def order_strokes_nearest(strokes):
    """
    Order strokes by nearest-neighbor to minimize travel between them.
    Each stroke can be reversed if its end is closer.
    """
    if not strokes:
        return []

    remaining = list(range(len(strokes)))
    ordered = [strokes[0]]
    remaining.remove(0)

    while remaining:
        cur = ordered[-1][-1]  # last point of last stroke
        best_dist = float('inf')
        best_idx = remaining[0]
        best_reverse = False

        for idx in remaining:
            s = strokes[idx]
            d_start = (s[0][0]-cur[0])**2 + (s[0][1]-cur[1])**2
            d_end = (s[-1][0]-cur[0])**2 + (s[-1][1]-cur[1])**2
            if d_start < best_dist:
                best_dist = d_start
                best_idx = idx
                best_reverse = False
            if d_end < best_dist:
                best_dist = d_end
                best_idx = idx
                best_reverse = True

        remaining.remove(best_idx)
        stroke = strokes[best_idx]
        if best_reverse:
            stroke = stroke[::-1]
        ordered.append(stroke)

    return ordered


def build_continuous_path(strokes):
    """
    Build a single continuous path from ordered strokes.
    Inserts straight-line transitions between disconnected strokes.
    """
    if not strokes:
        return []

    path = list(strokes[0])

    for i in range(1, len(strokes)):
        cur = path[-1]
        target = strokes[i][0]
        # Direct line transition (will be resampled later)
        path.append(target)
        path.extend(strokes[i][1:])

    return path


def main():
    svg_file = "/tmp/real-oviedo/Real Oviedo/Real Oviedo_id63BJrk76_1.svg"

    if not Path(svg_file).exists():
        print(f"SVG not found: {svg_file}")
        print("Searching for alternative...")
        import glob
        candidates = glob.glob("/tmp/real-oviedo/**/*.svg", recursive=True)
        if candidates:
            svg_file = candidates[0]
            print(f"Found: {svg_file}")
        else:
            print("No SVG found. Exiting.")
            return

    # Parse SVG paths
    paths_d = extract_paths(svg_file)
    print(f"Found {len(paths_d)} paths")

    # The SVG has translate(-15.124711,-13.610131) on groups
    tx, ty = -15.124711, -13.610131

    # Parse all paths with high resolution for bezier curves
    all_strokes = []
    for d in paths_d:
        pts = svg_path_to_points(d, points_per_curve=40)
        if len(pts) < 2:
            continue
        # Apply group transform
        pts = [(x + tx, y + ty) for x, y in pts]
        plen = path_length(pts)
        if plen < 2:
            continue
        all_strokes.append(pts)

    print(f"Usable strokes: {len(all_strokes)}")

    # Transform to Sandsara coordinate space
    transformed = transform_to_sandsara(all_strokes)

    # Order strokes to minimize travel
    ordered = order_strokes_nearest(transformed)

    # Build continuous path
    raw_path = build_continuous_path(ordered)
    print(f"Raw path points: {len(raw_path)}")

    # CRITICAL: Resample to uniform step distance
    resampled = resample_equidistant(raw_path, step=TARGET_STEP)
    print(f"Resampled points: {len(resampled)} (step={TARGET_STEP})")

    # Clamp to circle and remove points that got too close from clamping
    clamped = clamp_to_circle(resampled, MAX_RADIUS)
    final_points = remove_close_points(clamped, min_dist=200.0)

    # Verify stats
    if len(final_points) >= 2:
        steps = [math.sqrt((final_points[i][0]-final_points[i-1][0])**2 +
                           (final_points[i][1]-final_points[i-1][1])**2)
                 for i in range(1, len(final_points))]
        max_r = max(math.sqrt(x*x+y*y) for x,y in final_points)
        print(f"\nStats:")
        print(f"  Points: {len(final_points)}")
        print(f"  Step: avg={sum(steps)/len(steps):.1f} min={min(steps):.1f} max={max(steps):.1f}")
        print(f"  Max radius: {max_r:.0f}")
        print(f"  X range: [{min(x for x,_ in final_points):.0f}, {max(x for x,_ in final_points):.0f}]")
        print(f"  Y range: [{min(y for _,y in final_points):.0f}, {max(y for _,y in final_points):.0f}]")

    # Write binary
    output_path = Path(__file__).parent.parent / "research" / "patterns" / "real-oviedo.bin"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = bytearray()
    for x, y in final_points:
        data.extend(write_point(x, y))

    with open(output_path, "wb") as f:
        f.write(data)
    print(f"\nWritten: {output_path} ({len(data)} bytes, {len(final_points)} points)")

    # Also copy to HA location
    ha_path = Path("/tmp/real-oviedo-v2.bin")
    with open(ha_path, "wb") as f:
        f.write(data)
    print(f"Also saved: {ha_path}")

    # Visualize
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        xs = [p[0] for p in final_points]
        ys = [p[1] for p in final_points]

        fig, ax = plt.subplots(1, 1, figsize=(10, 10))
        ax.set_facecolor('#c4a882')
        fig.patch.set_facecolor('#c4a882')

        ax.plot(xs, ys, color='#8b6914', linewidth=0.3, alpha=0.8)

        # Draw circle boundary
        theta = [i * 2 * math.pi / 200 for i in range(201)]
        circle_x = [MAX_RADIUS * math.cos(t) for t in theta]
        circle_y = [MAX_RADIUS * math.sin(t) for t in theta]
        ax.plot(circle_x, circle_y, 'darkred', linewidth=2, alpha=0.5)

        ax.set_aspect('equal')
        ax.set_title(f'Real Oviedo - Sandsara ({len(final_points)} pts, step={TARGET_STEP})')
        plt.savefig('/tmp/real-oviedo-pattern-v2.png', dpi=150, bbox_inches='tight')
        print("Saved visualization: /tmp/real-oviedo-pattern-v2.png")
    except ImportError:
        print("matplotlib not available, skipping visualization")


if __name__ == "__main__":
    main()
