#!/usr/bin/env python3
"""Analyze Sandsara pattern files and visualize them."""

import struct
import sys
import math
from pathlib import Path

def read_pattern(filepath):
    """Read pattern file and return list of 6-byte tuples."""
    with open(filepath, 'rb') as f:
        data = f.read()

    points = []
    for i in range(0, len(data), 6):
        chunk = data[i:i+6]
        if len(chunk) == 6:
            # Try big-endian uint16 interpretation
            v1, v2, v3 = struct.unpack('>HHH', chunk)
            points.append((v1, v2, v3))
    return points

def analyze_pattern(filepath):
    """Analyze a pattern file and print statistics."""
    points = read_pattern(filepath)

    print(f"\n{'='*60}")
    print(f"File: {Path(filepath).name}")
    print(f"{'='*60}")
    print(f"Total points: {len(points)}")

    if not points:
        return points

    v1_vals = [p[0] for p in points]
    v2_vals = [p[1] for p in points]
    v3_vals = [p[2] for p in points]

    print(f"\nv1 (possible theta/angle):")
    print(f"  min={min(v1_vals):6}, max={max(v1_vals):6}, range={max(v1_vals)-min(v1_vals):6}")

    print(f"\nv2 (possible rho/radius):")
    print(f"  min={min(v2_vals):6}, max={max(v2_vals):6}, range={max(v2_vals)-min(v2_vals):6}")

    print(f"\nv3 (unknown/counter?):")
    print(f"  min={min(v3_vals):6}, max={max(v3_vals):6}, range={max(v3_vals)-min(v3_vals):6}")

    # Check if v3 is incrementing
    is_incrementing = all(v3_vals[i] <= v3_vals[i+1] for i in range(len(v3_vals)-1))
    print(f"  monotonically increasing: {is_incrementing}")

    print(f"\nFirst 10 points:")
    for i, (v1, v2, v3) in enumerate(points[:10]):
        # Convert v1 to angle (0-65535 -> 0-360)
        angle_deg = (v1 / 65535) * 360
        print(f"  [{i:4}] v1={v1:5} ({angle_deg:6.1f}°), v2={v2:5}, v3={v3:5}")

    return points

def plot_polar(points, title, output_path):
    """Plot points assuming polar coordinates (v1=theta, v2=rho)."""
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("matplotlib not installed. Install with: pip install matplotlib")
        return

    # Convert to polar coordinates
    # v1: 0-65535 maps to 0-2pi
    # v2: radius (use as-is)
    theta = [(p[0] / 65535) * 2 * math.pi for p in points]
    rho = [p[1] for p in points]

    # Convert polar to cartesian for plotting
    x = [r * math.cos(t) for r, t in zip(rho, theta)]
    y = [r * math.sin(t) for r, t in zip(rho, theta)]

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Plot 1: Polar as cartesian
    ax1 = axes[0]
    ax1.plot(x, y, 'b-', linewidth=0.5, alpha=0.7)
    ax1.set_aspect('equal')
    ax1.set_title(f'{title}\nPolar interpretation (v1=θ, v2=ρ)')
    ax1.set_xlabel('X')
    ax1.set_ylabel('Y')
    ax1.grid(True, alpha=0.3)

    # Plot 2: Direct cartesian (v1=x, v2=y)
    ax2 = axes[1]
    v1_vals = [p[0] for p in points]
    v2_vals = [p[1] for p in points]
    ax2.plot(v1_vals, v2_vals, 'r-', linewidth=0.5, alpha=0.7)
    ax2.set_aspect('equal')
    ax2.set_title(f'{title}\nCartesian interpretation (v1=X, v2=Y)')
    ax2.set_xlabel('v1')
    ax2.set_ylabel('v2')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    print(f"\nSaved plot to: {output_path}")
    plt.close()

def main():
    samples_dir = Path(__file__).parent / 'samples'
    output_dir = Path(__file__).parent / 'plots'
    output_dir.mkdir(exist_ok=True)

    # Analyze test patterns first
    test_files = ['testing-circle.bin', 'testing-spiral.bin', 'testing-x.bin']

    for filename in test_files:
        filepath = samples_dir / filename
        if filepath.exists():
            points = analyze_pattern(filepath)
            if points:
                plot_polar(points, filename, output_dir / f'{filepath.stem}.png')

    # Also analyze smallest regular pattern
    smallest = samples_dir / 'Sandsara-trackNumber-0014.bin'
    if smallest.exists():
        points = analyze_pattern(smallest)
        if points:
            plot_polar(points, smallest.name, output_dir / 'track-0014.png')

if __name__ == '__main__':
    main()
