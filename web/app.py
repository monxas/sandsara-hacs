#!/usr/bin/env python3
"""
Sandsara Pattern Viewer - Web UI
FastAPI backend for visualizing .bin pattern files
"""

import os
import struct
import math
from pathlib import Path
from typing import List, Dict, Any

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Sandsara Pattern Viewer", version="1.0.0")

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
BASE_DIR = Path(__file__).parent
PATTERNS_DIR = BASE_DIR.parent / "research" / "patterns"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def parse_pattern(file_path: Path) -> Dict[str, Any]:
    """Parse a .bin pattern file and return points as cartesian coordinates."""
    with open(file_path, "rb") as f:
        data = f.read()
    
    file_size = len(data)
    num_points = file_size // 6
    
    points = []
    for i in range(num_points):
        offset = i * 6
        if offset + 6 > len(data):
            break
        
        # Binary CSV format: X (int16 LE) + ',' (0x2C) + Y (int16 LE) + '\n' (0x0A)
        # Structure: [X_lo][X_hi][,][Y_lo][Y_hi][\n] = 6 bytes
        x_raw = struct.unpack('<h', data[offset:offset+2])[0]
        y_raw = struct.unpack('<h', data[offset+3:offset+5])[0]
        
        # Normalize to -1 to 1 range (values are -32768 to +32767)
        x = x_raw / 32767.0
        y = y_raw / 32767.0
        
        points.append({"x": round(x, 4), "y": round(y, 4)})
    
    return {
        "name": file_path.name,
        "file_size": file_size,
        "num_points": num_points,
        "points": points
    }


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main HTML page."""
    html_path = TEMPLATES_DIR / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=500, detail="Template not found")
    return html_path.read_text()


@app.get("/api/patterns")
async def list_patterns() -> List[Dict[str, Any]]:
    """List all available .bin pattern files."""
    patterns = []
    
    if not PATTERNS_DIR.exists():
        return patterns
    
    # Sort with real-oviedo first, then originals, then others
    def sort_key(p):
        name = p.name.lower()
        if 'real-oviedo' in name:
            return (0, name)
        elif name.startswith('sandsara-tracknumber'):
            return (1, name)
        else:
            return (2, name)
    
    for file_path in sorted(PATTERNS_DIR.glob("*.bin"), key=sort_key):
        stat = file_path.stat()
        num_points = stat.st_size // 6
        patterns.append({
            "name": file_path.name,
            "file_size": stat.st_size,
            "num_points": num_points,
            "path": str(file_path.relative_to(PATTERNS_DIR))
        })
    
    return patterns


@app.get("/api/patterns/{pattern_name}")
async def get_pattern(pattern_name: str) -> Dict[str, Any]:
    """Get parsed data for a specific pattern."""
    file_path = PATTERNS_DIR / pattern_name
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Pattern not found")
    
    if not file_path.suffix == ".bin":
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    return parse_pattern(file_path)


@app.post("/api/patterns/upload")
async def upload_pattern(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Upload a new .bin pattern file."""
    if not file.filename.endswith(".bin"):
        raise HTTPException(status_code=400, detail="Only .bin files are allowed")
    
    # Ensure patterns directory exists
    PATTERNS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save the file
    file_path = PATTERNS_DIR / file.filename
    content = await file.read()
    
    # Validate it's a valid pattern (must be divisible by 6)
    if len(content) % 6 != 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid pattern file: size {len(content)} is not divisible by 6"
        )
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    return {
        "message": "Pattern uploaded successfully",
        "name": file.filename,
        "file_size": len(content),
        "num_points": len(content) // 6
    }


@app.post("/api/patterns/generate/{pattern_type}")
async def generate_pattern(pattern_type: str) -> Dict[str, Any]:
    """Generate a sample pattern for testing."""
    PATTERNS_DIR.mkdir(parents=True, exist_ok=True)
    
    data = bytearray()
    
    def write_point(x_val, y_val):
        """Write a point in binary CSV format: X (int16 LE) + ',' + Y (int16 LE) + '\n'"""
        x_int = max(-32768, min(32767, int(x_val * 32767)))
        y_int = max(-32768, min(32767, int(y_val * 32767)))
        return struct.pack('<h', x_int) + b',' + struct.pack('<h', y_int) + b'\n'
    
    if pattern_type == "circle":
        # Simple circle
        num_points = 360
        for i in range(num_points):
            angle = (i / num_points) * 2 * math.pi
            x = math.cos(angle) * 0.9
            y = math.sin(angle) * 0.9
            data.extend(write_point(x, y))
        filename = "generated-circle.bin"
        
    elif pattern_type == "spiral":
        # Spiral outward
        num_points = 1000
        revolutions = 5
        for i in range(num_points):
            angle = (i / num_points) * 2 * math.pi * revolutions
            radius = (i / num_points) * 0.9
            x = math.cos(angle) * radius
            y = math.sin(angle) * radius
            data.extend(write_point(x, y))
        filename = "generated-spiral.bin"
        
    elif pattern_type == "flower":
        # Rose curve pattern
        num_points = 720
        petals = 5
        for i in range(num_points):
            angle = (i / num_points) * 2 * math.pi * petals
            radius = abs(math.cos(petals * angle / 2)) * 0.9
            x = math.cos(angle) * radius
            y = math.sin(angle) * radius
            data.extend(write_point(x, y))
        filename = "generated-flower.bin"
        
    elif pattern_type == "star":
        # Star pattern with spikes
        num_points = 360
        spikes = 8
        for i in range(num_points):
            angle = (i / num_points) * 2 * math.pi
            radius = (0.4 + 0.5 * abs(math.cos(spikes * angle / 2))) * 0.9
            x = math.cos(angle) * radius
            y = math.sin(angle) * radius
            data.extend(write_point(x, y))
        filename = "generated-star.bin"
        
    else:
        raise HTTPException(status_code=400, detail=f"Unknown pattern type: {pattern_type}")
    
    file_path = PATTERNS_DIR / filename
    with open(file_path, "wb") as f:
        f.write(data)
    
    return {
        "message": f"Generated {pattern_type} pattern",
        "name": filename,
        "file_size": len(data),
        "num_points": len(data) // 6
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8095)
