#!/usr/bin/env python3
"""Simple web server to visualize Sandsara patterns."""

import struct
import math
import json
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse

SAMPLES_DIR = Path(__file__).parent.parent / 'samples'

def read_pattern(filepath, sort_mode='original'):
    """Read pattern file and return points as list of dicts.

    ACTUAL FORMAT from Sandsara firmware (SdFiles.cpp):
    - bytes 0-1: signed int16 LITTLE-ENDIAN = X coordinate
    - byte 2: comma separator (0x2C = ',')
    - bytes 3-4: signed int16 LITTLE-ENDIAN = Y coordinate
    - byte 5: newline (0x0A = '\\n')
    """
    with open(filepath, 'rb') as f:
        data = f.read()

    raw_points = []
    for i in range(0, len(data), 6):
        chunk = data[i:i+6]
        if len(chunk) == 6:
            # Little-endian signed 16-bit integers
            x_raw = struct.unpack('<h', chunk[0:2])[0]  # signed short, little-endian
            y_raw = struct.unpack('<h', chunk[3:5])[0]  # signed short, little-endian
            raw_points.append({
                'index': i // 6,
                'x_raw': x_raw,
                'y_raw': y_raw,
            })

    # Find the range for normalization
    if raw_points:
        all_x = [p['x_raw'] for p in raw_points]
        all_y = [p['y_raw'] for p in raw_points]
        max_val = max(max(abs(min(all_x)), abs(max(all_x))),
                      max(abs(min(all_y)), abs(max(all_y))))
        if max_val == 0:
            max_val = 1
    else:
        max_val = 32767

    points = []
    for p in raw_points:
        # Normalize to -1 to 1 range
        x = p['x_raw'] / max_val
        y = p['y_raw'] / max_val

        points.append({
            'x': round(x, 4),
            'y': round(y, 4),
            'x_raw': p['x_raw'],
            'y_raw': p['y_raw'],
        })
    return points

def list_patterns():
    """List available pattern files."""
    patterns = []
    if SAMPLES_DIR.exists():
        for f in sorted(SAMPLES_DIR.glob('*.bin')):
            size = f.stat().st_size
            points = size // 6
            patterns.append({
                'name': f.name,
                'size': size,
                'points': points,
            })
    return patterns

class PatternHandler(SimpleHTTPRequestHandler):
    """Custom handler for pattern API endpoints."""

    def __init__(self, *args, **kwargs):
        # Serve files from webui directory
        super().__init__(*args, directory=str(Path(__file__).parent), **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == '/api/patterns':
            self.send_json(list_patterns())
        elif path.startswith('/api/pattern/'):
            name = urllib.parse.unquote(path[13:])
            # Parse query string for sort mode
            query = urllib.parse.parse_qs(parsed.query)
            sort_mode = query.get('sort', ['v3_theta'])[0]

            filepath = SAMPLES_DIR / name
            if filepath.exists() and filepath.suffix == '.bin':
                points = read_pattern(filepath, sort_mode)
                self.send_json({
                    'name': name,
                    'points': points,
                    'count': len(points),
                    'sort_mode': sort_mode,
                })
            else:
                self.send_error(404, f'Pattern not found: {name}')
        else:
            super().do_GET()

    def send_json(self, data):
        """Send JSON response."""
        content = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(content))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        """Suppress default logging for cleaner output."""
        if '/api/' in args[0]:
            print(f"API: {args[0]}")

def main():
    port = 8765
    server = HTTPServer(('localhost', port), PatternHandler)
    print(f"\n{'='*50}")
    print(f"  Sandsara Pattern Visualizer")
    print(f"{'='*50}")
    print(f"\n  Open in browser: http://localhost:{port}")
    print(f"\n  Found {len(list_patterns())} pattern files")
    print(f"\n  Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.shutdown()

if __name__ == '__main__':
    main()
