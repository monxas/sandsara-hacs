#!/usr/bin/env python3
"""
SVG to Sandsara .bin pattern converter (polar coordinates).

Sandsara binary format: 6 bytes per point, big-endian uint16:
  - Bytes 0-1: Theta (angle), 0-65535 maps to 0-360°
  - Bytes 2-3: Rho (radius), format 0x2Cxx where xx = 0-255
  - Bytes 4-5: Counter, sequential (idx % 256) * 256 + 10

Usage:
    python svg_to_sandsara_polar.py input.svg output.bin [--visualize out.png] [--max-points N] [--simplify]
"""

import argparse
import math
import struct
import sys
from xml.etree import ElementTree as ET

import numpy as np

try:
    from svgpathtools import parse_path
except ImportError:
    print("pip install svgpathtools")
    sys.exit(1)


def extract_paths_from_svg(svg_path):
    """Extract all path 'd' attributes from SVG, applying group transforms."""
    tree = ET.parse(svg_path)
    root = tree.getroot()
    ns = {'svg': 'http://www.w3.org/2000/svg'}
    
    paths_d = []
    # Find all path elements
    for path_el in root.iter('{http://www.w3.org/2000/svg}path'):
        d = path_el.get('d')
        if d:
            paths_d.append(d)
    return paths_d


def path_to_points(d_string, num_samples_per_unit=0.5):
    """Convert SVG path d-string to list of (x, y) points."""
    path = parse_path(d_string)
    points = []
    for segment in path:
        length = segment.length()
        n_samples = max(2, int(length * num_samples_per_unit))
        for i in range(n_samples):
            t = i / (n_samples - 1) if n_samples > 1 else 0
            pt = segment.point(t)
            points.append((pt.real, pt.imag))
    return points


def simplify_path_rdp(points, epsilon=1.0):
    """Ramer-Douglas-Peucker simplification."""
    if len(points) < 3:
        return points
    
    pts = np.array(points)
    # Find point furthest from line between first and last
    start, end = pts[0], pts[-1]
    line_vec = end - start
    line_len = np.linalg.norm(line_vec)
    
    if line_len < 1e-10:
        dists = np.linalg.norm(pts - start, axis=1)
    else:
        line_unit = line_vec / line_len
        proj = np.dot(pts - start, line_unit)
        proj_pts = start + np.outer(proj, line_unit)
        dists = np.linalg.norm(pts - proj_pts, axis=1)
    
    max_idx = np.argmax(dists)
    max_dist = dists[max_idx]
    
    if max_dist > epsilon:
        left = simplify_path_rdp(points[:max_idx + 1], epsilon)
        right = simplify_path_rdp(points[max_idx:], epsilon)
        return left[:-1] + right
    else:
        return [points[0], points[-1]]


def connect_paths(path_groups):
    """Connect disconnected path groups with straight lines (nearest endpoint)."""
    if not path_groups:
        return []
    
    connected = list(path_groups[0])
    remaining = list(path_groups[1:])
    
    while remaining:
        last_pt = np.array(connected[-1])
        best_idx = 0
        best_dist = float('inf')
        best_reverse = False
        
        for i, group in enumerate(remaining):
            if not group:
                continue
            d_start = np.linalg.norm(last_pt - np.array(group[0]))
            d_end = np.linalg.norm(last_pt - np.array(group[-1]))
            if d_start < best_dist:
                best_dist = d_start
                best_idx = i
                best_reverse = False
            if d_end < best_dist:
                best_dist = d_end
                best_idx = i
                best_reverse = True
        
        group = remaining.pop(best_idx)
        if best_reverse:
            group = list(reversed(group))
        connected.extend(group)
    
    return connected


def xy_to_polar_sandsara(points, max_rho=240):
    """Convert XY points to Sandsara polar format.
    
    Centers and scales points to fit in a circle, then converts to polar.
    Returns list of (theta_u16, rho_byte) tuples.
    """
    pts = np.array(points)
    
    # Center
    cx = (pts[:, 0].min() + pts[:, 0].max()) / 2
    cy = (pts[:, 1].min() + pts[:, 1].max()) / 2
    pts[:, 0] -= cx
    pts[:, 1] -= cy
    
    # Scale to fit in circle of radius max_rho
    max_r = np.max(np.sqrt(pts[:, 0]**2 + pts[:, 1]**2))
    if max_r > 0:
        pts *= max_rho / max_r
    
    result = []
    for x, y in pts:
        theta = math.atan2(y, x)  # -pi to pi
        if theta < 0:
            theta += 2 * math.pi
        theta_u16 = int(theta / (2 * math.pi) * 65535) & 0xFFFF
        
        rho = math.sqrt(x * x + y * y)
        rho_byte = min(255, max(0, int(rho)))
        
        result.append((theta_u16, rho_byte))
    
    return result


def write_sandsara_bin(polar_points, output_path):
    """Write Sandsara .bin file."""
    with open(output_path, 'wb') as f:
        for i, (theta, rho_byte) in enumerate(polar_points):
            rho_word = 0x2C00 | rho_byte
            counter = ((i % 256) << 8) | 0x0A
            f.write(struct.pack('>HHH', theta, rho_word, counter))
    print(f"Wrote {len(polar_points)} points ({len(polar_points)*6} bytes) to {output_path}")


def visualize(polar_points, output_path):
    """Visualize the pattern by converting back to cartesian."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    
    xs, ys = [], []
    for theta_u16, rho_byte in polar_points:
        theta = theta_u16 / 65535.0 * 2 * math.pi
        x = rho_byte * math.cos(theta)
        y = rho_byte * math.sin(theta)
        xs.append(x)
        ys.append(y)
    
    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.set_aspect('equal')
    ax.set_facecolor('tan')
    
    # Draw the path
    ax.plot(xs, ys, 'k-', linewidth=0.3, alpha=0.7)
    
    # Draw boundary circle
    circle = plt.Circle((0, 0), 255, fill=False, color='brown', linewidth=2)
    ax.add_patch(circle)
    
    ax.set_xlim(-270, 270)
    ax.set_ylim(-270, 270)
    ax.set_title(f'Sandsara Pattern ({len(polar_points)} points)')
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Visualization saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Convert SVG to Sandsara .bin pattern')
    parser.add_argument('input_svg', help='Input SVG file')
    parser.add_argument('output_bin', help='Output .bin file')
    parser.add_argument('--visualize', help='Save visualization PNG')
    parser.add_argument('--max-points', type=int, default=25000, help='Max points (default 25000)')
    parser.add_argument('--simplify', type=float, default=0, help='RDP simplification epsilon (0=off)')
    parser.add_argument('--density', type=float, default=0.5, help='Samples per SVG unit (default 0.5)')
    parser.add_argument('--max-rho', type=int, default=240, help='Max rho radius (default 240)')
    args = parser.parse_args()
    
    print(f"Reading SVG: {args.input_svg}")
    paths_d = extract_paths_from_svg(args.input_svg)
    print(f"Found {len(paths_d)} paths")
    
    # Convert each path to points
    path_groups = []
    for d in paths_d:
        pts = path_to_points(d, num_samples_per_unit=args.density)
        if pts:
            path_groups.append(pts)
    
    total = sum(len(g) for g in path_groups)
    print(f"Total raw points: {total}")
    
    # Simplify if needed
    if args.simplify > 0:
        path_groups = [simplify_path_rdp(g, args.simplify) for g in path_groups]
        total = sum(len(g) for g in path_groups)
        print(f"After simplification: {total}")
    
    # Connect paths
    all_points = connect_paths(path_groups)
    print(f"Connected path: {len(all_points)} points")
    
    # Downsample if too many points
    if len(all_points) > args.max_points:
        step = len(all_points) / args.max_points
        all_points = [all_points[int(i * step)] for i in range(args.max_points)]
        print(f"Downsampled to {len(all_points)} points")
    
    # Convert to polar
    polar = xy_to_polar_sandsara(all_points, max_rho=args.max_rho)
    
    # Write binary
    write_sandsara_bin(polar, args.output_bin)
    
    # Visualize
    if args.visualize:
        visualize(polar, args.visualize)


if __name__ == '__main__':
    main()
