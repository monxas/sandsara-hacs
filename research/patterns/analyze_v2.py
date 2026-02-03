#!/usr/bin/env python3
"""Try different interpretations of the pattern format."""

import struct
import math
from pathlib import Path

def analyze_raw(filepath):
    """Look at raw bytes with different interpretations."""
    with open(filepath, 'rb') as f:
        data = f.read()

    print(f"\n{'='*60}")
    print(f"File: {Path(filepath).name}")
    print(f"Size: {len(data)} bytes = {len(data)//6} points")
    print(f"{'='*60}")

    # Show first 60 bytes (10 points) as hex
    print("\nFirst 60 bytes (hex):")
    for i in range(0, min(60, len(data)), 6):
        chunk = data[i:i+6]
        hex_str = ' '.join(f'{b:02x}' for b in chunk)
        print(f"  Point {i//6:3}: {hex_str}")

    print("\n" + "-"*60)
    print("Interpretation 1: Big-endian (θ, ρ, counter)")
    print("-"*60)
    for i in range(0, min(60, len(data)), 6):
        v1, v2, v3 = struct.unpack('>HHH', data[i:i+6])
        theta_deg = (v1 / 65535) * 360
        print(f"  [{i//6:3}] θ={theta_deg:7.2f}°  ρ={v2:5}  v3={v3:5}")

    print("\n" + "-"*60)
    print("Interpretation 2: Little-endian (θ, ρ, counter)")
    print("-"*60)
    for i in range(0, min(60, len(data)), 6):
        v1, v2, v3 = struct.unpack('<HHH', data[i:i+6])
        theta_deg = (v1 / 65535) * 360
        print(f"  [{i//6:3}] θ={theta_deg:7.2f}°  ρ={v2:5}  v3={v3:5}")

    print("\n" + "-"*60)
    print("Interpretation 3: θ (16-bit) + ρ (32-bit little-endian)")
    print("-"*60)
    for i in range(0, min(60, len(data)), 6):
        theta = struct.unpack('>H', data[i:i+2])[0]
        rho = struct.unpack('<I', data[i+2:i+6])[0]
        theta_deg = (theta / 65535) * 360
        print(f"  [{i//6:3}] θ={theta_deg:7.2f}°  ρ={rho:10}")

    print("\n" + "-"*60)
    print("Interpretation 4: 3 bytes each for X and Y (big-endian)")
    print("-"*60)
    for i in range(0, min(60, len(data)), 6):
        # 3 bytes big-endian for each coordinate
        x = (data[i] << 16) | (data[i+1] << 8) | data[i+2]
        y = (data[i+3] << 16) | (data[i+4] << 8) | data[i+5]
        print(f"  [{i//6:3}] X={x:8}  Y={y:8}")

    print("\n" + "-"*60)
    print("Interpretation 5: Signed 16-bit (X, Y, Z)")
    print("-"*60)
    for i in range(0, min(60, len(data)), 6):
        x, y, z = struct.unpack('>hhh', data[i:i+6])
        print(f"  [{i//6:3}] X={x:6}  Y={y:6}  Z={z:6}")

def main():
    samples_dir = Path(__file__).parent / 'samples'

    # Focus on the simplest test file
    for name in ['testing-circle.bin', 'testing-x.bin']:
        filepath = samples_dir / name
        if filepath.exists():
            analyze_raw(filepath)

if __name__ == '__main__':
    main()
