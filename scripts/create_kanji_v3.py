#!/usr/bin/env python3
"""
Sandsara pattern generator for kanji 栄 (ei - prosperity/glory)

Physical constraint: The ball ALWAYS leaves a trail - it cannot jump.
When moving to a new stroke, we must RETRACE the existing path.

Format: X (int16 LE) + ',' + Y (int16 LE) + '\n' = 6 bytes per point
Coordinates: -32767 to +32767, scale ~0.7, center (0,0), Y+ is UP
"""

import struct
import os

# Scale factor to stay within bounds
SCALE = 0.65
MAX_COORD = int(32767 * SCALE)

def lerp_points(start, end, num_points):
    """Generate interpolated points between start and end."""
    points = []
    for i in range(num_points):
        t = i / max(num_points - 1, 1)
        x = int(start[0] + (end[0] - start[0]) * t)
        y = int(start[1] + (end[1] - start[1]) * t)
        points.append((x, y))
    return points

def bezier_quadratic(p0, p1, p2, num_points):
    """Generate points along a quadratic Bezier curve."""
    points = []
    for i in range(num_points):
        t = i / max(num_points - 1, 1)
        x = int((1-t)**2 * p0[0] + 2*(1-t)*t * p1[0] + t**2 * p2[0])
        y = int((1-t)**2 * p0[1] + 2*(1-t)*t * p1[1] + t**2 * p2[1])
        points.append((x, y))
    return points

def bezier_cubic(p0, p1, p2, p3, num_points):
    """Generate points along a cubic Bezier curve."""
    points = []
    for i in range(num_points):
        t = i / max(num_points - 1, 1)
        x = int((1-t)**3 * p0[0] + 3*(1-t)**2*t * p1[0] + 3*(1-t)*t**2 * p2[0] + t**3 * p3[0])
        y = int((1-t)**3 * p0[1] + 3*(1-t)**2*t * p1[1] + 3*(1-t)*t**2 * p2[1] + t**3 * p3[1])
        points.append((x, y))
    return points

class KanjiEi:
    def __init__(self):
        self.points = []
        self.current_pos = (0, 0)
        
    def add_points(self, new_points):
        """Add points to the path."""
        if new_points:
            self.points.extend(new_points)
            self.current_pos = new_points[-1]
    
    def move_to(self, target, num_points=80):
        """Move to a new position (creates visible line)."""
        pts = lerp_points(self.current_pos, target, num_points)
        self.add_points(pts)
    
    def scale_point(self, x, y):
        """Scale normalized coordinates to Sandsara coordinates."""
        return (int(x * MAX_COORD), int(y * MAX_COORD))
    
    def draw_flame_left(self):
        """Draw the left flame mark - curved diagonal stroke."""
        start = self.scale_point(-0.38, 0.88)
        ctrl = self.scale_point(-0.28, 0.72)
        end = self.scale_point(-0.20, 0.52)
        
        if self.points:
            self.move_to(start, 150)
        else:
            self.current_pos = start
            self.points.append(start)
        
        pts = bezier_quadratic(start, ctrl, end, 200)
        self.add_points(pts)
        self.add_points(pts[::-1])
    
    def draw_flame_center(self):
        """Draw the center flame - vertical stroke."""
        top = self.scale_point(0.0, 0.92)
        bottom = self.scale_point(0.0, 0.52)
        
        self.move_to(top, 150)
        pts = lerp_points(top, bottom, 180)
        self.add_points(pts)
        self.add_points(pts[::-1])
    
    def draw_flame_right(self):
        """Draw the right flame mark - curved diagonal stroke."""
        start = self.scale_point(0.32, 0.88)
        ctrl = self.scale_point(0.24, 0.72)
        end = self.scale_point(0.16, 0.55)
        
        self.move_to(start, 150)
        pts = bezier_quadratic(start, ctrl, end, 200)
        self.add_points(pts)
        self.add_points(pts[::-1])
    
    def draw_roof(self):
        """Draw the roof component 冖 with hooks at corners."""
        # Key coordinates
        left_hook_bottom = self.scale_point(-0.58, 0.22)
        left_hook_mid = self.scale_point(-0.58, 0.38)
        left_corner = self.scale_point(-0.52, 0.44)
        right_corner = self.scale_point(0.58, 0.44)
        right_hook_mid = self.scale_point(0.64, 0.38)
        right_hook_bottom = self.scale_point(0.64, 0.18)
        
        # Move to left hook
        self.move_to(left_hook_bottom, 150)
        
        # Left hook upward with curve
        pts1 = lerp_points(left_hook_bottom, left_hook_mid, 80)
        self.add_points(pts1)
        
        pts2 = bezier_quadratic(left_hook_mid, 
                               self.scale_point(-0.56, 0.46),
                               left_corner, 60)
        self.add_points(pts2)
        
        # Horizontal roof line
        pts3 = lerp_points(left_corner, right_corner, 350)
        self.add_points(pts3)
        
        # Curve into right hook
        pts4 = bezier_quadratic(right_corner,
                               self.scale_point(0.62, 0.46),
                               right_hook_mid, 60)
        self.add_points(pts4)
        
        # Right hook downward
        pts5 = lerp_points(right_hook_mid, right_hook_bottom, 100)
        self.add_points(pts5)
        
        # RETURN to center of roof for next stroke
        self.add_points(pts5[::-1])
        self.add_points(pts4[::-1])
        center_roof = self.scale_point(0.0, 0.44)
        return_pts = lerp_points(right_corner, center_roof, 180)
        self.add_points(return_pts)
    
    def draw_middle_horizontal(self):
        """Draw the middle horizontal line."""
        center = self.scale_point(0.0, 0.12)
        left = self.scale_point(-0.42, 0.12)
        right = self.scale_point(0.42, 0.12)
        
        # Move from roof to center of this line
        self.move_to(center, 120)
        
        # Go left
        pts_left = lerp_points(center, left, 150)
        self.add_points(pts_left)
        self.add_points(pts_left[::-1])
        
        # Go right
        pts_right = lerp_points(center, right, 150)
        self.add_points(pts_right)
        self.add_points(pts_right[::-1])
    
    def draw_tree_radical(self):
        """Draw the tree radical 木 at bottom."""
        # Trunk from middle line down
        trunk_top = self.scale_point(0.0, 0.12)
        branch_point = self.scale_point(0.0, -0.22)
        trunk_bottom = self.scale_point(0.0, -0.88)
        
        # Branch endpoints
        left_branch_end = self.scale_point(-0.48, -0.72)
        right_branch_end = self.scale_point(0.48, -0.72)
        
        # We're at center, go down to branch point
        pts1 = lerp_points(trunk_top, branch_point, 120)
        self.add_points(pts1)
        
        # Left diagonal branch
        pts_left = lerp_points(branch_point, left_branch_end, 180)
        self.add_points(pts_left)
        self.add_points(pts_left[::-1])
        
        # Right diagonal branch  
        pts_right = lerp_points(branch_point, right_branch_end, 180)
        self.add_points(pts_right)
        self.add_points(pts_right[::-1])
        
        # Continue trunk to bottom
        pts2 = lerp_points(branch_point, trunk_bottom, 200)
        self.add_points(pts2)
    
    def generate(self):
        """Generate the complete kanji path."""
        print("Generating kanji 栄 pattern...")
        
        print("  1. Drawing left flame...")
        self.draw_flame_left()
        
        print("  2. Drawing center flame...")
        self.draw_flame_center()
        
        print("  3. Drawing right flame...")
        self.draw_flame_right()
        
        print("  4. Drawing roof 冖...")
        self.draw_roof()
        
        print("  5. Drawing middle horizontal line...")
        self.draw_middle_horizontal()
        
        print("  6. Drawing tree radical 木...")
        self.draw_tree_radical()
        
        print(f"  Total points: {len(self.points)}")
        return self.points

def write_sandsara_binary(points, filename):
    """Write points in Sandsara binary format."""
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    with open(filename, 'wb') as f:
        for x, y in points:
            x = max(-32767, min(32767, x))
            y = max(-32767, min(32767, y))
            f.write(struct.pack('<h', x))
            f.write(b',')
            f.write(struct.pack('<h', y))
            f.write(b'\n')
    
    print(f"Written {len(points)} points ({len(points) * 6} bytes) to {filename}")

def main():
    kanji = KanjiEi()
    points = kanji.generate()
    
    output_file = "/root/clawd/sandsara-hacs/research/patterns/kanji-ei-v3.bin"
    write_sandsara_binary(points, output_file)
    
    print("\nVerification - first 10 points:")
    with open(output_file, 'rb') as f:
        for i in range(10):
            chunk = f.read(6)
            if len(chunk) == 6:
                x = struct.unpack('<h', chunk[0:2])[0]
                y = struct.unpack('<h', chunk[3:5])[0]
                hex_repr = ' '.join(f'{b:02x}' for b in chunk)
                print(f"  {i}: X={x:6d}, Y={y:6d}  |  {hex_repr}")
    
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    print(f"\nRanges: X=[{min(xs)}, {max(xs)}]  Y=[{min(ys)}, {max(ys)}]")
    print(f"File size: {os.path.getsize(output_file)} bytes")

if __name__ == "__main__":
    main()
