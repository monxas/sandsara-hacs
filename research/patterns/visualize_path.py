#!/usr/bin/env python3
"""Visualize Sandsara patterns as sequential paths."""

import struct
import math
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

def read_pattern(filepath):
    """Read pattern file and return points."""
    with open(filepath, 'rb') as f:
        data = f.read()

    points = []
    for i in range(0, len(data), 6):
        chunk = data[i:i+6]
        if len(chunk) == 6:
            # Big-endian: theta (uint16), rho (uint16), counter (uint16)
            theta_raw, rho_raw, counter = struct.unpack('>HHH', chunk)
            # Convert theta: 0-65535 -> 0-2π
            theta = (theta_raw / 65535.0) * 2 * math.pi
            # Rho is approximately 11264-11519, normalize to 0-1
            rho_norm = (rho_raw - 11264) / 255.0
            points.append({
                'theta': theta,
                'rho': rho_raw,
                'rho_norm': rho_norm,
                'counter': counter,
                'theta_raw': theta_raw,
            })
    return points

def plot_pattern(filepath, output_dir):
    """Create visualization of pattern."""
    points = read_pattern(filepath)
    name = Path(filepath).stem

    # Convert to cartesian for plotting
    x = [p['rho'] * math.cos(p['theta']) for p in points]
    y = [p['rho'] * math.sin(p['theta']) for p in points]

    fig, axes = plt.subplots(2, 2, figsize=(14, 12))

    # Plot 1: Full path with color gradient showing sequence
    ax1 = axes[0, 0]
    n = len(x)
    colors = np.linspace(0, 1, n)
    scatter = ax1.scatter(x, y, c=colors, cmap='viridis', s=1, alpha=0.7)
    ax1.set_aspect('equal')
    ax1.set_title(f'{name}\nFull path (color = sequence order)')
    ax1.set_xlabel('X')
    ax1.set_ylabel('Y')
    plt.colorbar(scatter, ax=ax1, label='Point sequence (0=start, 1=end)')

    # Plot 2: First 100 points as connected line
    ax2 = axes[0, 1]
    n_show = min(100, len(x))
    ax2.plot(x[:n_show], y[:n_show], 'b-', linewidth=1, alpha=0.8)
    ax2.plot(x[0], y[0], 'go', markersize=10, label='Start')
    ax2.plot(x[n_show-1], y[n_show-1], 'ro', markersize=10, label='Point 100')
    ax2.set_aspect('equal')
    ax2.set_title(f'First {n_show} points connected')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Plot 3: Theta over sequence
    ax3 = axes[1, 0]
    theta_vals = [p['theta_raw'] for p in points]
    ax3.plot(range(len(theta_vals)), theta_vals, 'b-', linewidth=0.5)
    ax3.set_xlabel('Point index')
    ax3.set_ylabel('Theta (raw)')
    ax3.set_title('Theta over sequence')
    ax3.grid(True, alpha=0.3)

    # Plot 4: Rho over sequence
    ax4 = axes[1, 1]
    rho_vals = [p['rho'] for p in points]
    ax4.plot(range(len(rho_vals)), rho_vals, 'r-', linewidth=0.5)
    ax4.set_xlabel('Point index')
    ax4.set_ylabel('Rho (raw)')
    ax4.set_title('Rho over sequence')
    ax4.grid(True, alpha=0.3)
    ax4.set_ylim(11200, 11600)

    plt.tight_layout()
    output_path = output_dir / f'{name}_detail.png'
    plt.savefig(output_path, dpi=150)
    print(f"Saved: {output_path}")
    plt.close()

    # Print summary
    print(f"\n{name}:")
    print(f"  Points: {len(points)}")
    print(f"  Theta range: {min(theta_vals)} - {max(theta_vals)}")
    print(f"  Rho range: {min(rho_vals)} - {max(rho_vals)}")

def main():
    samples_dir = Path(__file__).parent / 'samples'
    output_dir = Path(__file__).parent / 'plots'
    output_dir.mkdir(exist_ok=True)

    # Test files
    for name in ['testing-circle.bin', 'testing-spiral.bin', 'testing-x.bin']:
        filepath = samples_dir / name
        if filepath.exists():
            plot_pattern(filepath, output_dir)

    # Also a regular pattern
    filepath = samples_dir / 'Sandsara-trackNumber-0014.bin'
    if filepath.exists():
        plot_pattern(filepath, output_dir)

if __name__ == '__main__':
    main()
