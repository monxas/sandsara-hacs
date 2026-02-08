#!/usr/bin/env python3
"""Convert Real Oviedo SVG crest to Sandsara pattern."""

import xml.etree.ElementTree as ET
import math
from pathlib import Path
from svg_to_sandsara import (
    svg_path_to_points, transform_svg_to_sandsara, write_point, interpolate_line
)

def extract_paths(svg_file):
    """Extract all d attributes from SVG paths, applying group transforms."""
    tree = ET.parse(svg_file)
    root = tree.getroot()
    ns = {'svg': 'http://www.w3.org/2000/svg'}
    
    paths = []
    for path in root.iter('{http://www.w3.org/2000/svg}path'):
        d = path.get('d')
        if d:
            paths.append(d)
    return paths

def apply_translate(points, tx, ty):
    return [(x + tx, y + ty) for x, y in points]

def path_length(points):
    if len(points) < 2:
        return 0
    total = 0
    for i in range(1, len(points)):
        dx = points[i][0] - points[i-1][0]
        dy = points[i][1] - points[i-1][1]
        total += math.sqrt(dx*dx + dy*dy)
    return total

def main():
    svg_file = "/tmp/real-oviedo/Real Oviedo/Real Oviedo_id63BJrk76_1.svg"
    
    # SVG viewBox is "0 0 208 472", but there's a translate(-15.124711,-13.610131) on groups
    # So actual content spans roughly 16-222 in x, 14-486 in y
    # We'll parse paths, apply the group transform, then normalize
    
    paths_d = extract_paths(svg_file)
    print(f"Found {len(paths_d)} paths")
    
    # The SVG has translate(-15.124711,-13.610131) on all groups
    tx, ty = -15.124711, -13.610131
    
    # Parse all paths to points
    all_strokes = []
    for d in paths_d:
        pts = svg_path_to_points(d, points_per_curve=20)
        if len(pts) < 2:
            continue
        # Apply group transform
        pts = apply_translate(pts, tx, ty)
        plen = path_length(pts)
        if plen < 2:  # skip tiny paths
            continue
        all_strokes.append(pts)
    
    print(f"Usable strokes: {len(all_strokes)}")
    
    # Find bounding box of all points
    all_pts = [p for s in all_strokes for p in s]
    min_x = min(p[0] for p in all_pts)
    max_x = max(p[0] for p in all_pts)
    min_y = min(p[1] for p in all_pts)
    max_y = max(p[1] for p in all_pts)
    print(f"Bounding box: x=[{min_x:.1f}, {max_x:.1f}], y=[{min_y:.1f}, {max_y:.1f}]")
    
    # Center and scale to fit in circle
    cx = (min_x + max_x) / 2
    cy = (min_y + max_y) / 2
    width = max_x - min_x
    height = max_y - min_y
    # Scale so the largest dimension maps to ~0.85 of the Sandsara range
    max_dim = max(width, height)
    scale_factor = 32767 * 0.85 * 2 / max_dim  # maps max_dim to 0.85 * diameter
    
    # Transform all strokes: center, flip Y, scale
    transformed_strokes = []
    for stroke in all_strokes:
        t_pts = []
        for x, y in stroke:
            sx = (x - cx) * scale_factor
            sy = -(y - cy) * scale_factor  # flip Y
            t_pts.append((sx, sy))
        transformed_strokes.append(t_pts)
    
    # Build continuous path with retracing between disconnected strokes
    # Use nearest-neighbor ordering to minimize travel
    remaining = list(range(len(transformed_strokes)))
    
    # Start with first stroke
    final_points = list(transformed_strokes[0])
    remaining.remove(0)
    
    while remaining:
        cur = final_points[-1]
        # Find nearest stroke start/end
        best_dist = float('inf')
        best_idx = remaining[0]
        best_reverse = False
        for idx in remaining:
            s = transformed_strokes[idx]
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
        stroke = transformed_strokes[best_idx]
        if best_reverse:
            stroke = stroke[::-1]
        
        # Add transition line from current to stroke start
        transition = interpolate_line(cur[0], cur[1], stroke[0][0], stroke[0][1], 10)
        final_points.extend(transition[1:])
        final_points.extend(stroke)
    
    print(f"Total points: {len(final_points)}")
    
    # Write binary
    output_path = Path(__file__).parent.parent / "research" / "patterns" / "real-oviedo.bin"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    data = bytearray()
    for x, y in final_points:
        data.extend(write_point(x, y))
    
    with open(output_path, "wb") as f:
        f.write(data)
    print(f"Written: {output_path} ({len(data)} bytes)")
    
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
        circle_x = [32767 * 0.85 * math.cos(t) for t in theta]
        circle_y = [32767 * 0.85 * math.sin(t) for t in theta]
        ax.plot(circle_x, circle_y, 'darkred', linewidth=2)
        
        ax.set_aspect('equal')
        ax.set_title(f'Sandsara Pattern ({len(final_points)} points)')
        plt.savefig('/tmp/real-oviedo-pattern.png', dpi=150, bbox_inches='tight')
        print("Saved visualization: /tmp/real-oviedo-pattern.png")
    except ImportError:
        print("matplotlib not available, skipping visualization")

if __name__ == "__main__":
    main()
